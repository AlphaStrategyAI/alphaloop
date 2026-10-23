# 最终验证状态

日期：2026-10-23。环境：Linux，Python 3.12.3，Node v22.14.0，rustc 1.83.0（契约测试期间 rustup 另装过 stable）。

状态只用：实际运行 / 仅静态检查 / 未验证。

| 主张或步骤 | 状态 | 记录 |
| --- | --- | --- |
| `pip install -e ".[dev]"` | 实际运行 | 成功。解析到 pandas 3.1.0、yfinance 1.7.0、akshare 1.19.3。脚本装在用户目录，不在默认 PATH 时用 `python3 -m apps.cli.main` |
| `python3 -m apps.cli.main start` 然后 `status` | 实际运行 | JSON 与 README 中的示例一致（pid 11699 是这一次）。进程随后被结束，再次 status 为 `running: false` |
| 离线 pytest | 实际运行 | 484 passed，2 deselected（network），1 failed。失败原因为本机起初没有 gdk-3.0，安装 GTK 开发包后变为缺少 CI 才放置的空引擎占位。按 `.github/workflows/python-tests.yml` 放上占位后，`test_rust_shared_fixture_table` 1 passed。占位未留在工作区 |
| `npm ci && npm test` | 实际运行 | 44 files / 169 tests passed，`tsc --noEmit` 通过。耗时约 14 秒（含 npm ci 约数秒，测试本身 8.81 秒）。这不是用户完成一项研究的时间 |
| `npm audit --omit=dev` | 实际运行 | 生产依赖漏洞计数为 0。含 dev 时为 2 moderate、2 high |
| 合成价格上的 `daily_book` | 实际运行 | 首行权重为 0，与 `shift(1)` 一致。净值不写入 README |
| 池子只数 | 实际运行 | 503 / 300 / 40 / 40 |
| PyPI 包名 | 实际运行 | HTTP 404 |
| 默认数据根字符串 | 实际运行 | `platformdirs` 打印出 Linux 路径 |
| `scripts/build_sidecar.sh`（未安装 python3-venv） | 实际运行 | 退出码 1。stderr：虚拟环境未创建成功，因为 ensurepip 不可用，并提示安装 `python3.12-venv`。已写入 README 的前置条件。安装该包后的重试见本节末尾 |
| `npm run tauri dev` 以及在界面里新建研究、确认、导出 | 未验证 | 没有在图形会话里点击。README 中的点击步骤来自界面代码和测试名，不是这次的屏幕录像 |
| 带网络的均值回归验收 `tests/test_v1_honest_path.py` | 未验证 | 需要 `ALPHALOOP_ACCEPTANCE_NETWORK=1`，本次未设 |
| macOS / Windows 安装包 | 未验证 | 只读了对应 workflow。没有在那些系统上构建 |
| Node 20 上的 `npm test` | 未验证 | 打包 workflow 写 Node 20，本次只用了 Node 22 |
| 所有 README 外链在浏览器中逐一点开 | 仅静态检查为主 | 写作时抓取过 yfinance、AkShare、vectorbt、米筐文档、Bailey PDF、聚宽 API PDF。聚宽收费页与社区调价帖返回 403。其余链接与仓库内相对路径在提交前做一次存在性检查 |
| 英文 README 与中文 README 的事实一致 | 仅静态检查 | 同一轮写成，没有独立翻译审校 |
| 真人是否看懂首屏 | 未验证 | 方案在 user-validation-plan.md，没有执行 |

模拟评审不是真人反馈。评审记录若存在，见 review-log.md，不得被引用成用户证言。
