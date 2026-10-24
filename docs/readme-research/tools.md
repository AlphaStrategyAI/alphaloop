# 工具

## 实际使用

| 工具 | 用途 |
| --- | --- |
| 阅读仓库 | `README.md`、`LICENSE`、`pyproject.toml`、`engine/`、`apps/cli`、`apps/desktop`、`docs/requirements/`、`docs/GLOSSARY.md`、`.github/workflows/` |
| 本机命令 | `pip install -e ".[dev]"`、`python3 -m pytest -q -m "not network"`、补跑 Rust 契约测试、`npm ci && npm test`、`npm audit`、`python3 -m apps.cli.main start/status`、合成价格上的 `daily_book` |
| GitHub CLI | `gh repo view`、`gh release list`、`gh issue list`、`gh pr list`、contributors API。只读 |
| 网页检索与抓取 | 聚宽 API PDF、yfinance README、AkShare README、vectorbt README、zipline-reloaded、backtrader PyPI、米筐文档、Qlib、LEAN、Bailey & López de Prado PDF、Reddit、知乎检索摘要、PyPI 404、Yahoo API 条款页 |

## 建议使用但本次没有用到

| 工具 | 原因 |
| --- | --- |
| 带网络的验收测试 `ALPHALOOP_ACCEPTANCE_NETWORK=1` | 会访问 Yahoo / AkShare / Crossref。README 不需要一次真实回测数字，也避免把未授权拉取写成演示 |
| 图形界面里的完整点击（Tauri） | 需要侧车和显示。侧车构建若在本环境完成，结果记在 verification.md；点击路径仍要人在桌面上看 |
| 聚宽收费页的人工登录查看 | 直接请求返回 403。不注册账号去看价格 |
| 知乎 / 雪球正文 | 检索只给出摘要。不把摘要扩写成引语 |

## 无法访问或不适用

| 工具 | 情况 |
| --- | --- |
| 本仓库 Discussions | API 410，功能关闭 |
| 本仓库用户访谈、客服、支付 | 不存在，也不去创建 |
| 对外发帖或联系维护者 | 任务禁止对外发布和联系 |
| Figma | 这次不改界面，不打开设计文件 |
| 支付或标价创建 | 没有付费产品，不新建价格 |
