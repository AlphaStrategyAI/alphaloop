from __future__ import annotations

from enum import StrEnum


class SlotName(StrEnum):
    THESIS = "thesis"
    UNIVERSE = "universe"
    MAX_EFFECTIVE_HOURS = "max_effective_hours"
    ROUND1_METHODS = "round1_methods"
    COVERAGE_FLOOR = "coverage_floor"


QUESTIONS = {
    SlotName.THESIS: (
        "原理想靠什么赚钱？例如：美股大市值股票的均值回归。"
    ),
    SlotName.UNIVERSE: (
        "研究哪类资产？例如：美股股票；也可以说「SPY、QQQ」指定标的。"
    ),
    SlotName.MAX_EFFECTIVE_HOURS: (
        "最多允许多少有效研究时间？例如：12 小时，或 30 分钟。暂停和等待确认不计时。"
    ),
    SlotName.ROUND1_METHODS: (
        "第一轮用哪些冻结验证方法？例如：走样检验、样本外稳定、拥挤度、换手成本。"
    ),
    SlotName.COVERAGE_FLOOR: (
        "最低数据覆盖？例如：至少 25 个、10 年、缺失不超过 5%。"
    ),
}
