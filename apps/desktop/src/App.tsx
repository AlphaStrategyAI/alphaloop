import {FormEvent, useEffect, useState} from "react";

import type {
  AnomalyPresentation,
  DesktopApi,
  DesktopView,
  HostStatus,
  ResearchStatus,
  ValidationMethod,
} from "./contracts";
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
        <button className="quiet-button" onClick={() => void api.createDraft()}>新建研究</button>
      </header>
      {awaiting && (
        <article className="awaiting-primary" data-kind="awaiting-primary">
          <a className="awaiting-primary-body" href={`#/research/${awaiting.id}`}>
            <h2>{awaiting.title}</h2>
            <p>
              <span>{awaiting.universeLabel ?? "未锁定"}</span>
              {awaiting.createdAt ? ` · ${awaiting.createdAt}` : " · 等了 2 小时"}
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
                {row.createdAt ? ` · ${row.createdAt}` : ""}
                {row.updatedAt ? ` · ${row.updatedAt}` : ""}
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

const settingLabels = [
  ["thesis", "大致原理"],
  ["universe", "资产类别"],
  ["max_effective_hours", "最长研究时间"],
  ["round1_methods", "第一轮验证方法"],
  ["coverage_floor", "最低数据覆盖"],
] as const;

function Settings({values}: {values: Extract<DesktopView, {kind: "draft" | "confirm_run"}>["settings"]}) {
  return (
    <aside className="settings">
      <p className="eyebrow">研究设定</p>
      {settingLabels.map(([key, label]) => (
        <div data-testid="brief-slot" key={key}>
          <dt>{label}</dt>
          <dd>{values[key] || "未锁定"}</dd>
        </div>
      ))}
    </aside>
  );
}

function DraftScreen({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "draft"}>}) {
  const [message, setMessage] = useState("");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (message.trim()) void api.sendDialogue(view.researchId, message.trim());
  };
  return (
    <div className="draft-layout">
      <section className="conversation">
        <h1>新研究</h1>
        {view.messages.map((item) => <p className="message" key={item}>{item}</p>)}
        <p className="message system">我会逐项锁定原理、资产、时间、方法和覆盖底线。</p>
        <form onSubmit={submit}>
          <input value={message} onChange={(event) => setMessage(event.target.value)} placeholder="把方向说清楚，不用填表。" />
        </form>
      </section>
      <Settings values={view.settings} />
    </div>
  );
}

export function ConfirmRunCard({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "confirm_run"}>}) {
  return (
    <article className="confirm-card" data-testid="confirm-run-card">
      <h1>确认开跑</h1>
      <p>认下这次研究做什么、跑多久、拿什么验证。确认前不会自己开始。</p>
      <p>研究方法 / 建模方法 / 参数的小迭代自动做；经济逻辑改动、以及数据覆盖要跌破你认下的底线，都会停下来问你。</p>
      <p>最长研究时间只计有效研究时间，暂停和等你确认的时间不算。</p>
      <Settings values={view.settings} />
      <div className="actions">
        <button className="cyan-button" onClick={() => void api.confirmRun(view.researchId)}>确认开跑</button>
        <a href={`#/research/${view.researchId}`}>再改改</a>
      </div>
    </article>
  );
}

function RunningScreen({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "running"}>}) {
  const [modification, setModification] = useState("");
  return (
    <div className="focus running-screen">
      <header>
        <StatusPill status={view.status} />
        {view.currentAction ? ` ${view.currentAction} · ` : " "}
        第 {view.version} 版 · 有效研究 {view.effective}
        {view.remaining ? ` · 剩余 ${view.remaining}` : ""}
        {" · "}{view.coverage}
      </header>
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
          <input value={modification} onChange={(event) => setModification(event.target.value)} placeholder="说明要改的研究设定" />
          <button className="quiet-button" disabled={!modification.trim()} onClick={() => void (async () => {
            await api.sendDialogue(view.researchId, modification.trim());
            await api.confirmModification(view.researchId);
          })()}>确认修改并开新版</button>
        </>
      )}
    </div>
  );
}

export function AwaitingConfirmCard({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "awaiting_confirm"}>}) {
  const [whoPays, setWhoPays] = useState("");
  const isCoverage = view.confirmKind === "coverage";
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
        <div className="decision-stack">
          <button className="cyan-button" onClick={handleApprove}>同意，开新的一版</button>
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
  const checks = [
    ["当前验证方法全部通过", view.eligibility.allMethodsPassed],
    ["没有待确认", view.eligibility.noPendingConfirm],
    ["重验仍然成立", view.eligibility.reverifiesPassed],
    ["时点一致性已执行且通过", view.eligibility.pitExecutedAndPassed],
  ] as const;
  const eligible = checks.every(([, passed]) => passed);
  return (
    <div className="focus completed-screen">
      <StatusPill status={view.status} />
      <p>alphaloop 到这里结束，不提供执行入口。</p>
      {view.overturnedExports && <p>此前导出的策略包所依据的验证已被推翻</p>}
      {view.anomaly && <AnomalyChecklist anomaly={view.anomaly} />}
      <div className="eligibility">{checks.map(([label, passed]) => <span key={label}>{passed ? "●" : "○"} {label}</span>)}</div>
      <article className="result-card">
        <h1>{view.title}</h1>
        <p>美股 · 股票 · 经过市场基准和全部额外验证</p>
        <button disabled={!eligible || view.status === "ended"} onClick={() => void api.exportArtifact(view.researchId, "strategy_pack")}>导出策略包</button>
        <button className="text-button" onClick={() => void api.reverify(view.researchId, view.selectedRoundId, view.selectedMethodId)}>对某一步重新验证</button>
        <button className="text-button" onClick={() => void api.exportArtifact(view.researchId, "research_record")}>导出研究记录包</button>
        <label>
          改策略再跑
          <input value={modification} onChange={(event) => setModification(event.target.value)} placeholder="说明要改的研究设定" />
          <button disabled={!modification.trim()} onClick={() => void (async () => {
            await api.sendDialogue(view.researchId, modification.trim());
            await api.confirmModification(view.researchId);
          })()}>确认修改并开新版</button>
        </label>
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
      <p>当前冻结定义：{method.revision}</p>
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
          <a href={`#/methods/${method.id}`} key={method.id}>
            {method.name}
            <small>{method.revision}</small>
            {method.usageCount != null ? <small>被 {method.usageCount} 次研究用过</small> : null}
          </a>
        ))}
      </aside>
      {selected && <MethodDetail api={api} method={selected} />}
    </div>
  );
}

function Screen({api, initialView: view}: AppProps) {
  switch (view.kind) {
    case "research_list": return <ResearchList api={api} view={view} />;
    case "draft": return <DraftScreen api={api} view={view} />;
    case "confirm_run": return <div className="focus"><ConfirmRunCard api={api} view={view} /></div>;
    case "running": return <RunningScreen api={api} view={view} />;
    case "awaiting_confirm": return <div className="focus"><AwaitingConfirmCard api={api} view={view} /></div>;
    case "completed": return <CompletedScreen api={api} view={view} />;
    case "methods": return <MethodsScreen api={api} view={view} />;
  }
}

export function App({api, initialView}: AppProps) {
  const [view, setView] = useState(initialView);
  useEffect(() => {
    let active = true;
    const refresh = () => {
      void api.fetchView(routeFor(view)).then((next) => {
        if (active) setView(next);
      });
    };
    const timer = window.setInterval(refresh, 1_000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [api, view]);
  return <NightShell view={view}><Screen api={api} initialView={view} /></NightShell>;
}
