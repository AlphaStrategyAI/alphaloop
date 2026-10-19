# alphaloop

本机优先的投资策略工坊：你给出一个大致方向，它在你自己的机器上做历史研究，交出一份可以检查的策略包。alphaloop 不下单。

## 当前能做

- 在桌面应用里用对话把一项研究谈清楚，确认后用冻结的验证方法做历史回测。
- 默认标的池是仓库里的版本化清单：美股大市值 40 只（`us_equity_large_cap_v1`）、A 股大市值 40 只（`cn_equity_large_cap_v1`）。日线来自 Yahoo（美股）和 AkShare（A 股，新浪优先）。用户写出代码可以覆盖默认池。
- 导出策略包或研究记录。包里的回测是历史假设业绩，不是实盘业绩，也不是对未来的承诺。
- 引擎里实现的策略族只有截面均值回归。

## 当前不能做

- 不下单，不接券商，不跑模拟盘。
- 没有 128 只池，没有 `US-EQ-LIQUID`，没有本机 parquet。本地 CSV/parquet 导入和更大的池是 P1，不在这一版。
- 论点文字不会把策略换成动量或其他族。对话、确认卡和完成页会说明 V1 只做均值回归（[#133](https://github.com/AlphaStrategyAI/alphaloop/pull/133)）。
- 门禁展示名是「分段稳健性检验」「集中度」。旧词「走样检验」「拥挤度」只在对话里当别名。左栏有「术语」页（[#129](https://github.com/AlphaStrategyAI/alphaloop/pull/129)）。
- 联网时，默认设定下回撤等门禁通常仍可能不通过。无发布日的资料不作为证据，时点一致性不再因此恒败（[#132](https://github.com/AlphaStrategyAI/alphaloop/pull/132)，pit-v2）。完成页「本研究累计」与导出 `rounds.json` 用同一把研究窗口键（[#131](https://github.com/AlphaStrategyAI/alphaloop/pull/131)）。

## 快速开始

需要 Python 3.12。

```bash
pip install -e ".[dev]"
python -m pytest -q -m "not network"
```

桌面（Node 22；`npm test` 含 vitest 与 `tsc --noEmit`）：

```bash
cd apps/desktop
npm ci
npm test
```

本机桌面：`cd apps/desktop && npm run tauri dev`（需要 Rust 与系统 WebView）。CLI 只有启动和看状态：安装后 `alphaloop start`、`alphaloop status`。引擎入口是 `alphaloop-engine`。

联网验收不是默认 CI。带网络的测试要显式打开 `ALPHALOOP_ACCEPTANCE_NETWORK=1`，并且不要用 `-m "not network"` 把它滤掉。

## 数据与联网

| 用途 | 来源 |
| --- | --- |
| 美股日线、美股基准 | Yahoo Finance（`yfinance`） |
| A 股日线、A 股基准 | AkShare（新浪优先） |
| 公开论文 / 发行人清单 | Crossref、SEC EDGAR |
| 本机材料 | `materials/` 下的 Markdown |

这些调用需要网络。抓取失败或数据不全时，研究按覆盖底线处理，不会改用一套仓库里不存在的 parquet 池。

## 文档

- [产品定位](./docs/requirements/product-positioning.md)
- [产品设计 v0.0.1](./docs/requirements/product-design-v0_0_1.md)
- [界面设计 v0.0.1](./docs/requirements/ui-design-v0_0_1.md)（03 / 05 / 06 与代码不一致处已标注，不重画）
- [V1 交付收口](./docs/requirements/v1-cut-line.md)
- [术语表](./docs/GLOSSARY.md) — 展示名（分段稳健性检验、集中度、试验次数与累计 M、基准与成本口径）
- [Tech Pulse 界面说明](./apps/desktop/docs/tech-pulse-ui.md)

## 已知限制

- 默认实现层预算是 5 轮（`ALPHALOOP_MAX_TRIALS`）。设计稿若画 6/6 轮或 M=8，与代码不符。
- 股票基准是价格指数，策略收益按复权总回报计算，两者不是同一口径。
- 成本门禁在验证器里按换手近似，回测收益序列本身不含逐日费用。
- 窗口键含确认日。同一想法隔天重开是新窗口；是否改成数据截止日尚未决定。完成页会把「数据窗口截止」和「回测截止（最后交易日）」分开写。

## License

MIT. See [`LICENSE`](./LICENSE).
