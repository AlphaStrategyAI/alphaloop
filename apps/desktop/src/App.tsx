import {FormEvent, useCallback, useEffect, useMemo, useState} from "react";

import {bindDesktopApi} from "./api-bind";

import type {
  AnomalyPresentation,
  BriefSlotName,
  DesktopApi,
  DesktopView,
  HostStatus,
  ResearchStatus,
  SidecarUiState,
  ValidationMethod,
} from "./contracts";
import {formatResearchTimestamp} from "./format";
import {readBrowserRoute, routeFromHash} from "./routing";
import "./night.css";

const anomalyIndicatorLabels: Record<string, string> = {
  sharpe_outlier: "夏普比率相对基线异常偏高",
  coverage_shrunk: "数据覆盖相比开始时已缩减",
  high_trial_count: "尝试次数相对基线异常多",
  recent_method_revision: "验证方法近期有修订",
};

function AnomalyChecklist({anomaly}: {anomaly: AnomalyPresentation}) {
  const baseline = anomaly.baseline;
  const hasSharpe = baseline && "sharpe" in baseline && baseline.sharpe != null;
  const hasTrialCount = baseline && "trialCount" in baseline && baseline.trialCount != null;
  return (
    <section className="anomaly-section" data-testid="anomaly-checklist">
      <h4>结果需要额外审视</h4>
      {baseline && (
        <p className="baseline-note">
          对比基线：{baseline.kind === "version_1_logic" ? "第一版逻辑" : baseline.kind}
          {hasSharpe && ` · 基线夏普 ${(baseline as {sharpe: number}).sharpe}`}
          {hasTrialCount && ` · 基线尝试 ${(baseline as {trialCount: number}).trialCount}`}
        </p>
      )}
      <ul className="anomaly-checklist">
        {anomaly.indicators.map((indicator) => (
          <li key={indicator}>
            <span className="indicator-icon">⚠</span>
            <span>{anomalyIndicatorLabels[indicator] ?? indicator}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export interface AppProps {
  api: DesktopApi;
  initialView: DesktopView;
  /** Hash route for first paint; defaults to browser location. */
  initialRoute?: string;
  /** Test hook: poll Tauri sidecar supervision state. */
  pollSidecar?: () => Promise<SidecarUiState | null>;
  /** Test hook: manual engine restart from the shell. */
  restartSidecar?: () => Promise<void>;
}

const statusLabels: Record<ResearchStatus, string> = {
  draft: "草稿",
  running: "运行中",
  awaiting_confirm: "等待确认",
  paused: "已暂停",
  completed: "已完成",
  ended: "已结束（未通过）",
};

const hostStatusLabels: Record<HostStatus, string> = {
  awaiting_confirm: "等待确认",
  running: "运行中",
  completed: "已完成",
  idle: "本机静",
};


export function routeFor(view: DesktopView): string {
  if (view.kind === "research_list") return "#/research";
  if (view.kind === "methods") return `#/methods${view.selected ? `/${view.selected}` : ""}`;
  return `#/research/${view.researchId}`;
}

function Logo() {
  return <div className="logo" aria-label="alphaloop">α<span /></div>;
}

function NightShell({view, children}: {view: DesktopView; children: React.ReactNode}) {
  const methods = view.kind === "methods";
  const hostKey: HostStatus = view.hostStatus ?? (
    view.kind === "awaiting_confirm" ? "awaiting_confirm" :
    view.kind === "running" ? "running" :
    view.kind === "completed" ? "completed" : "idle"
  );
  const hostStatus = hostStatusLabels[hostKey];
  return (
    <main className="night-shell" data-testid="night-shell" data-view={view.kind}>
      <aside className="rail" data-testid="rail">
        <div className="rail-center">
          <Logo />
          <nav aria-label="主导航">
            <a className={!methods ? "active" : ""} href="#/research">研究</a>
            <a className={methods ? "active" : ""} href="#/methods">方法库</a>
          </nav>
        </div>
        <div className={`host-status ${hostKey}`}>● {hostStatus}</div>
      </aside>
      <section className={`content ${view.kind}`}>
        {view.thesisChangeHint && <p className="thesis-hint">{view.thesisChangeHint}</p>}
        {children}
      </section>
    </main>
  );
}

function StatusPill({status}: {status: ResearchStatus}) {
  return <span className={`status-pill ${status}`}>{statusLabels[status]}</span>;
}

const deleteWarning =
  "删除会永久移除对话、版本、迭代与验证记录及导出资格；已导出的本机文件不受影响。";

function confirmDelete(api: DesktopApi, researchId: string) {
  if (window.confirm(deleteWarning)) void api.deleteResearch(researchId);
}

function ResearchList({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "research_list"}>}) {
  const awaiting = view.awaiting;
  const rows = view.rows;
  return (
    <div className="browse list-screen">
      <header className="list-header">
        <p>一条对话，一次研究。等你确认的会排在最上面。</p>
        <button
          className="quiet-button"
          onClick={() => {
            void api.createDraft().then((id) => {
              window.location.hash = `#/research/${id}`;
            });
          }}
        >
          新建研究
        </button>
      </header>
      {awaiting && (
        <article className="awaiting-primary" data-kind="awaiting-primary">
          <a className="awaiting-primary-body" href={`#/research/${awaiting.id}`}>
            <h2>{awaiting.title}</h2>
            <p>
              <span>{awaiting.universeLabel ?? "未锁定"}</span>
              {awaiting.createdAt
                ? ` · ${formatResearchTimestamp(awaiting.createdAt)}`
                : " · 等了 2 小时"}
            </p>
          </a>
          <div className="row-actions">
            <a href={`#/research/${awaiting.id}`}>进入</a>
            <button onClick={() => confirmDelete(api, awaiting.id)}>删除</button>
            <StatusPill status="awaiting_confirm" />
          </div>
        </article>
      )}
      <div className="research-rows">
        {rows.map((row) => (
          <article className="research-row" data-testid="research-row" key={row.id}>
            <div>
              <h3>{row.title}</h3>
              <p>
                <span>{row.universeLabel ?? "未锁定"}</span>
                {row.createdAt ? ` · ${formatResearchTimestamp(row.createdAt)}` : ""}
                {row.updatedAt ? ` · 更新 ${formatResearchTimestamp(row.updatedAt)}` : ""}
              </p>
            </div>
            <div className="row-actions">
              <a href={`#/research/${row.id}`}>进入</a>
              <button onClick={() => confirmDelete(api, row.id)}>删除</button>
              <StatusPill status={row.status} />
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

const settingLabels: readonly [BriefSlotName, string][] = [
  ["thesis", "大致原理"],
  ["universe", "资产类别"],
  ["max_effective_hours", "最长研究时间"],
  ["round1_methods", "第一轮验证方法"],
  ["coverage_floor", "最低数据覆盖"],
];

function Settings({
  values,
  onEditSlot,
}: {
  values: Extract<DesktopView, {kind: "draft" | "confirm_run"}>["settings"];
  onEditSlot?: (slot: BriefSlotName) => void;
}) {
  return (
    <aside className="settings">
      <p className="eyebrow">研究设定</p>
      {settingLabels.map(([key, label]) => (
        <div data-testid="brief-slot" key={key}>
          <dt>{label}</dt>
          <dd>{values[key] || "未锁定"}</dd>
          {key === "universe" && values.universe_symbols ? (
            <dd className="universe-symbols" data-testid="universe-symbols">
              {values.universe_symbols}
            </dd>
          ) : null}
          {onEditSlot ? (
            <button
              className="text-button slot-edit"
              type="button"
              data-testid={`edit-slot-${key}`}
              onClick={() => onEditSlot(key)}
            >
              改一改
            </button>
          ) : null}
        </div>
      ))}
    </aside>
  );
}

function DraftScreen({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "draft"}>}) {
  const [message, setMessage] = useState("");
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const text = message.trim();
    if (!text) return;
    try {
      await api.sendDialogue(view.researchId, text);
      setMessage("");
    } catch {
      /* mutation error banner */
    }
  };
  return (
    <div className="draft-layout">
      <section className="conversation">
        <h1>新研究</h1>
        <p className="message assistant system" data-testid="dialogue-system-intro">
          我会逐项问清原理、资产、时间、方法和覆盖底线；齐全后进入确认开跑。
        </p>
        {view.dialogue.map((turn, index) => (
          <p className={`message ${turn.role}`} data-testid="dialogue-turn" key={index}>
            {turn.text}
          </p>
        ))}
        <form onSubmit={submit}>
          <input value={message} onChange={(event) => setMessage(event.target.value)} placeholder="把方向说清楚，不用填表。" />
        </form>
      </section>
      <Settings values={view.settings} />
    </div>
  );
}

export function ConfirmRunCard({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "confirm_run"}>}) {
  const editSlot = (slot: BriefSlotName) => void api.unlockBrief(view.researchId, slot);
  const [symbolsOpen, setSymbolsOpen] = useState(false);
  const sel = view.symbolSelection;
  return (
    <article className="confirm-card" data-testid="confirm-run-card">
      <h1>确认开跑</h1>
      <p>认下这次研究做什么、跑多久、拿什么验证。确认前不会自己开始。</p>
      <p>研究方法 / 建模方法 / 参数的小迭代自动做；经济逻辑改动、以及数据覆盖要跌破你认下的底线，都会停下来问你。</p>
      <p>最长研究时间只计有效研究时间，暂停和等你确认的时间不算。</p>
      {sel && (
        <section className="symbol-selection" data-testid="symbol-selection">
          <p className="eyebrow">标的与数据窗口（确认后锁定）</p>
          <p>
            {sel.count} 只 · {sel.listName} · 版本 {sel.listVersion}
            {sel.generatedDate ? ` · ${sel.generatedDate}` : ""}
            {sel.source === "user_override" || sel.overrideNote
              ? ` · ${sel.overrideNote ?? "已覆盖默认标的池"}`
              : " · 默认标的池"}
          </p>
          <p>数据区间 {sel.dataStart} 至 {sel.dataEnd}（截止 {sel.dataCutoff}） · 来源 {sel.dataSource}</p>
          <button
            type="button"
            className="text-button"
            data-testid="toggle-symbol-list"
            onClick={() => setSymbolsOpen((open) => !open)}
          >
            {symbolsOpen ? "收起全部标的" : "展开全部标的"}
          </button>
          {symbolsOpen && (
            <p className="symbol-ticker-list" data-testid="symbol-ticker-list">
              {sel.symbols.join("、")}
            </p>
          )}
        </section>
      )}
      <Settings values={view.settings} onEditSlot={editSlot} />
      <div className="actions">
        <button className="cyan-button" onClick={() => void api.confirmRun(view.researchId)}>确认开跑</button>
      </div>
    </article>
  );
}

function RunningScreen({
  api,
  view,
  modification,
  onModificationChange,
}: {
  api: DesktopApi;
  view: Extract<DesktopView, {kind: "running"}>;
  modification: string;
  onModificationChange: (text: string) => void;
}) {
  return (
    <div className="focus running-screen">
      <header>
        <StatusPill status={view.status} />
        {view.currentAction && view.currentAction !== "idle"
          ? ` ${view.currentAction} · `
          : " "}
        第 {view.version} 版 · 有效研究 {view.effective}
        {view.remaining ? ` · 剩余 ${view.remaining}` : ""}
        {" · "}{view.coverage}
        {view.versionTrialLabel ? ` · ${view.versionTrialLabel}` : ""}
        {view.windowCumulativeLabel ? ` · ${view.windowCumulativeLabel}` : ""}
      </header>
      {view.lastError && (
        <p className="run-error" data-testid="last-run-error">
          运行错误（{view.lastError.count} 次
          {view.lastError.code ? ` · ${view.lastError.code}` : ""}）：{view.lastError.message}
        </p>
      )}
      {view.honestStopHint && (
        <p className="honest-stop-hint" data-testid="honest-stop-hint-running">
          {view.honestStopHint}
        </p>
      )}
      <section className="materials-note">
        <p className="eyebrow">资料与数据说明</p>
        <p>用到的资料：{view.sources ?? "公开资料与本机材料"}</p>
        <p>数据截止：{view.dataCutoff || "以本轮冻结快照为准"}</p>
        <p>当前覆盖相对底线：{view.coverage}</p>
        <p>这里只说明结论的适用范围，不是行情终端。</p>
      </section>
      <h1>迭代与验证</h1>
      {view.anomaly && <AnomalyChecklist anomaly={view.anomaly} />}
      {view.rounds.map((round, index) => (
        <article className="round-card" key={round.roundId} data-testid="round-card">
          <small>v{view.version} · 第 {view.rounds.length - index} 轮</small>
          <div className="round-columns">
            <div className="round-logic">
              <p className="eyebrow">逻辑陈述</p>
              <p>{round.logicStatement.statement}</p>
              {round.logicStatement.changedFromPrior && round.logicStatement.changeDescription && (
                <p className="change-note">变更：{round.logicStatement.changeDescription}</p>
              )}
            </div>
            <div className="round-impl">
              <p className="eyebrow">实现与参数</p>
              {round.implementationDelta.modelChanges.length > 0 && (
                <p>模型变更：{round.implementationDelta.modelChanges.join(", ")}</p>
              )}
              {round.implementationDelta.paramChanges.length > 0 && (
                <ul className="param-changes">
                  {round.implementationDelta.paramChanges.map(([param, from, to]) => (
                    <li key={param}>{param}: {from} → {to}</li>
                  ))}
                </ul>
              )}
              {round.implementationDelta.modelChanges.length === 0 &&
               round.implementationDelta.paramChanges.length === 0 && (
                <p className="no-changes">本轮无实现变更</p>
              )}
            </div>
          </div>
          <div className="trial-counters">
            <span>候选 {round.trialCounters.candidatesEvaluated}</span>
            <span>通过 {round.trialCounters.candidatesPassed}</span>
            <span>第 {round.trialCounters.conclusionAttemptNumber} 次尝试</span>
            <span className={round.verificationPassed ? "passed" : "failed"}>
              {round.verificationPassed ? "✓ 验证通过" : "✗ 验证未通过"}
            </span>
          </div>
        </article>
      ))}
      {view.status === "running" ? (
        <button className="quiet-button" onClick={() => void api.pauseResearch(view.researchId)}>暂停</button>
      ) : (
        <>
          <button className="quiet-button" onClick={() => void api.resumeResearch(view.researchId)}>按当前版本继续</button>
          <input
            value={modification}
            onChange={(event) => onModificationChange(event.target.value)}
            placeholder="把最长研究时间改成 6 小时"
            data-testid="paused-modification-input"
          />
          <button
            className="quiet-button"
            data-testid="confirm-modification-button"
            disabled={!modification.trim()}
            onClick={() => void (async () => {
              await api.sendDialogue(view.researchId, modification.trim());
              await api.confirmModification(view.researchId);
            })()}
          >
            确认修改并开新版
          </button>
        </>
      )}
    </div>
  );
}

export function AwaitingConfirmCard({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "awaiting_confirm"}>}) {
  const [whoPays, setWhoPays] = useState("");
  const isCoverage = view.confirmKind === "coverage";
  const hasEvidence = view.whyChange && view.whyChange.length > 0;
  const canApproveEconomic = isCoverage || hasEvidence;
  const handleApprove = () => {
    void api.resolveConfirm(view.researchId, "approve_new_version", whoPays.trim() || undefined);
  };
  return (
    <article className="awaiting-card" data-testid="awaiting-confirm-card">
      <p className="eyebrow">等待确认 · 第 {view.version} 版 · 这段时间不计入额度</p>
      <h1>{isCoverage ? "数据覆盖要跌破底线" : "经济逻辑要改了"}</h1>
      <section><small>现在打算改什么</small><p>{view.proposed}</p></section>
      <section><small>为什么要改</small><p>{view.reason}</p></section>
      <section><small>改了之后会变成什么样</small><p>{view.effect}</p></section>
      {view.whyChange && view.whyChange.length > 0 && (
        <section className="evidence-section">
          <small>证据依据</small>
          <ul className="evidence-list">
            {view.whyChange.map((ref) => (
              <li key={ref.recordId}>
                <span className="evidence-kind">{ref.kind}</span>
                <span className="evidence-id">{ref.recordId}</span>
                {ref.summary && <span className="evidence-summary">{ref.summary}</span>}
                <span className="evidence-time">{ref.recordedAt}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {!isCoverage && (
        <section className="who-pays-section">
          <small>谁为此买单（选填）</small>
          <textarea
            value={whoPays}
            onChange={(e) => setWhoPays(e.target.value)}
            placeholder="不填则记录为「未作答」"
            className="who-pays-input"
          />
        </section>
      )}
      {isCoverage ? (
        <div className="decision-stack coverage-decisions" data-testid="coverage-decisions">
          <button className="cyan-button" onClick={() => void api.resolveConfirm(view.researchId, "accept_lower_floor")}>
            认下更低底线并开新版
          </button>
          <button onClick={() => void api.resolveConfirm(view.researchId, "supply_local_materials")}>
            提供本机材料补充覆盖
          </button>
          <button onClick={() => void api.resolveConfirm(view.researchId, "redefine_scope")}>
            缩小研究范围
          </button>
          <button onClick={() => void api.resolveConfirm(view.researchId, "pause_and_edit")}>暂停，我自己改</button>
        </div>
      ) : (
        <div className="decision-stack" data-testid="economic-decisions">
          {!hasEvidence && (
            <p className="evidence-required-hint">需要证据依据才能同意</p>
          )}
          <button className="cyan-button" onClick={handleApprove} disabled={!canApproveEconomic}>
            同意，开新的一版
          </button>
          <button onClick={() => void api.resolveConfirm(view.researchId, "reject_keep_logic")}>不同意，维持原逻辑继续</button>
          <button onClick={() => void api.resolveConfirm(view.researchId, "pause_and_edit")}>暂停，我自己改</button>
        </div>
      )}
    </article>
  );
}

function CompletedScreen({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "completed"}>}) {
  const [extensionHours, setExtensionHours] = useState("4");
  const [modification, setModification] = useState("");
  const [exportFeedback, setExportFeedback] = useState<
    {status: "success"; path: string} | {status: "error"; message: string} | null
  >(null);
  const [openFolderError, setOpenFolderError] = useState<string | null>(null);

  const runExport = async (kind: "strategy_pack" | "research_record") => {
    setExportFeedback(null);
    try {
      const path = await api.exportArtifact(view.researchId, kind);
      setExportFeedback({status: "success", path});
    } catch (error) {
      setExportFeedback({
        status: "error",
        message: error instanceof Error ? error.message : String(error),
      });
    }
  };
  const checks = [
    ["当前验证方法全部通过", view.eligibility.allMethodsPassed],
    ["没有待确认", view.eligibility.noPendingConfirm],
    ["重验仍然成立", view.eligibility.reverifiesPassed],
    ["时点一致性已执行且通过", view.eligibility.pitExecutedAndPassed],
  ] as const;
  const eligible = checks.every(([, passed]) => passed);
  const headline = view.resultHeadline ?? (eligible ? "研究已完成" : "研究已结束，验证未通过");
  return (
    <div className="focus completed-screen">
      <StatusPill status={view.status} />
      <p>{headline}</p>
      {view.subtitle && <p>{view.subtitle}</p>}
      {view.honestStopHint && <p className="honest-stop-hint" data-testid="honest-stop-hint">{view.honestStopHint}</p>}
      {view.canContinueIterate && (
        <button
          type="button"
          data-testid="continue-iterate"
          onClick={() => {
            const m = view.cumulativeRoundsOnWindow ?? 0;
            const threshold = view.highSuspicionRoundThreshold ?? 20;
            const first = window.confirm(
              `本数据窗口已累计 ${m} 轮。\n再加预算不放宽任何阈值，只增加偶然通过的可能性。\n确认继续迭代？`,
            );
            if (!first) return;
            let highSuspicionAcknowledged = false;
            if (m >= threshold) {
              const second = window.confirm(
                `高怀疑提示：已累计 ${m} 轮（阈值 ${threshold}）。偶然通过的可能性更高。\n确认仍要追加预算并继续？`,
              );
              if (!second) return;
              highSuspicionAcknowledged = true;
            }
            void api.continueIterate(view.researchId, {
              userConfirmed: true,
              highSuspicionAcknowledged,
            });
          }}
        >
          继续迭代
        </button>
      )}
      {view.latePassPresentation?.show && (
        <section className="late-pass-record" data-testid="late-pass-prior-failures">
          <p className="eyebrow">先前未通过轮次（验证记录）</p>
          <p>
            本数据窗口累计 {view.latePassPresentation.cumulativeRoundsOnWindow} 轮；
            结论来自第 {view.latePassPresentation.conclusionRoundId}。
          </p>
          <ul>
            {view.latePassPresentation.priorFailureRecords.map((record) => (
              <li key={record.roundId}>
                v{record.versionNumber} 第 {record.roundNumber} 轮（累计第 {record.cumulativeRoundOnWindow} 轮）：
                未通过 {record.failedGateIds.join("、") || "验证"}
                {record.paramChanges.length > 0 && (
                  <span>
                    {" "}
                    参数：
                    {record.paramChanges.map(([p, a, b]) => `${p}:${a}→${b}`).join(", ")}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
      {view.overturnedExports && <p>此前导出的策略包所依据的验证已被推翻</p>}
      {view.anomaly && <AnomalyChecklist anomaly={view.anomaly} />}
      <div className="eligibility">{checks.map(([label, passed]) => <span key={label}>{passed ? "●" : "○"} {label}</span>)}</div>
      <article className="result-card">
        <h1>{view.title}</h1>
        {view.failedVerifierIds && view.failedVerifierIds.length > 0 && (
          <p>未通过门禁：{view.failedVerifierIds.join("、")}</p>
        )}
        <button disabled={!eligible || view.status === "ended"} onClick={() => void runExport("strategy_pack")}>导出策略包</button>
        <button className="text-button" onClick={() => void api.reverify(view.researchId, view.selectedRoundId, view.selectedMethodId)}>对某一步重新验证</button>
        <button className="text-button" onClick={() => void runExport("research_record")}>导出研究记录包</button>
        {exportFeedback?.status === "success" && (
          <p className="export-feedback success" data-testid="export-success" role="status">
            已导出到 {exportFeedback.path}
            <button
              type="button"
              className="text-button"
              onClick={() => {
                void api.revealExportInFolder(exportFeedback.path).catch(async () => {
                  setOpenFolderError(`无法打开文件夹，路径已复制：${exportFeedback.path}`);
                  try {
                    await navigator.clipboard.writeText(exportFeedback.path);
                  } catch {
                    /* clipboard unavailable */
                  }
                });
              }}
            >
              打开所在文件夹
            </button>
          </p>
        )}
        {exportFeedback?.status === "error" && (
          <p className="export-feedback error" data-testid="export-error" role="alert">
            导出失败：{exportFeedback.message}
          </p>
        )}
        {openFolderError && (
          <p className="export-feedback error" data-testid="open-folder-error" role="alert">
            {openFolderError}
          </p>
        )}
        <label>
          改策略再跑
          <input value={modification} onChange={(event) => setModification(event.target.value)} placeholder="把最长研究时间改成 6 小时" />
          <button disabled={!modification.trim()} onClick={() => void (async () => {
            await api.sendDialogue(view.researchId, modification.trim());
            await api.confirmModification(view.researchId);
          })()}>确认修改并开新版</button>
        </label>
        {view.recentDialogue && view.recentDialogue.length > 0 && (
          <div className="modification-dialogue" data-testid="modification-dialogue">
            {view.recentDialogue.map((turn, index) => (
              <p className={`message ${turn.role}`} key={index}>{turn.text}</p>
            ))}
          </div>
        )}
        {view.status === "ended" && (
          <label>
            延长有效研究小时
            <input value={extensionHours} onChange={(event) => setExtensionHours(event.target.value)} inputMode="decimal" />
            <button onClick={() => void api.extendResearch(view.researchId, Number(extensionHours))}>确认延长并开新版</button>
          </label>
        )}
      </article>
    </div>
  );
}

function MethodDetail({api, method}: {api: DesktopApi; method: ValidationMethod}) {
  return (
    <section className="method-detail">
      <h1>{method.name}</h1>
      {method.category && <span className="method-category-badge">{method.category}</span>}
      <p>{method.description}</p>
      <p>
        当前冻结定义：
        <span title={method.revision}>
          {method.revision.length > 8 ? `${method.revision.slice(0, 8)}…` : method.revision}
        </span>
      </p>
      {method.usageCount != null && <p>被 {method.usageCount} 次研究用过</p>}
      {method.dimensions && method.dimensions.length > 0 && (
        <div className="scorecard-dimensions" data-testid="scorecard-dimensions">
          <p className="eyebrow">计分卡维度</p>
          <table>
            <thead>
              <tr>
                <th>类型</th>
                <th>名称</th>
                <th>阈值</th>
                <th>比较</th>
                <th>失败提示</th>
              </tr>
            </thead>
            <tbody>
              {method.dimensions.map((dim) => (
                <tr key={`${dim.kind}-${dim.name}`}>
                  <td>{dim.kind}</td>
                  <td>{dim.name}</td>
                  <td>{dim.passThreshold}</td>
                  <td>{dim.comparison}</td>
                  <td>{dim.failureDisplay}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <button className="quiet-button" onClick={() => void api.reviseMethod(method.id, method.description)}>编辑为新定义</button>
      <p>旧研究和已导出的策略包仍引用原定义。</p>
    </section>
  );
}

function MethodsScreen({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "methods"}>}) {
  const selected = view.methods.find((item) => item.id === view.selected) ?? view.methods[0];
  const [name, setName] = useState("");
  const [definition, setDefinition] = useState("");
  return (
    <div className="methods-layout">
      <aside className="method-list">
        <p>编辑得到新定义，旧研究不改写。</p>
        <div className="method-create">
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="新方法名称" />
          <input value={definition} onChange={(event) => setDefinition(event.target.value)} placeholder="方法定义" />
          <button className="quiet-button" onClick={() => {
            if (name.trim() && definition.trim()) void api.createMethod(name.trim(), definition.trim());
          }}>预先新建方法</button>
        </div>
        {view.methods.map((method) => (
          <a
            className={method.id === selected?.id ? "active" : undefined}
            href={`#/methods/${encodeURIComponent(method.id)}`}
            key={method.id}
          >
            {method.name}
            <small title={method.revision}>
              {method.revision.length > 8 ? `${method.revision.slice(0, 8)}…` : method.revision}
            </small>
            {method.usageCount != null ? <small>被 {method.usageCount} 次研究用过</small> : null}
          </a>
        ))}
      </aside>
      {selected && <MethodDetail api={api} method={selected} />}
    </div>
  );
}

type ScreenProps = AppProps & {
  pausedModificationByResearch: Record<string, string>;
  onPausedModificationChange: (researchId: string, text: string) => void;
};

function Screen({
  api,
  initialView: view,
  pausedModificationByResearch,
  onPausedModificationChange,
}: ScreenProps) {
  switch (view.kind) {
    case "research_list": return <ResearchList api={api} view={view} />;
    case "draft": return <DraftScreen api={api} view={view} />;
    case "confirm_run": return <div className="focus"><ConfirmRunCard api={api} view={view} /></div>;
    case "running":
      return (
        <RunningScreen
          api={api}
          view={view}
          modification={pausedModificationByResearch[view.researchId] ?? ""}
          onModificationChange={(text) => onPausedModificationChange(view.researchId, text)}
        />
      );
    case "awaiting_confirm": return <div className="focus"><AwaitingConfirmCard api={api} view={view} /></div>;
    case "completed": return <CompletedScreen api={api} view={view} />;
    case "methods": return <MethodsScreen api={api} view={view} />;
  }
}

export function App({
  api,
  initialView,
  initialRoute,
  pollSidecar,
  restartSidecar,
}: AppProps) {
  const [route, setRoute] = useState(() => initialRoute ?? readBrowserRoute());
  const [view, setView] = useState(initialView);
  const [syncedRoute, setSyncedRoute] = useState(() => initialRoute ?? readBrowserRoute());
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [sidecarState, setSidecarState] = useState<SidecarUiState | null>(null);
  const [pausedModificationByResearch, setPausedModificationByResearch] = useState<
    Record<string, string>
  >({});
  const onPausedModificationChange = useCallback((researchId: string, text: string) => {
    setPausedModificationByResearch((prev) => ({...prev, [researchId]: text}));
  }, []);
  const engineStopped = sidecarState?.phase === "stopped";
  const routePending = route !== syncedRoute;

  const refreshView = useCallback(async () => {
    const next = await api.fetchView(route);
    setView(next);
  }, [api, route]);

  const clearMutationError = useCallback(() => setMutationError(null), []);

  const boundApi = useMemo(
    () =>
      bindDesktopApi(api, {
        refresh: refreshView,
        onError: setMutationError,
        onSuccess: clearMutationError,
      }),
    [api, refreshView, clearMutationError],
  );

  useEffect(() => {
    clearMutationError();
  }, [route, clearMutationError]);

  useEffect(() => {
    if (!mutationError) return;
    const timer = window.setTimeout(() => clearMutationError(), 12_000);
    return () => window.clearTimeout(timer);
  }, [mutationError, clearMutationError]);

  useEffect(() => {
    const onHashChange = () => setRoute(readBrowserRoute());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  useEffect(() => {
    if (!pollSidecar) return;
    let active = true;
    const tick = () => {
      void pollSidecar()
        .then((next) => {
          if (active) setSidecarState(next);
        })
        .catch(() => {
          /* sidecar state poll failed; keep last UI state */
        });
    };
    tick();
    const timer = window.setInterval(tick, 2_000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [pollSidecar]);

  useEffect(() => {
    if (engineStopped) return;
    let active = true;
    const refresh = () => {
      void api
        .fetchView(route)
        .then((next) => {
          if (!active) return;
          setView(next);
          setSyncedRoute(route);
        })
        .catch(() => {
          /* engine unreachable; avoid unhandled rejection while polling */
        });
    };
    refresh();
    const timer = window.setInterval(refresh, 1_000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [api, route, engineStopped]);

  const handleRestartSidecar = useCallback(async () => {
    if (!restartSidecar) return;
    try {
      await restartSidecar();
      if (pollSidecar) {
        const next = await pollSidecar();
        setSidecarState(next);
      }
    } catch {
      /* restart failed; banner stays until user retries */
    }
  }, [restartSidecar, pollSidecar]);

  return (
    <NightShell view={view}>
      {mutationError && (
        <p className="mutation-error" data-testid="mutation-error" role="alert">
          <span>{mutationError}</span>
          <button
            type="button"
            className="mutation-error-dismiss"
            aria-label="关闭"
            data-testid="mutation-error-dismiss"
            onClick={clearMutationError}
          >
            ×
          </button>
        </p>
      )}
      {sidecarState?.phase === "stopped" && (
        <div className="sidecar-stopped" data-testid="sidecar-stopped" role="alert">
          <p>{sidecarState.message || "引擎已停止"}</p>
          {restartSidecar && (
            <button type="button" onClick={() => void handleRestartSidecar()}>
              重启引擎
            </button>
          )}
        </div>
      )}
      {routePending ? (
        <p className="route-loading" data-testid="route-loading">加载中…</p>
      ) : (
        <Screen
          api={boundApi}
          initialView={view}
          pausedModificationByResearch={pausedModificationByResearch}
          onPausedModificationChange={onPausedModificationChange}
        />
      )}
    </NightShell>
  );
}
