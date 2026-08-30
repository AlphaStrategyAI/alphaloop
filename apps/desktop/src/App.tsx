import {FormEvent, useEffect, useState} from "react";

import type {
  DesktopApi,
  DesktopView,
  ResearchStatus,
  ValidationMethod,
} from "./contracts";
import "./night.css";

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
  const hostStatus =
    view.kind === "awaiting_confirm" ? "等待确认" :
    view.kind === "running" ? "运行中" :
    view.kind === "completed" ? "已完成" : "本机静";
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
        <div className={`host-status ${view.kind}`}>● {hostStatus}</div>
      </aside>
      <section className={`content ${view.kind}`}>{children}</section>
    </main>
  );
}

function StatusPill({status}: {status: ResearchStatus}) {
  return <span className={`status-pill ${status}`}>{statusLabels[status]}</span>;
}

function ResearchList({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "research_list"}>}) {
  return (
    <div className="browse list-screen">
      <header className="list-header">
        <p>一条对话，一次研究。等你确认的会排在最上面。</p>
        <button className="quiet-button" onClick={() => void api.createDraft()}>新建研究</button>
      </header>
      {view.awaiting && (
        <article className="awaiting-primary" data-kind="awaiting-primary">
          <StatusPill status="awaiting_confirm" />
          <h2>{view.awaiting.title}</h2>
          <p>美股 · 股票 · 等了 2 小时</p>
        </article>
      )}
      <div className="research-rows">
        {view.rows.map((row) => (
          <article className="research-row" data-testid="research-row" key={row.id}>
            <div><h3>{row.title}</h3><p>最近活动保留在本机</p></div>
            <div className="row-actions">
              <a href={`#/research/${row.id}`}>进入</a>
              <button onClick={() => {
                const accepted = window.confirm(
                  "删除会永久移除对话、版本、迭代与验证记录及导出资格；已导出的本机文件不受影响。",
                );
                if (accepted) void api.deleteResearch(row.id);
              }}>删除</button>
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
      <header><StatusPill status={view.status} /> 第 {view.version} 版 · 有效研究 {view.effective} · {view.coverage}</header>
      <h1>迭代与验证</h1>
      {view.rounds.map((round, index) => (
        <article className="round-card" key={round}>
          <small>v{view.version} · 第 {view.rounds.length - index} 轮</small>
          <h2>{round}</h2>
          <p>每轮都显示市场基准指标、四项验证和独立审查。</p>
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
  return (
    <article className="awaiting-card" data-testid="awaiting-confirm-card">
      <p className="eyebrow">等待确认 · 第 {view.version} 版 · 这段时间不计入额度</p>
      <h1>经济逻辑要改了</h1>
      <section><small>现在打算改什么</small><p>{view.proposed}</p></section>
      <section><small>为什么要改</small><p>{view.reason}</p></section>
      <section><small>改了之后会变成什么样</small><p>{view.effect}</p></section>
      <div className="decision-stack">
        <button className="cyan-button" onClick={() => void api.resolveConfirm(view.researchId, "approve_new_version")}>同意，开新的一版</button>
        <button onClick={() => void api.resolveConfirm(view.researchId, "reject_keep_logic")}>不同意，维持原逻辑继续</button>
        <button onClick={() => void api.resolveConfirm(view.researchId, "pause_and_edit")}>暂停，我自己改</button>
      </div>
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
  ] as const;
  const eligible = checks.every(([, passed]) => passed);
  return (
    <div className="focus completed-screen">
      <StatusPill status={view.status} />
      <p>alphaloop 到这里结束，不提供执行入口。</p>
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
      <p>{method.description}</p>
      <p>当前冻结定义：{method.revision}</p>
      <button className="quiet-button" onClick={() => void api.reviseMethod(method.id, method.description)}>编辑为新定义</button>
      <p>旧研究和已导出的策略包仍引用原定义。</p>
    </section>
  );
}

function MethodsScreen({api, view}: {api: DesktopApi; view: Extract<DesktopView, {kind: "methods"}>}) {
  const selected = view.methods.find((item) => item.id === view.selected) ?? view.methods[0];
  return (
    <div className="methods-layout">
      <aside className="method-list">
        <p>编辑得到新定义，旧研究不改写。</p>
        {view.methods.map((method) => <a href={`#/methods/${method.id}`} key={method.id}>{method.name}<small>{method.revision}</small></a>)}
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
