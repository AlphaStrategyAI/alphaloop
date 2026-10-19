import {FormEvent, useCallback, useEffect, useMemo, useRef, useState} from "react";

import {bindDesktopApi} from "./api-bind";
import {InAppConfirmOverlay, type InAppConfirmRequest} from "./InAppConfirm";

import type {
  AnomalyPresentation,
  BriefSlotName,
  DesktopApi,
  DesktopView,
  HostStatus,
  PitDetail,
  ResearchListDisplayStatus,
  ResearchStatus,
  SidecarUiState,
  ValidationMethod,
} from "./contracts";
import {formatResearchTimestamp} from "./format";
import {readBrowserRoute, routeFromHash} from "./routing";
import "./night.css";
import "./tech-pulse.css";
import {BrandMark} from "./BrandMark";
import {parseEffectiveQuotaFromView} from "./effectiveQuota";
import {completedShowsFailedTone, viewContentFailedTone} from "./completedFailedTone";
import {listRowStatusLabel} from "./listStatusDisplay";
import {railStatusLabel} from "./railStatus";
import {useRunStartRitual} from "./useRunStartRitual";

const CN_TICKER_IN_PROSE = /(\d{6}\.(?:SH|SZ|BJ))/g;

function renderSettingsProse(text: string) {
  const parts: Array<string | {token: string; key: string}> = [];
  let last = 0;
  for (const match of text.matchAll(CN_TICKER_IN_PROSE)) {
    const index = match.index ?? 0;
    if (index > last) {
      parts.push(text.slice(last, index));
    }
    parts.push({token: match[1], key: `${index}-${match[1]}`});
    last = index + match[1].length;
  }
  if (last < text.length) {
    parts.push(text.slice(last));
  }
  if (parts.length === 0) {
    return text;
  }
  return parts.map((part) =>
    typeof part === "string" ? (
      part
    ) : (
      <span className="cn-ticker-nowrap" key={part.key}>{part.token}</span>
    ),
  );
}

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

export function routeFor(view: DesktopView): string {
  if (view.kind === "research_list") return "#/research";
  if (view.kind === "methods") return `#/methods${view.selected ? `/${view.selected}` : ""}`;
  if (view.kind === "glossary") return "#/glossary";
  return `#/research/${view.researchId}`;
}

function engineStatusLabel(sidecar: SidecarUiState | null | undefined): string {
  if (!sidecar) return "引擎：检测中";
  if (sidecar.phase === "stopped") return "引擎：已停止";
  if (sidecar.phase === "restarting") return "引擎：重启中";
  return "引擎：运行中";
}

function railSection(route: string): "research" | "methods" | "glossary" {
  if (route.startsWith("#/glossary")) return "glossary";
  if (route.startsWith("#/methods")) return "methods";
  return "research";
}

function routeFailureMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) return error.message;
  if (typeof error === "string" && error.trim()) return error;
  return "无法加载这个页面";
}

function NightShell({
  view,
  route,
  children,
  sidecarState,
  runStartRitual,
}: {
  view: DesktopView;
  route: string;
  children: React.ReactNode;
  sidecarState?: SidecarUiState | null;
  runStartRitual?: boolean;
}) {
  const section = railSection(route);
  const fetchingQuotes = Boolean(view.marketDataProgress && view.marketDataProgress.total > 0);
  const hostKey: HostStatus = fetchingQuotes
    ? "running"
    : (view.hostStatus ?? (
      view.kind === "awaiting_confirm" ? "awaiting_confirm" :
      view.kind === "running" ? "running" :
      view.kind === "completed" ? "completed" : "idle"
    ));
  const railLabel = fetchingQuotes ? "运行中" : railStatusLabel(view);
  const engineLine = engineStatusLabel(sidecarState);
  const statusTitle = railLabel
    ? `${railLabel} · ${engineLine}`
    : engineLine;
  const failedTone = viewContentFailedTone(view);
  const atmosphereTone =
    view.kind === "running"
      ? "running"
      : view.kind === "confirm_run"
        ? "confirm"
        : failedTone
          ? "failed"
          : view.kind === "completed"
            ? "success"
            : undefined;
  return (
    <main className="night-shell tech-pulse-shell" data-testid="night-shell" data-view={view.kind}>
      <aside className="rail" data-testid="rail">
        <div className="rail-center">
          <BrandMark />
          <nav aria-label="主导航">
            <a className={section === "research" ? "active" : ""} href="#/research">研究</a>
            <a className={section === "methods" ? "active" : ""} href="#/methods">方法库</a>
            <a className={section === "glossary" ? "active" : ""} href="#/glossary">术语</a>
          </nav>
        </div>
        {railLabel ? (
          <div className={`host-status rail-status ${hostKey}`} title={statusTitle} data-testid="host-status">
            <span className="host-status-line" data-testid="rail-status-label">
              <span className="host-status-dot" aria-hidden />
              {railLabel}
            </span>
          </div>
        ) : null}
      </aside>
      <section
        className={`content ${view.kind} tech-pulse-content${failedTone ? " tech-pulse-failed-tone" : ""}${runStartRitual ? " run-start-ritual" : ""}`}
        data-run-start-ritual={runStartRitual ? "active" : undefined}
      >
        <div
          className="tech-pulse-atmosphere"
          data-testid="tech-pulse-atmosphere"
          data-atmosphere-tone={atmosphereTone}
          aria-hidden
        />
        {view.marketDataProgress && view.marketDataProgress.total > 0 ? (
          <p data-testid="market-data-progress">
            正在取行情 {view.marketDataProgress.done}/{view.marketDataProgress.total}
          </p>
        ) : null}
        {view.thesisChangeHint && <p className="thesis-hint">{view.thesisChangeHint}</p>}
        {children}
      </section>
    </main>
  );
}

function StatusPill({status}: {status: ResearchListDisplayStatus}) {
  return (
    <span className={`status-pill status-pill-dot ${status}`} data-testid="list-status-pill">
      <span className="pill-dot" aria-hidden />
      {listRowStatusLabel(status)}
    </span>
  );
}

const deleteWarning =
  "删除会永久移除对话、版本、迭代与验证记录及导出资格；已导出的本机文件不受影响。";

function ResearchList({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "research_list"}>}) {
  const [deleteConfirm, setDeleteConfirm] = useState<InAppConfirmRequest | null>(null);
  const awaiting = view.awaiting;
  const confirmPinned = view.rows.find((row) => row.status === "confirm_run");
  const rows = view.rows.filter((row) => row.status !== "confirm_run");
  const askDelete = (researchId: string) => {
    setDeleteConfirm({
      title: "确认删除研究",
      body: deleteWarning,
      confirmLabel: "删除",
      onConfirm: () => {
        void api.deleteResearch(researchId);
        setDeleteConfirm(null);
      },
    });
  };
  return (
    <div className="browse list-screen">
      <InAppConfirmOverlay request={deleteConfirm} onClose={() => setDeleteConfirm(null)} />
      <header className="list-header">
        <div>
          <p className="tech-pulse-eyebrow">研究</p>
          <h1 className="list-title">本机工坊</h1>
          <p className="list-tagline">一条对话，一次研究。等你确认的会排在最上面。</p>
        </div>
        <button
          className="quiet-button list-new-research"
          data-testid="new-research-button"
          onClick={() => {
            void api.createDraft().then((id) => {
              window.location.hash = `#/research/${id}`;
            });
          }}
        >
          <span className="list-new-research-icon" aria-hidden>+</span>
          新建研究
        </button>
      </header>
      {awaiting && (
        <article className="awaiting-primary list-pinned-card" data-kind="awaiting-primary">
          <div className="list-pinned-head">
            <StatusPill status="awaiting_confirm" />
            <span className="list-pinned-meta">额度已冻结 · 等你拍板</span>
          </div>
          <a className="awaiting-primary-body" href={`#/research/${awaiting.id}`}>
            <h2>{awaiting.title}</h2>
            <p>
              <span>{awaiting.universeLabel ?? "未锁定"}</span>
              {awaiting.createdAt
                ? ` · ${formatResearchTimestamp(awaiting.createdAt)}`
                : ""}
            </p>
          </a>
          <div className="list-pinned-actions">
            <a className="cyan-button list-open-confirm" href={`#/research/${awaiting.id}`}>
              打开确认卡
            </a>
            <span className="list-pinned-hint">点击整卡也可进入</span>
            <button type="button" className="text-button" onClick={() => askDelete(awaiting.id)}>
              删除
            </button>
          </div>
        </article>
      )}
      {confirmPinned && (
        <article
          className="awaiting-primary list-pinned-card list-pinned-confirm"
          data-kind="confirm-pinned"
          data-testid="confirm-pinned-card"
        >
          <div className="list-pinned-head">
            <StatusPill status="confirm_run" />
          </div>
          <a className="awaiting-primary-body" href={`#/research/${confirmPinned.id}`}>
            <h2>{confirmPinned.title}</h2>
            <p>{confirmPinned.universeLabel ?? "五项设定已齐"}</p>
          </a>
          <div className="list-pinned-actions">
            <a className="cyan-button list-open-confirm" href={`#/research/${confirmPinned.id}`}>
              打开确认卡
            </a>
          </div>
        </article>
      )}
      <div className="research-rows">
        {rows.map((row) => (
          <article
            className={`research-row${row.status === "ended" ? " research-row--failed" : ""}`}
            data-testid="research-row"
            key={row.id}
          >
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
              <button onClick={() => askDelete(row.id)}>删除</button>
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
        <div className="settings-row" data-testid={`brief-slot-${key}`} key={key}>
          <dt className="settings-label">{label}</dt>
          <dd
            className={`settings-value${key === "thesis" ? " settings-value-prose" : ""}`}
            data-testid={key === "thesis" ? "brief-thesis-value" : undefined}
          >
            {key === "thesis"
              ? values.thesis
                ? renderSettingsProse(values.thesis)
                : "未锁定"
              : values[key] || "未锁定"}
            {key === "universe" && values.universe_symbol_chips && values.universe_symbol_chips.length > 0 ? (
              <span className="universe-symbol-chips" data-testid="universe-symbol-chips">
                {values.universe_symbol_chips.map((symbol) => (
                  <span className="symbol-chip" key={symbol}>{symbol}</span>
                ))}
              </span>
            ) : key === "universe" && values.universe_symbols ? (
              <span className="universe-symbols" data-testid="universe-symbols">
                {values.universe_symbols}
              </span>
            ) : null}
          </dd>
          {onEditSlot ? (
            <button
              className="text-button slot-edit settings-action"
              type="button"
              data-testid={`edit-slot-${key}`}
              onClick={() => onEditSlot(key)}
            >
              改一改
            </button>
          ) : (
            <span className="settings-action" />
          )}
        </div>
      ))}
    </aside>
  );
}

function DialoguePanel({
  researchId,
  api,
  dialogue,
  chatEnabled = true,
  title = "新研究",
}: {
  researchId: string;
  api: DesktopApi;
  dialogue: readonly {role: "user" | "assistant"; text: string}[];
  chatEnabled?: boolean;
  title?: string;
}) {
  const [message, setMessage] = useState("");
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const text = message.trim();
    if (!text || !chatEnabled) return;
    try {
      await api.sendDialogue(researchId, text);
      setMessage("");
    } catch {
      /* mutation error banner */
    }
  };
  useEffect(() => {
    const node = document.querySelector(".conversation");
    if (node) {
      node.scrollTop = node.scrollHeight;
    }
  }, [dialogue.length]);

  return (
    <section className="conversation">
      <h1>{title}</h1>
      <p className="message assistant system" data-testid="dialogue-system-intro">
        我会逐项问清原理、资产、时间、方法和覆盖底线；齐全后进入确认开跑。
      </p>
      {dialogue.map((turn, index) => (
        <p className={`message ${turn.role}`} data-testid="dialogue-turn" key={index}>
          {turn.text}
        </p>
      ))}
      {chatEnabled && (
        <form onSubmit={submit}>
          <input
            data-testid="dialogue-input"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="把方向说清楚，不用填表。"
          />
        </form>
      )}
    </section>
  );
}

function DraftScreen({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "draft"}>}) {
  return (
    <div className="draft-layout">
      <DialoguePanel
        api={api}
        researchId={view.researchId}
        dialogue={view.dialogue}
        chatEnabled
      />
      <Settings values={view.settings} />
    </div>
  );
}

export function ConfirmRunScreen({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "confirm_run"}>}) {
  return (
    <div className="draft-layout confirm-run-layout">
      <DialoguePanel
        api={api}
        researchId={view.researchId}
        dialogue={view.dialogue}
        chatEnabled={view.chatEnabled ?? false}
        title="确认开跑"
      />
      <ConfirmRunCard api={api} view={view} />
    </div>
  );
}

export function ConfirmRunCard({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "confirm_run"}>}) {
  const editSlot = (slot: BriefSlotName) => {
    void api.unlockBrief(view.researchId, slot).then(() => {
      requestAnimationFrame(() => {
        const node = document.querySelector(".conversation");
        if (node && "scrollTo" in node && typeof node.scrollTo === "function") {
          node.scrollTo({top: node.scrollHeight, behavior: "smooth"});
        } else if (node) {
          node.scrollTop = node.scrollHeight;
        }
      });
    });
  };
  const [symbolsOpen, setSymbolsOpen] = useState(false);
  const [starting, setStarting] = useState(false);
  const startingRef = useRef(false);
  const sel = view.symbolSelection;
  const returnToDraft = () => {
    void api.unlockBrief(view.researchId);
  };
  const startRun = () => {
    if (startingRef.current) return;
    startingRef.current = true;
    setStarting(true);
    void api
      .confirmRun(view.researchId)
      .catch(() => {
        /* bindDesktopApi already recorded the message */
      })
      .finally(() => {
        startingRef.current = false;
        setStarting(false);
      });
  };
  return (
    <article className="confirm-card tech-pulse-card confirm-card-layout" data-testid="confirm-run-card">
      <p className="tech-pulse-eyebrow">Confirm to run</p>
      <h1>确认开跑</h1>
      <p className="confirm-lead">
        五项设定已锁定。点开跑后进入本机研究；「再修改」回草稿并解锁设定。
      </p>
      <details className="confirm-policy-details" data-testid="confirm-policy-details">
        <summary>运行与锁定说明</summary>
        <div className="confirm-policy-body">
          <p>认下这次研究做什么、跑多久、拿什么验证。确认前不会自己开始。</p>
          <p>研究方法 / 建模方法 / 参数的小迭代自动做；经济逻辑改动、以及数据覆盖要跌破你认下的底线，都会停下来问你。</p>
          <p>最长研究时间只计有效研究时间，暂停和等你确认的时间不算。</p>
        </div>
      </details>
      {view.meanReversionOnlyNotice && (
        <p className="confirm-lead" data-testid="mean-reversion-only-notice">
          {view.meanReversionOnlyNotice}
        </p>
      )}
      {view.confirmDataNotice && (
        <p className="confirm-data-notice" data-testid="confirm-data-notice" role="alert">
          {view.confirmDataNotice}
        </p>
      )}
      {sel && (
        <section className="confirm-data-panel" data-testid="symbol-selection">
          <div className="confirm-data-panel-head">
            <p className="confirm-data-panel-title">将使用的数据</p>
            <button
              type="button"
              className="text-button confirm-data-expand"
              data-testid="toggle-symbol-list"
              onClick={() => setSymbolsOpen((open) => !open)}
            >
              {symbolsOpen ? "收起看全表" : "展开看全表"}
            </button>
          </div>
          <p className="confirm-data-summary" data-testid="symbol-selection-summary">
            {sel.summaryLine ??
              `标的 ${sel.count} 只 · 清单 ${sel.listName} · 版本 ${sel.listVersion}${
                sel.isDefaultPool || sel.source === "default_pool"
                  ? " · 默认标的池"
                  : ` · ${sel.overrideNote ?? "用户指定池"}`
              }`}
          </p>
          {sel.listNote ? (
            <p className="confirm-data-meta" data-testid="symbol-selection-note">{sel.listNote}</p>
          ) : null}
          {sel.listNote && sel.listVersion ? (
            <p className="confirm-data-footnote" data-testid="symbol-selection-version">
              版本 {sel.listVersion}
            </p>
          ) : null}
          <p className="confirm-data-meta">
            数据 {sel.dataStart} → {sel.dataEnd} · 日频 · 来源：{sel.dataSource}
          </p>
          <p className="confirm-data-footnote">确认开跑前锁定清单版本与数据区间。</p>
          {sel.shrinkNote && (
            <p className="pool-shrink-note" data-testid="pool-shrink-note">{sel.shrinkNote}</p>
          )}
          {symbolsOpen && (
            <ul className="symbol-ticker-list" data-testid="symbol-ticker-list">
              {sel.symbols.map((symbol) => (
                <li key={symbol}>{symbol}</li>
              ))}
            </ul>
          )}
        </section>
      )}
      <Settings values={view.settings} onEditSlot={editSlot} />
      <div className="actions confirm-actions">
        <button
          className="cyan-button"
          data-testid="confirm-run-start"
          disabled={starting}
          aria-busy={starting}
          onClick={startRun}
        >
          {starting ? "开跑中…" : "开跑"}
        </button>
        <button type="button" className="quiet-button" data-testid="confirm-return-draft" onClick={returnToDraft}>
          再修改
        </button>
      </div>
    </article>
  );
}

function RunningScreen({
  api,
  view,
  modification,
  onModificationChange,
  runStartRitual,
}: {
  api: DesktopApi;
  view: Extract<DesktopView, {kind: "running"}>;
  modification: string;
  onModificationChange: (text: string) => void;
  runStartRitual?: boolean;
}) {
  const quota = parseEffectiveQuotaFromView(view.effective, view.remaining);
  const stageLabel =
    view.currentAction && view.currentAction !== "idle" ? view.currentAction : null;
  return (
    <div
      className={`focus running-screen${runStartRitual ? " run-start-ritual-running" : ""}`}
      data-testid="running-screen"
      data-run-start-ritual={runStartRitual ? "active" : undefined}
    >
      <div className="running-hero">
        <div className="version-orbit" data-testid="version-orbit">
          <span className="orbit-version">v{view.version}</span>
          {stageLabel ? <span className="orbit-stage">{stageLabel}</span> : null}
        </div>
        <div>
          <h1>运行中</h1>
          <p className="running-sub">
            第 {view.version} 版
            {view.currentAction && view.currentAction !== "idle" ? ` · ${view.currentAction}` : ""}
          </p>
          {view.coverage && <p className="running-accent">{view.coverage}</p>}
        </div>
        {view.status === "running" ? (
          <button className="quiet-button" type="button" onClick={() => void api.pauseResearch(view.researchId)}>
            暂停
          </button>
        ) : (
          <span />
        )}
      </div>
      {quota && (
        <div className="effective-quota" data-testid="effective-quota-progress">
          <div className="effective-quota-labels">
            <span>有效研究额度</span>
            <span>{quota.usedLabel} / {quota.totalLabel}</span>
          </div>
          <div
            className="effective-quota-track"
            data-testid="effective-quota-track"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(quota.ratio * 100)}
          >
            <div className="effective-quota-fill" style={{width: `${quota.ratio * 100}%`}} />
          </div>
        </div>
      )}
      {view.versionOpenedNotice && (
        <p className="version-opened-banner" data-testid="version-opened-banner" role="status">
          {view.versionOpenedNotice}
        </p>
      )}
      <header className="running-header">
        <StatusPill status={view.status} />
        {view.currentAction && view.currentAction !== "idle"
          ? ` ${view.currentAction} · `
          : " "}
        第 {view.version} 版 · 有效研究 {view.effective}
        {view.remaining ? ` · 剩余 ${view.remaining}` : ""}
        {" · "}{view.coverage}
        {view.workbenchHeaderSummary ? ` · ${view.workbenchHeaderSummary}` : ""}
        {view.versionTrialLabel ? ` · ${view.versionTrialLabel}` : ""}
        {!view.workbenchHeaderSummary && view.windowCumulativeLabel
          ? ` · ${view.windowCumulativeLabel}`
          : ""}
      </header>
      {view.effectiveTimeHint && (
        <p className="effective-time-hint" data-testid="effective-time-hint">
          {view.effectiveTimeHint}
        </p>
      )}
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
            </div>
            <div className="round-impl">
              <p className="eyebrow">实现与参数</p>
              {round.implementationDelta.modelChangesDisplay ? (
                <p>{round.implementationDelta.modelChangesDisplay}</p>
              ) : (
                round.implementationDelta.modelChanges.length > 0 && (
                  <p>模型变更：{round.implementationDelta.modelChanges.join("、")}</p>
                )
              )}
              {round.logicStatement.changedFromPrior && round.logicStatement.changeDescription && (
                <p className="change-note">{round.logicStatement.changeDescription}</p>
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
      {view.status === "running" && (
        <p className="running-modify-hint" data-testid="running-modify-hint">
          运行中不能改策略，请先暂停。
        </p>
      )}
      {view.status === "running" ? null : (
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
    <article className="awaiting-card tech-pulse-card" data-testid="awaiting-confirm-card">
      <p className="tech-pulse-eyebrow">等待确认</p>
      <p className="eyebrow">第 {view.version} 版 · 这段时间不计入额度</p>
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

function ExportOutcomeMessages({
  exportFeedback,
  openFolderError,
  onReveal,
}: {
  exportFeedback: {status: "success"; path: string} | {status: "error"; message: string} | null;
  openFolderError: string | null;
  onReveal: (path: string) => void;
}) {
  return (
    <div className="export-outcome-messages" data-testid="export-outcome-messages">
      {exportFeedback?.status === "success" && (
        <p className="export-feedback success" data-testid="export-success" role="status">
          已导出到 {exportFeedback.path}
          <button
            type="button"
            className="text-button"
            data-testid="reveal-export-folder"
            onClick={() => onReveal(exportFeedback.path)}
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
    </div>
  );
}

function ExportFeedbackBlock({
  exportFeedback,
  openFolderError,
  onExport,
  onReveal,
}: {
  exportFeedback: {status: "success"; path: string} | {status: "error"; message: string} | null;
  openFolderError: string | null;
  onExport: () => void;
  onReveal: (path: string) => void;
}) {
  return (
    <div className="export-actions" data-testid="export-research-record-block">
      <button
        type="button"
        className="cyan-button"
        data-testid="export-research-record"
        onClick={onExport}
      >
        导出研究记录包
      </button>
      {exportFeedback?.status === "success" && (
        <p className="export-feedback success" data-testid="export-success" role="status">
          已导出到 {exportFeedback.path}
          <button
            type="button"
            className="text-button"
            data-testid="reveal-export-folder"
            onClick={() => onReveal(exportFeedback.path)}
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
    </div>
  );
}

function pitGateLabel(detail: PitDetail | null | undefined, passed: boolean): string {
  if (passed) return "时点一致性已执行且通过";
  if (!detail || detail.executed === false) return "时点一致性未执行";
  return "时点一致性未通过";
}

function pitFailureCopy(detail: PitDetail | null | undefined): string | null {
  if (!detail || detail.passed) return null;
  if (detail.executed === false) {
    return "时点一致性未执行，暂不能导出策略包。";
  }
  const count = detail.violationCount ?? 0;
  const first = detail.firstViolation;
  if (!first) {
    return "时点一致性未通过，暂不能导出策略包。";
  }
  const doi = first.materialId.startsWith("doi:") ? first.materialId.slice(4) : "";
  const title = first.title || first.text || first.materialId || "未命名资料";
  const yearNote = first.precision === "year" ? "（仅知年份，按年末计）" : "";
  const when = first.publishedAt
    ? `发布日 ${first.publishedAt}${yearNote}`
    : "没有发布日";
  const cutoff = detail.backtestCutoff ? `回测截止日 ${detail.backtestCutoff}` : "没有回测截止日";
  const doiPart = doi ? `（DOI ${doi}）` : "";
  return `时点一致性未通过，暂不能导出策略包。共 ${count} 条违规。第一条：${title}${doiPart}，${when}，${cutoff}。`;
}

function CompletedScreen({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "completed"}>}) {
  const [extensionHours, setExtensionHours] = useState("4");
  const [modification, setModification] = useState("");
  const [iterateConfirm, setIterateConfirm] = useState<InAppConfirmRequest | null>(null);
  const [reverifyRoundId, setReverifyRoundId] = useState(view.selectedRoundId);
  const [reverifyMethodId, setReverifyMethodId] = useState(view.selectedMethodId);
  const [reverifyBusy, setReverifyBusy] = useState(false);
  const [reverifyError, setReverifyError] = useState<string | null>(null);
  const [exportFeedback, setExportFeedback] = useState<
    {status: "success"; path: string} | {status: "error"; message: string} | null
  >(null);
  const [openFolderError, setOpenFolderError] = useState<string | null>(null);

  useEffect(() => {
    setReverifyRoundId(view.selectedRoundId);
    setReverifyMethodId(view.selectedMethodId);
  }, [view.selectedRoundId, view.selectedMethodId]);

  const runExport = async (kind: "strategy_pack" | "research_record") => {
    setExportFeedback(null);
    setOpenFolderError(null);
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
  const revealExportFolder = (path: string) => {
    void api.revealExportInFolder(path).catch(async () => {
      setOpenFolderError(`无法打开文件夹，路径已复制：${path}`);
      try {
        await navigator.clipboard.writeText(path);
      } catch {
        /* clipboard unavailable */
      }
    });
  };
  const pitLabel = pitGateLabel(view.pitDetail, view.eligibility.pitExecutedAndPassed);
  const checks = [
    ["当前验证方法全部通过", view.eligibility.allMethodsPassed],
    ["没有待确认", view.eligibility.noPendingConfirm],
    ["重验仍然成立", view.eligibility.reverifiesPassed],
    [pitLabel, view.eligibility.pitExecutedAndPassed],
  ] as const;
  const pitFailure = pitFailureCopy(view.pitDetail);
  const eligible = checks.every(([, passed]) => passed);
  const researchRecordExportPrimary = completedShowsFailedTone(view);
  const headline = view.resultHeadline ?? (eligible ? "研究已完成" : "研究已结束，验证未通过");
  const gatesInSubtitle = Boolean(view.subtitle?.includes("未通过门禁"));
  const showFailedGateLine =
    view.failedVerifierIds &&
    view.failedVerifierIds.length > 0 &&
    !gatesInSubtitle;
  const reverifyRounds = view.reverifyOptions?.rounds ?? [];
  const methodsForRound =
    reverifyRounds.find((item) => item.roundId === reverifyRoundId)?.methods ?? [];
  const runReverify = async () => {
    if (!reverifyRoundId || !reverifyMethodId) {
      setReverifyError("请选择轮次与验证方法");
      return;
    }
    setReverifyBusy(true);
    setReverifyError(null);
    try {
      await api.reverify(view.researchId, reverifyRoundId, reverifyMethodId);
    } catch (error) {
      setReverifyError(error instanceof Error ? error.message : String(error));
    } finally {
      setReverifyBusy(false);
    }
  };

  return (
    <div
      className={`focus completed-screen${researchRecordExportPrimary ? " tech-pulse-failed-tone" : " tech-pulse-success-tone"}`}
      data-testid="completed-screen"
    >
      <InAppConfirmOverlay request={iterateConfirm} onClose={() => setIterateConfirm(null)} />
      <article
        className={`completed-focus-card tech-pulse-card${eligible ? " completed-focus-card--success" : " completed-focus-card--failed"}`}
        data-testid="completed-focus-card"
      >
        {eligible ? (
          <p className="export-ready-eyebrow" data-testid="export-ready-eyebrow">
            Export ready · 四关全绿
          </p>
        ) : (
          <p className="failed-eyebrow" data-testid="completed-failed-eyebrow">
            COMPLETED · 未通过门禁
          </p>
        )}
        <h1 data-testid="completed-focus-title">{eligible ? "已完成" : "已完成"}</h1>
        <p className="completed-focus-headline">{headline}</p>
        {view.meanReversionOnlyNotice && (
          <p className="confirm-lead" data-testid="mean-reversion-only-notice">
            {view.meanReversionOnlyNotice}
          </p>
        )}
        {view.subtitle && <p className="completed-focus-subtitle">{view.subtitle}</p>}
        {view.honestStopHint && (
          <p className="honest-stop-hint" data-testid="honest-stop-hint">{view.honestStopHint}</p>
        )}
        <div className="eligibility eligibility-pills" data-testid="completed-gate-pills">
          {checks.map(([label, passed]) => (
            <span className={`gate-pill ${passed ? "gate-pill--ok" : "gate-pill--fail"}`} key={label}>
              {passed ? "●" : "○"} {label}
            </span>
          ))}
        </div>
        {view.pitDetail && (view.pitDetail.scope || view.pitDetail.note || pitFailure) && (
          <p className="materials-note" data-testid="pit-detail">
            {pitFailure ? <span data-testid="pit-failure-reason">{pitFailure}</span> : null}
            {view.pitDetail.note ? `${view.pitDetail.note}。` : ""}
            {view.pitDetail.executed ? (
              <>
                已采信 {view.pitDetail.evidenceUsed ?? 0} 份有发布日的资料
                {(view.pitDetail.undatedExcluded?.length ?? 0) > 0
                  ? `，已浏览未采信 ${view.pitDetail.undatedExcluded?.length} 份无日期资料`
                  : ""}
                。{view.pitDetail.scope}
              </>
            ) : null}
          </p>
        )}
        <p className="workbench-summary completed-meta" data-testid="completed-workbench-header">
          第 {view.version ?? 1} 版
          {view.researchCumulativeLabel ? ` · ${view.researchCumulativeLabel}` : ""}
          {view.workbenchHeaderSummary ? ` · ${view.workbenchHeaderSummary}` : ""}
          {view.windowCumulativeLabel && view.windowCumulativeLabel !== view.workbenchHeaderSummary
            ? ` · ${view.windowCumulativeLabel}`
            : ""}
          {view.effective ? ` · 有效研究 ${view.effective}` : ""}
          {view.remaining ? ` · 剩余 ${view.remaining}` : ""}
        </p>
        {showFailedGateLine && (
          <p className="failed-gates-line" data-testid="failed-gates-line">
            未通过门禁：{view.failedVerifierIds!.join("、")}
          </p>
        )}
        {eligible && view.title && (
          <section className="completed-strategy-summary">
            <h2>{view.title}</h2>
          </section>
        )}
        <div className="completed-export-actions" data-testid="completed-export-actions">
          {eligible ? (
            <button
              type="button"
              className="cyan-button"
              data-testid="export-strategy-pack-primary"
              disabled={view.status === "ended"}
              onClick={() => void runExport("strategy_pack")}
            >
              导出策略包
            </button>
          ) : (
            <>
              <button
                type="button"
                className="stop-button-primary"
                data-testid="export-research-record-primary"
                onClick={() => void runExport("research_record")}
              >
                导出研究记录
              </button>
              <button type="button" className="quiet-button" disabled data-testid="export-strategy-pack-locked">
                导出策略包（未解锁）
              </button>
            </>
          )}
        </div>
        {!eligible && (
          <ExportOutcomeMessages
            exportFeedback={exportFeedback}
            openFolderError={openFolderError}
            onReveal={revealExportFolder}
          />
        )}
        {!eligible && view.exportBlockerMessages && view.exportBlockerMessages.length > 0 && (
          <ul className="export-blockers" data-testid="export-blockers">
            {view.exportBlockerMessages.map((message) => (
              <li key={message}>{message}</li>
            ))}
          </ul>
        )}
        {!eligible && (
          <details className="completed-tools-details" data-testid="completed-tools-details">
            <summary>重新验证与改策略再跑</summary>
            <div className="reverify-panel" data-testid="reverify-panel">
              <p className="eyebrow">对某一步重新验证</p>
              <label>
                轮次
                <select
                  value={reverifyRoundId}
                  onChange={(event) => {
                    const nextRound = event.target.value;
                    setReverifyRoundId(nextRound);
                    const round = reverifyRounds.find((item) => item.roundId === nextRound);
                    const stillThere = round?.methods.some(
                      (item) => item.methodId === reverifyMethodId,
                    );
                    if (round && !stillThere && round.methods[0]) {
                      setReverifyMethodId(round.methods[0].methodId);
                    }
                  }}
                  data-testid="reverify-round-select"
                >
                  {reverifyRounds.map((round) => (
                    <option key={round.roundId} value={round.roundId}>{round.roundLabel}</option>
                  ))}
                </select>
              </label>
              <label>
                验证方法
                <select
                  value={reverifyMethodId}
                  onChange={(event) => setReverifyMethodId(event.target.value)}
                  data-testid="reverify-method-select"
                >
                  {methodsForRound.map((method) => (
                    <option key={method.methodId} value={method.methodId}>
                      {method.methodLabel}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                className="text-button"
                disabled={reverifyBusy}
                aria-busy={reverifyBusy}
                data-testid="reverify-submit"
                onClick={() => void runReverify()}
              >
                {reverifyBusy ? "重新验证中…" : "执行重新验证"}
              </button>
              {view.lastReverification && (
                <p
                  className={
                    view.lastReverification.passed
                      ? "reverify-result"
                      : "reverify-result reverify-result--fail"
                  }
                  data-testid="reverify-result"
                  role="status"
                >
                  {view.lastReverification.userMessage ??
                    `最近重验：${view.lastReverification.methodLabel}（${
                      view.lastReverification.passed ? "通过" : "未通过"
                    }）`}
                </p>
              )}
              {reverifyError && (
                <p className="reverify-error" data-testid="reverify-error" role="alert">{reverifyError}</p>
              )}
            </div>
            <div className="stacked-field modify-rerun-field">
              <span className="field-label">改策略再跑</span>
              <input
                value={modification}
                onChange={(event) => setModification(event.target.value)}
                placeholder="例如：把最长研究时间改成 6 小时"
                aria-label="改策略再跑"
              />
              <button
                disabled={!modification.trim()}
                data-testid="confirm-modification-button"
                onClick={() => void (async () => {
                  await api.sendDialogue(view.researchId, modification.trim());
                  await api.confirmModification(view.researchId);
                })()}
              >
                确认修改并开新版
              </button>
              {!modification.trim() && (
                <p className="field-hint" data-testid="modify-empty-hint">
                  请先在上面的输入框说明要改什么，再点「确认修改并开新版」。
                </p>
              )}
            </div>
          </details>
        )}
      {view.symbolSelection && (
        <section className="materials-note completed-data-window" data-testid="completed-symbol-selection">
          <p className="eyebrow">标的与数据窗口</p>
          <p data-testid="completed-symbol-selection-summary">
            {view.symbolSelection.summaryLine ??
              `${view.symbolSelection.count} 只 · ${view.symbolSelection.listName} · 版本 ${view.symbolSelection.listVersion}`}
          </p>
          {view.symbolSelection.listNote ? (
            <p data-testid="symbol-selection-note">{view.symbolSelection.listNote}</p>
          ) : null}
          {view.symbolSelection.listNote && view.symbolSelection.listVersion ? (
            <p data-testid="symbol-selection-version">版本 {view.symbolSelection.listVersion}</p>
          ) : null}
          <p>
            数据区间 {view.symbolSelection.dataStart} 至 {view.symbolSelection.dataEnd}
            （数据窗口截止 {view.symbolSelection.dataCutoff}
            {view.backtestCutoff
              ? ` · 回测截止（最后交易日）${view.backtestCutoff}`
              : ""}
            ） · 来源{" "}
            {view.symbolSelection.dataSource}
          </p>
        </section>
      )}
      {view.status !== "ended" && (
        <p className="extend-hint" data-testid="extend-research-hint">
          「延长有效研究时间」仅在研究状态为「已结束（未通过）」时出现；有效时间用尽后会显示延长入口。
        </p>
      )}
      {view.canContinueIterate && (
        <button
          type="button"
          data-testid="continue-iterate"
          onClick={() => {
            const m = view.cumulativeRoundsOnWindow ?? 0;
            const threshold = view.highSuspicionRoundThreshold ?? 20;
            setIterateConfirm({
              title: "继续迭代",
              body: `${view.windowCumulativeLabel ?? `本窗口所有研究累计 ${m} 轮`}。再加预算不放宽任何阈值，只增加偶然通过的可能性。确认继续迭代？`,
              confirmLabel: "继续迭代",
              onConfirm: () => {
                if (m >= threshold) {
                  setIterateConfirm({
                    title: "高怀疑提示",
                    body: `已累计 ${m} 轮（阈值 ${threshold}）。偶然通过的可能性更高。确认仍要追加预算并继续？`,
                    confirmLabel: "仍要继续",
                    onConfirm: () => {
                      void api.continueIterate(view.researchId, {
                        userConfirmed: true,
                        highSuspicionAcknowledged: true,
                      });
                      setIterateConfirm(null);
                    },
                  });
                  return;
                }
                void api.continueIterate(view.researchId, {
                  userConfirmed: true,
                  highSuspicionAcknowledged: false,
                });
                setIterateConfirm(null);
              },
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
            {view.windowCumulativeLabel ?? `本窗口所有研究累计 ${view.latePassPresentation.cumulativeRoundsOnWindow} 轮`}；
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
      {view.rounds && view.rounds.length > 0 && (
        <section className="completed-rounds" data-testid="completed-round-evidence">
          <p className="eyebrow">各轮证据摘要</p>
          {view.rounds.map((round, index) => (
            <article className="round-card" key={round.roundId} data-testid="completed-round-card">
              <small>第 {(view.rounds?.length ?? 0) - index} 轮</small>
              <p>{round.logicStatement.statement}</p>
              {round.logicStatement.changeDescription && (
                <p className="change-note">{round.logicStatement.changeDescription}</p>
              )}
              {round.implementationDelta.modelChangesDisplay && (
                <p>{round.implementationDelta.modelChangesDisplay}</p>
              )}
              <p className="round-verdict">
                {round.verificationPassed
                  ? round.pitPassed === false
                    ? "验证通过 · 时点未通过"
                    : "验证通过"
                  : "验证未通过"}
              </p>
            </article>
          ))}
        </section>
      )}
        {eligible && (
          <details className="completed-tools-details">
            <summary>更多操作</summary>
            <ExportFeedbackBlock
              exportFeedback={exportFeedback}
              openFolderError={openFolderError}
              onExport={() => void runExport("research_record")}
              onReveal={revealExportFolder}
            />
            <div className="reverify-panel" data-testid="reverify-panel">
              <p className="eyebrow">对某一步重新验证</p>
              <label>
                轮次
                <select
                  value={reverifyRoundId}
                  onChange={(event) => setReverifyRoundId(event.target.value)}
                  data-testid="reverify-round-select"
                >
                  {reverifyRounds.map((round) => (
                    <option key={round.roundId} value={round.roundId}>{round.roundLabel}</option>
                  ))}
                </select>
              </label>
              <label>
                验证方法
                <select
                  value={reverifyMethodId}
                  onChange={(event) => setReverifyMethodId(event.target.value)}
                  data-testid="reverify-method-select"
                >
                  {methodsForRound.map((method) => (
                    <option key={method.methodId} value={method.methodId}>
                      {method.methodLabel}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                className="text-button"
                disabled={reverifyBusy}
                data-testid="reverify-submit"
                onClick={() => void runReverify()}
              >
                {reverifyBusy ? "重新验证中…" : "执行重新验证"}
              </button>
            </div>
            <div className="stacked-field modify-rerun-field">
              <span className="field-label">改策略再跑</span>
              <input
                value={modification}
                onChange={(event) => setModification(event.target.value)}
                placeholder="例如：把最长研究时间改成 6 小时"
                aria-label="改策略再跑"
              />
              <button
                disabled={!modification.trim()}
                data-testid="confirm-modification-button"
                onClick={() => void (async () => {
                  await api.sendDialogue(view.researchId, modification.trim());
                  await api.confirmModification(view.researchId);
                })()}
              >
                确认修改并开新版
              </button>
            </div>
          </details>
        )}
        {view.status === "ended" && (
          <label className="extend-hours-field">
            延长有效研究小时
            <input value={extensionHours} onChange={(event) => setExtensionHours(event.target.value)} inputMode="decimal" />
            <button onClick={() => void api.extendResearch(view.researchId, Number(extensionHours))}>确认延长并开新版</button>
          </label>
        )}
      </article>
    </div>
  );
}

export function MethodDetail({api, method}: {api: DesktopApi; method: ValidationMethod}) {
  const [reviseOpen, setReviseOpen] = useState(false);
  const [reviseBody, setReviseBody] = useState(
    method.definitionDisplay ?? method.description,
  );
  const comparisonLabel = (dim: NonNullable<ValidationMethod["dimensions"]>[number]) =>
    dim.comparisonLabel ??
    ({gt: "大于", gte: "不小于", eq: "等于", lt: "小于", lte: "不大于"} as const)[dim.comparison];
  return (
    <section className="method-detail">
      <h1>{method.name}</h1>
      {method.category && <span className="method-category-badge">{method.category}</span>}
      {method.description && !method.description.trim().startsWith("{") ? (
        <p>{method.description}</p>
      ) : null}
      <div className="method-definition-display" data-testid="method-definition-display">
        {method.definitionDisplay ?? method.description}
      </div>
      <details className="method-advanced">
        <summary>修订标识（高级）</summary>
        <code className="revision-id" title={method.revision}>{method.revision}</code>
      </details>
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
                  <td>{dim.kindLabel ?? dim.kind}</td>
                  <td>{dim.name}</td>
                  <td>{dim.passThreshold}</td>
                  <td>{comparisonLabel(dim)}</td>
                  <td>{dim.failureDisplay}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <button className="quiet-button" type="button" onClick={() => setReviseOpen(true)}>编辑为新定义</button>
      <p>旧研究和已导出的策略包仍引用原定义。</p>
      {reviseOpen && (
        <div className="in-app-confirm-backdrop" data-testid="revise-method-dialog">
          <div className="in-app-confirm-card revise-method-card" role="dialog" aria-modal="true">
            <h2>编辑为新定义</h2>
            <p>将基于下方正文生成新修订；旧研究仍引用原定义。</p>
            <label>
              新定义正文
              <textarea
                value={reviseBody}
                onChange={(event) => setReviseBody(event.target.value)}
                rows={6}
              />
            </label>
            <div className="in-app-confirm-actions">
              <button type="button" onClick={() => setReviseOpen(false)}>取消</button>
              <button
                type="button"
                className="cyan-button"
                disabled={!reviseBody.trim()}
                onClick={() => {
                  void api.reviseMethod(method.id, reviseBody.trim());
                  setReviseOpen(false);
                }}
              >
                确认生成新修订
              </button>
            </div>
          </div>
        </div>
      )}
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
            <small className="revision-label">
              {(method as {revisionLabel?: string}).revisionLabel ?? "内置修订"}
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
  runStartRitual,
}: ScreenProps & {runStartRitual?: boolean}) {
  switch (view.kind) {
    case "research_list": return <ResearchList api={api} view={view} />;
    case "draft": return <DraftScreen api={api} view={view} />;
    case "confirm_run": return <ConfirmRunScreen api={api} view={view} />;
    case "running":
      return (
        <RunningScreen
          api={api}
          view={view}
          modification={pausedModificationByResearch[view.researchId] ?? ""}
          onModificationChange={(text) => onPausedModificationChange(view.researchId, text)}
          runStartRitual={runStartRitual}
        />
      );
    case "awaiting_confirm": return <div className="focus"><AwaitingConfirmCard api={api} view={view} /></div>;
    case "completed": return <CompletedScreen api={api} view={view} />;
    case "methods": return <MethodsScreen api={api} view={view} />;
    case "glossary": return <GlossaryScreen view={view} />;
  }
}

function GlossaryScreen({view}: {view: Extract<DesktopView, {kind: "glossary"}>}) {
  return (
    <div className="glossary-page" data-testid="glossary-page">
      <p className="confirm-lead">{view.intro}</p>
      {view.entries.map((entry) => (
        <details key={entry.id} className="tech-pulse-card glossary-entry" open>
          <summary>{entry.term}</summary>
          <p>{entry.body}</p>
        </details>
      ))}
    </div>
  );
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
  const routeGeneration = useRef(0);
  const seenRoute = useRef(route);
  if (seenRoute.current !== route) {
    seenRoute.current = route;
    routeGeneration.current += 1;
  }
  const [routeError, setRouteError] = useState<string | null>(null);
  const [failedRoute, setFailedRoute] = useState<string | null>(null);
  const [routeRetry, setRouteRetry] = useState(0);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [sidecarState, setSidecarState] = useState<SidecarUiState | null>(null);
  const [pausedModificationByResearch, setPausedModificationByResearch] = useState<
    Record<string, string>
  >({});
  const onPausedModificationChange = useCallback((researchId: string, text: string) => {
    setPausedModificationByResearch((prev) => ({...prev, [researchId]: text}));
  }, []);
  const engineStopped = sidecarState?.phase === "stopped";
  const routeFailed = failedRoute === route && routeError !== null;
  const routePending = route !== syncedRoute && !routeFailed;
  const runStartRitual = useRunStartRitual(view);

  const refreshView = useCallback(async () => {
    const generation = routeGeneration.current;
    const requestedRoute = route;
    const next = await api.fetchView(requestedRoute);
    if (generation !== routeGeneration.current) return;
    setView(next);
    setSyncedRoute(requestedRoute);
    setRouteError(null);
    setFailedRoute((current) => (current === requestedRoute ? null : current));
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
    if (/MARKET_DATA_|DATA_SOURCE_UNAVAILABLE/.test(mutationError)) return;
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
    if (engineStopped || !api.pollMarketDataProgress) return;
    let active = true;
    const tick = () => {
      void api.pollMarketDataProgress?.()
        .then((next) => {
          if (!active || !next) return;
          setView((current) => ({
            ...current,
            marketDataProgress: next.marketDataProgress,
            hostStatus: next.hostStatus ?? current.hostStatus,
          }));
        })
        .catch(() => {
          /* progress poll failed; the route poll can still refresh */
        });
    };
    tick();
    const timer = window.setInterval(tick, 400);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [api, engineStopped]);

  useEffect(() => {
    if (engineStopped) return;
    let active = true;
    const generation = routeGeneration.current;
    const requestedRoute = route;
    const refresh = () => {
      void api
        .fetchView(requestedRoute)
        .then((next) => {
          if (!active || generation !== routeGeneration.current) return;
          setView(next);
          setSyncedRoute(requestedRoute);
          setRouteError(null);
          setFailedRoute((current) => (current === requestedRoute ? null : current));
        })
        .catch((error: unknown) => {
          if (!active || generation !== routeGeneration.current) return;
          setRouteError(routeFailureMessage(error));
          setFailedRoute(requestedRoute);
        });
    };
    refresh();
    const timer = window.setInterval(refresh, 1_000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [api, route, engineStopped, routeRetry]);

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
    <NightShell view={view} route={route} sidecarState={sidecarState} runStartRitual={runStartRitual}>
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
      ) : routeFailed ? (
        <div className="route-error" data-testid="route-error" role="alert">
          <p>{routeError}</p>
          <button
            type="button"
            className="quiet-button"
            data-testid="route-retry"
            onClick={() => {
              setFailedRoute(null);
              setRouteRetry((count) => count + 1);
            }}
          >
            重试
          </button>
        </div>
      ) : (
        <Screen
          api={boundApi}
          initialView={view}
          pausedModificationByResearch={pausedModificationByResearch}
          onPausedModificationChange={onPausedModificationChange}
          runStartRitual={runStartRitual}
        />
      )}
    </NightShell>
  );
}
