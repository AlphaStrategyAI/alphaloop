# 最值得补齐的材料

按对「一个合适的人是否愿意试跑」的影响排序。只列少量。产品缺口和材料缺口分得开。

## 材料

1. **两名外部读者的笔记。** 按 [user-validation-plan.md](./user-validation-plan.md) 做。2026-10-23 已经有一次维护者自己的桌面运行和截图，仍然没有外部用户的原话。
2. **依赖锁定。** `pyproject.toml` 不钉版本。一次安装得到 pandas 3.1.0，而对照的 zipline-reloaded 3.2 明确不支持 pandas 3。没有锁文件，README 里的安装步骤过几个月可能不再是同一次解析。
3. **默认数据根上的同一次点击。** 这次桌面进程继承了 `ALPHALOOP_DATA_ROOT=/tmp/alphaloop-readme-demo`。默认 `~/.local/share/ai.alphastrategy.alphaloop` 上的点击还没有做。结果本身不依赖这个临时目录，但路径截图写的是 `/tmp`。

## 产品缺口（不在这次 README 里假装已经有）

1. **未经许可来源的告知与主动确认。** 规格已写，界面和确认流程没有。在这之前，README 必须继续写「还没做到」。
2. **能开跑的策略只有均值回归。** 五族规格提前了，执行没有。要么把其余四族跑通，要么继续在首屏写死边界。
3. **导出门禁与规格不一致。** `coverage_satisfied` 不在 `strategy_pack_eligibility` 里。成本有两层，术语表仍写收益序列不含费用。
4. **没有贡献入口的实体。** 没有 CONTRIBUTING，讨论区关闭，没有开放的 good first issue。在补上之前，README 不应邀请人「加入社区」。
5. **EDGAR 身份是 `research@example.invalid`。** 若继续请求 EDGAR，应换成真实联系方式，并确认对方的访问政策。这不是 README 能解决的。
