"""Locked glossary terms are final English. They must not carry the placeholder marker."""

from __future__ import annotations

import json
from pathlib import Path

from engine.i18n.conventions import placeholder_marker

ROOT = Path(__file__).resolve().parents[1]
GLOSSARY_MD = ROOT / "docs" / "requirements" / "i18n-glossary-v1.md"
GLOSSARY_JSON = ROOT / "apps" / "desktop" / "src" / "i18n" / "locked-glossary.json"

KEY_BY_ZH = {
    "策略族": "strategyFamily",
    "低波": "lowVolatility",
    "股债再平衡": "stockBondRebalance",
    "均值回归": "meanReversion",
    "基本面因子": "fundamentalFactor",
    "全天候": "allWeather",
    "四道门禁": "fourGates",
    "数据覆盖": "dataCoverage",
    "验证": "verification",
    "待确认清空": "noPendingConfirmations",
    "时点一致性": "pointInTimeConsistency",
    "未经许可": "unlicensed",
    "待选择": "notSelected",
    "尚未对接": "notYetSupported",
    "幸存者偏差": "survivorshipBias",
    "时点数据": "pointInTime",
    "数据血缘": "dataLineage",
    "数据指纹": "dataFingerprint",
    "试验轮数": "trialCount",
    "确认卡": "confirmationCard",
    "策略包": "strategyPack",
    "研究记录": "researchRecord",
    "A 股": "chinaAShares",
    "可开跑 / 开跑就绪": "readyToRun",
    "开跑": "run",
    "知情确认": "acknowledgment",
    "股票池": "universe",
    "口径": "dataBasis",
    "PIT 可能不通过": "mayFailPit",
    "技术详情": "technicalDetails",
    "生成语言未记录": "languageNotRecorded",
    "分段稳健性检验": "subperiodRobustness",
    "集中度": "concentration",
    "样本外稳定": "outOfSampleStability",
}


def _table_rows() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in GLOSSARY_MD.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2 or cells[0] in {"中文", "---"} or cells[0].startswith("-"):
            continue
        rows.append((cells[0], cells[1]))
    return rows


def test_locked_glossary_json_matches_the_spec_and_has_no_placeholder() -> None:
    rows = _table_rows()
    payload = json.loads(GLOSSARY_JSON.read_text(encoding="utf-8"))
    marker = placeholder_marker()
    assert [zh for zh, _en in rows] == list(KEY_BY_ZH)
    assert set(payload) == set(KEY_BY_ZH.values())
    for zh, en in rows:
        entry = payload[KEY_BY_ZH[zh]]
        assert entry["zh"] == zh
        assert entry["en"] == en
        assert marker not in entry["en"]
        assert marker not in entry["zh"]
