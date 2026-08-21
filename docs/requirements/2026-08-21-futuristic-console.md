# Futuristic console visual brief (2026-08-21)

Reference survey (GPT-5.6 Sol): OpenBB Workspace, QuantConnect Results, WorldQuant BRAIN, Weights & Biases, Elicit systematic review, Anthropic Console, JupyterLab, Linear. Steal: dense local research bench, results/logs layering, constrained experiment params, run table + collapsible evidence, protocol timeline + screening funnel, eval matrix honesty, local collapsible workspace, restrained dark + keyboard. Reject: cloud-upload narrative, trading-deploy / equity-curve-as-center, “make alpha” / contests / profit, unlimited custom SaaS, 10× efficiency marketing, chat-oracle center, window-manager complexity, brand-purple over-polish.

## Brief (≤1000 汉字)

将单页塑造成“昼夜交接台”，不是行情终端。顶部固定显示 LOCAL、worker、主机需保持唤醒及最近心跳；主体以 Before bed / Morning 双阶段切换，Help 降为辅助入口。睡前采用单列渐进流程：假设→市场与数据→预检→冻结协议→提交，提供可靠默认值、行内校验、键盘操作和清晰提交回执，目标一分钟完成。早晨反转信息层级：先给唯一结论，再给主要证据与停止原因，随后才是候选漏斗、方法修订、未执行建议及可展开原始证据，保证五分钟读懂。

字体用中性无衬线承载叙述，等宽字体仅用于 ID、状态、参数和哈希。深色为首版主主题：背景近黑蓝，表面以两级石墨灰区分，正文高亮灰白，辅助文字冷灰；青色仅表示操作、焦点与运行。`FOUND` 专用绿色且必须与“GateEvidence 完整”同时出现；`NO_EVIDENCE` 用冷灰蓝，`INCONCLUSIVE` 用琥珀色，红色只表示技术失败或危险操作。未来若增加浅色主题，状态语义不变。

动效限于 120–180ms 淡入、4px 位移、面板展开与真实检查点推进；禁止假进度、粒子、霓虹脉冲和持续扫描线。所有运行状态应可静止阅读并尊重减少动态效果设置。

不得复制收益排行榜、社交交易、K 线墙、经纪商 CTA、云端上传诱导、AI 神谕式文案或“发现 Alpha”承诺；报告是证据视图，不是证据来源，更不代表未来盈利。

## Implementation locks

Packaged first-release UI only: `src/alphaloop/webui/static/{index.html,styles.css,app.js}`. Do not unfreeze `webui/`. Do not change Help sentences or `HOST_CONSTRAINT`. Do not remap these tokens (e2e locks the computed RGB):

| Token | Hex | Locked computed color |
| --- | --- | --- |
| `--accent` FOUND / Freeze | `#3ee0a0` | `rgb(62, 224, 160)` |
| `--warn` NO_EVIDENCE / Resume | `#ffb020` | `rgb(255, 176, 32)` |
| `--inconclusive` | `#c4a0ff` | keep purple (do not switch to amber) |
| `--focus` Preview / Cancel | `#7eb8ff` | `rgb(126, 184, 255)` |
| `--ink` designed button fill | `#0b0f16` | `rgb(11, 15, 22)` |
| `--fg` Load example | `#f3efe6` | `rgb(243, 239, 230)` |

Keep `@keyframes overnight-pulse`, `prefers-reduced-motion { animation: none }`, and a `repeating-linear-gradient` in CSS (instrument hairline, not a full-page scan grid). No webfont `http`. No `override` in `app.js`.

## Acceptance

- Masthead shows a `LOCAL` instrument chip and a worker idle/running chip.
- `#stage-nav` switches Before bed / Morning / Help. Narrow: only the active stage is shown. Wide: Before bed and Morning stay side by side; Help replaces them.
- Freeze selects the Morning stage and still `scrollIntoView`s the current job.
- Body is graphite with restrained glows; no full-page scan overlay.
- Motion 120–180ms; reduced-motion disables animation and transitions.
- Existing morning e2e color and copy locks still pass.
