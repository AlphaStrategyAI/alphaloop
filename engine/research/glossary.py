"""User-facing glossary. Method labels come from display_names; do not fork them."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from engine.research.display_names import method_label
from engine.research.method_body_display import method_purpose
from engine.research.window_copy import (
    all_researches_on_window_label,
    research_on_window_label,
    version_trial_label,
)
from engine.verifiers import VERIFIER_REVISIONS


@dataclass(frozen=True, slots=True)
class GlossaryEntry:
    term_id: str
    term: str
    body: str


def glossary_intro() -> str:
    return (
        "这些是界面和导出包里使用的展示名。方法的 id 与修订号没有改，计算也没有改。"
        "对话里仍可输入旧称，会解析成同一个方法。"
    )


def _legacy_note(method_id: str, legacy: str) -> str:
    return (
        f"{method_purpose(method_id)}"
        f"展示名是「{method_label(method_id)}」。"
        f"对话里的旧称「{legacy}」仍可解析，方法 id 与修订号不变。"
    )


def glossary_entries() -> tuple[GlossaryEntry, ...]:
    cost = VERIFIER_REVISIONS["cost.turnover"]
    us_bp = cost["us_cost_bp"]
    cn_bp = cost["cn_cost_bp"]
    return (
        GlossaryEntry(
            "pit.consistency",
            method_label("pit.consistency"),
            method_purpose("pit.consistency"),
        ),
        GlossaryEntry(
            "trial_counts",
            "试验次数（X/N）与累计 M",
            (
                f"「{version_trial_label(1, 5)}」这种写法里，斜线前是当前版本已经跑过的轮次，"
                "斜线后是这一版的轮次预算（例子里的 1 和 5 只是格式）。"
                f"「{research_on_window_label(1)}」只计这一次研究在同一数据窗口上的轮次；"
                f"「{all_researches_on_window_label(1)}」把同一窗口上的其他研究也算进去。"
                "数字变大只说明试过更多轮，不代表任何门槛被放宽。"
            ),
        ),
        GlossaryEntry(
            "overfit.walk",
            method_label("overfit.walk"),
            _legacy_note("overfit.walk", "走样检验"),
        ),
        GlossaryEntry(
            "stability.oos",
            method_label("stability.oos"),
            method_purpose("stability.oos"),
        ),
        GlossaryEntry(
            "crowding.load",
            method_label("crowding.load"),
            _legacy_note("crowding.load", "拥挤度"),
        ),
        GlossaryEntry(
            "frozen_methods",
            "冻结验证方法",
            "验证方法按 id 与修订号冻结。改定义会生成新修订；已经跑过的研究仍引用当时那一版，不会被新展示名改写结论。",
        ),
        GlossaryEntry(
            "benchmark",
            "基准口径",
            (
                "股票默认基准是价格指数（美股标普 500、A 股沪深 300）。"
                "策略收益按复权后的总回报计算，和价格指数不是同一口径。"
                "债的基准另有约定，不要把股票这套口径套过去。"
            ),
        ),
        GlossaryEntry(
            "cost_bp",
            "成本（bp）",
            (
                f"{method_purpose('cost.turnover')}"
                f"美股按 {us_bp}bp、A 股按 {cn_bp}bp，用「年化超额 − 年化换手 × bp/10000」估算净超额。"
                "这个扣减发生在验证器里；回测收益序列本身不含逐日费用。"
                "1bp 是万分之一。"
            ),
        ),
    )


def glossary_markdown() -> str:
    lines = ["# 术语表", "", glossary_intro(), ""]
    for entry in glossary_entries():
        lines.append(f"## {entry.term}")
        lines.append("")
        lines.append(entry.body)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_glossary(root: Path) -> None:
    path = root / "docs" / "GLOSSARY.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(glossary_markdown(), encoding="utf-8")
