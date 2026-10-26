# 产品事实清单

核对日：2026-10-23。实现优先于规格。冲突写在第 8 节，不选好听的说法。

## 1. 这是什么

本机桌面应用加一个 Python 引擎。版本 0.2.0（`pyproject.toml`、`apps/desktop/package.json`）。Python 要求 `>=3.12`。桌面是 Tauri 2 + React + TypeScript。命令行入口 `python3 -m apps.cli.main`，只有 `start` 和 `status`（`apps/cli/main.py`）。引擎入口是 `python3 -m engine.main`。

GitHub 仓库描述写的是 “AI-automated quant research loop”。默认配置不是这条：`ALPHALOOP_REVIEWER` 默认 `deterministic`（`engine/main.py`）。

## 2. 核心工作流

1. 桌面里新建研究。对话按槽位补齐五项：论点、标的、有效研究时间、第一轮验证方法、覆盖底线（`engine/dialogue/prompts.py`）。
2. 未写代码时，空标的列表填入该市场的默认池（`engine/research/universe_pool.py`）。
3. 草稿按标的钉数据源：全部是 A 股代码则 `akshare_sina_daily`，否则 `yahoo_daily`（`engine/research/planned_data_window.py`）。这是自动钉选，不是用户在界面上点选。
4. 确认开跑把 `construction_schedule` 设为 `schedule_v1`（`engine/main.py`）。
5. `ResearchLoop` 取数、模拟、验证。只有 `strategy_family` 为 `mean_reversion` 或 `legacy_mean_reversion` 且 `family_method` 为 `legacy_zscore_daily` 才能跑（`engine/research/families.py`、`engine/research/loop.py`）。其他族抛出 `STRATEGY_FAMILY_NOT_RUNNABLE`，文案是「这一族还不能开跑。」
6. 信号是回看窗口内收益均值的截面 z 分数（单名时用自身滚动标准差）。权重使用 `shift(1)` 之后的信号（`engine/strategy.py`）。
7. 验证方法未全过、且下一步只是实现层参数变化时，在当前版本内自动迭代，直到预算用尽。默认预算 5（`ALPHALOOP_MAX_TRIALS`）。自动提案把 `lookback_days` 加 5（`engine/research/honest_stop.py`）。
8. 经济逻辑、覆盖、数据血缘类变更需要确认，不自动继续。
9. 导出：`strategy_pack_eligibility` 五项全过才是策略包，否则研究记录（`engine/export.py`）。

计划中的数据窗口是从当天 UTC 日期倒推 `365 * 12` 天（`planned_data_window`）。

## 3. 首个可观察的价值

命令行的第一个可观察结果是 `status` 的 JSON：`running: true` 只表示进程在，没有研究。研究价值出现在桌面完成页：门禁结果、试验次数、以及导出的 zip。本次环境没有打开图形界面，因此没有观察到一次真实的完成页。离线测试能够把研究循环跑到 `COMPLETED`（例如 `tests/test_loop_runtime.py`，包含在第 7 节的 pytest 结果里）。

## 4. 稳定与实验

当作已经交出去的路径：一条截面均值回归、确定性评审器、离线测试所覆盖的状态机和导出。

规格已写、代码未当作可运行能力：五个策略族里的其余四个、本地 CSV 导入、商业数据商、设置页的数据源与大模型、未经许可来源的知情确认、导出键 `coverage_satisfied`、中英文里策略族的英文显示名（非中文时 `family_display_name` 返回 id 本身，见 `tests/test_a1_family_frozen_input.py`）。

界面语言切换（跟随系统 / 中文 / 英文）在设置的通用页，是已接上的界面，不是「稍后」页（`apps/desktop/src/settings/SettingsPage.tsx`）。数据源页和大模型页渲染 `settings.later.body`。

## 5. 运行、数据与外部依赖

| 去向 | 代码 |
| --- | --- |
| 美股日线 | `YahooDataAdapter`，依赖 yfinance |
| A 股日线 | `AkShareDataAdapter`，新浪优先，东财回退 |
| 论文 | `PapersAdapter`，Crossref |
| 发行人材料 | `SecEdgarAdapter`，User-Agent 固定为 `alphaloop/0.2 research@example.invalid` |
| 本机 Markdown | 数据目录 `materials/` |
| 研究库 | SQLite `research.db` |
| 密钥 | 桌面有保险库按钮，优先系统钥匙串；无 Secret Service 时可选本次会话或口令文件（`apps/desktop/src/SecretVault.tsx` 与引擎 `secret_memory`）。设置页还不能把数据源账户配成一项可用来源。 |

没有云账号，没有托管。默认数据根：`platformdirs.user_data_dir("ai.alphastrategy.alphaloop")`，Linux 示例 `~/.local/share/ai.alphastrategy.alphaloop`。

依赖未钉版本。2026-10-23 本次 `pip install -e ".[dev]"` 解析到 pandas 3.1.0、yfinance 1.7.0、akshare 1.19.3。

## 6. 费用、许可、支持

- 软件许可证：MIT。版权行 `Copyright (c) 2026 AlphaStrategyAI`，与 GitHub 组织名一致。2026-10-23 起由维护者把原来的 `OpenStrategy Team` 改成这个名字。许可类型和年份没有改。
- 没有 PyPI 发布（该 URL 404），没有 GitHub Release。桌面打包只在 CI 里上传 artifact，不构成公开发布的安装包。
- 没有价格、没有支持合同、没有招聘页面。
- `npm audit`：全部依赖 2 moderate + 2 high；`--omit=dev` 为 0。未逐条打开公告。

## 7. 测试与 CI

工作流：`python-tests.yml`（pytest，跳过 network，并安装 WebKit/GTK 与一个空的引擎占位）、`desktop-typecheck.yml`（Node 22）、`desktop-tauri-rust.yml`、`desktop-release-macos.yml` 与 `desktop-release-windows.yml`（Node 20，构建侧车与安装包 artifact）、`keyring-linux-optional.yml`。

本次运行见 [verification.md](./verification.md)。

## 8. 与规格或旧文档冲突（实现为准）

| 主题 | 规格或旧文案 | 2026-10-23 的代码 |
| --- | --- | --- |
| 产品一句话 | 定位文档：随时丢进大致方向，长时间自主研究，交出经过验证的策略 | 只有均值回归能跑；对话是五个槽位；默认不调用大模型 |
| 五个策略族 | `strategy-families-v1.md` 把美国版本提前到 M2 | `families.py` 只有 id 和中文名；`loop.py` 拒绝非 legacy 均值回归 |
| 未经许可 | 设置规格：Yahoo / AkShare 不默认选中，必须知情确认，界面标「未经许可」 | 按标的自动钉源；展示名是「雅虎日线」「AkShare 日线（新浪优先）」；确认流程无该勾选。词条只在 i18n 术语表 |
| 导出第五项 | 产品设计：五项资格含 `coverage_satisfied` | `strategy_pack_eligibility` 的五项是 completed、methods、no_pending_confirm、reverifies、pit。全库测试无 `coverage_satisfied` 字符串 |
| 成本是否进入收益序列 | `docs/GLOSSARY.md` 与旧 README：验证器里按换手近似，收益序列不含逐日费用 | 新确认使用 `schedule_v1`，`simulate_daily` 用 `book.net`，已经扣了表内 bp；`cost.turnover` 仍再减 10bp（美）或 20bp（A） |
| 成本数字 | 门禁 10bp / 20bp；回测表 5 / 1 / 20 / 5 bp | 两套同时存在，见上一行 |
| 默认池只数 | `apps/desktop/docs/tech-pulse-ui.md` 仍写确认卡展示 40+40 | v2 池文件分别是 503 与 300。v1 仍是 40，只给旧研究 |
| 数据源是否默认 | 规格：不是默认选中 | `pin_draft_data_source` 在草稿上写入源 id |
| 仓库标语 | GitHub description 强调 AI automated loop | 默认评审器是确定性的 |
| 版权名 | 曾写 OpenStrategy Team | 2026-10-23 维护者决定统一为 AlphaStrategyAI，`LICENSE` 已改。不再是未关闭缺口 |
| 英文族名 | 规格：显示名按当前语言渲染 | 非中文 locale 返回 id 字符串 |

## 9. 影响决策的限制

- 生成日名单的幸存者偏差写在池 JSON 的中文 `selection.survivorship` 里，界面注记是「非时点成分」（`engine/research/pool_display.py`）。规格里的字段 id `survivorship_bias_untested` 没有写入导出。它不是被排除，只是没有成为导出门禁。
- A 股不模拟 T+1 和涨跌停。
- 个股按复权价请求（yfinance `auto_adjust=True`，AkShare `qfq`），基准仍是价格指数（`SPX` 取 `^GSPC`，`000300.SH` 取指数日线）。口径不一致是这条路径的结果。
- 窗口键含确认日，隔天重开是新窗口。
- 时点检查范围窄，见第 2 节。
- EDGAR 使用 `example.invalid` 邮箱，本次没有做真实 EDGAR 请求，不能声称该身份会被接受。
- 公开仓库没有可引用的采用记录。
