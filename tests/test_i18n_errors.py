"""Error-code envelope: legacy sentence kept, params and detail added, redactor reserved."""

from __future__ import annotations

import json
from pathlib import Path

from engine.i18n.conventions import error_code_catalog, placeholder_marker
from engine.i18n.errors import (
    build_error_envelope,
    contact_email_missing_envelope,
    identity_redactor,
    redact_technical_detail,
    set_technical_detail_redactor,
)
from engine.research.data_errors import EmptySymbolsError
from engine.research.user_errors import UserFacingError, http_error_payload

ROOT = Path(__file__).resolve().parents[1]


def test_user_facing_error_keeps_legacy_sentence_and_adds_envelope() -> None:
    error = EmptySymbolsError()
    payload = http_error_payload(error)
    assert payload["code"] == "DATA_SYMBOLS_EMPTY"
    assert payload["error"] == error.message
    assert payload["params"] == {}
    assert payload["detail"] is None


def test_running_cannot_modify_is_one_of_the_migrated_codes() -> None:
    from engine.research.state_machine import InvalidTransition

    payload = http_error_payload(InvalidTransition("running research cannot modify"))
    assert payload["code"] == "RUNNING_CANNOT_MODIFY"
    assert payload["error"] == "研究仍在运行中，请先暂停再确认修改。"
    assert payload["params"] == {}
    assert "running research" not in payload["error"]


def test_unknown_exception_keeps_text_and_puts_it_in_detail() -> None:
    payload = http_error_payload(ValueError("error sending request for url secret"))
    assert payload["code"] == "bad_request"
    assert payload["error"] == "error sending request for url secret"
    assert payload["detail"] == "error sending request for url secret"


def test_contact_email_missing_carries_params() -> None:
    payload = contact_email_missing_envelope("Crossref / SEC 全文", detail="raw smtp")
    assert payload["code"] == "contact_email_missing"
    assert payload["params"] == {"sources": "Crossref / SEC 全文"}
    assert payload["error"].startswith("未配置联系邮箱")
    assert payload["detail"] == "raw smtp"


def test_redactor_hook_is_applied_and_defaults_to_identity() -> None:
    assert redact_technical_detail("plain") == identity_redactor("plain")

    def hide(text: str) -> str:
        return text.replace("secret-token", "[redacted]")

    previous = set_technical_detail_redactor(hide)
    try:
        payload = build_error_envelope(
            code="internal_error",
            message="服务器内部错误，请稍后重试。",
            detail="failed with secret-token",
        )
        assert payload["detail"] == "failed with [redacted]"
        assert "secret-token" not in payload["detail"]
        assert payload["error"] == "服务器内部错误，请稍后重试。"
    finally:
        set_technical_detail_redactor(previous)


def test_catalogued_codes_match_the_contract_file() -> None:
    catalog = error_code_catalog()
    disk = json.loads((ROOT / "contracts" / "error-codes.json").read_text(encoding="utf-8"))
    assert set(catalog) == set(disk)
    assert "contact_email_missing" in catalog
    assert catalog["contact_email_missing"]["params"] == ["sources"]
    assert placeholder_marker() == "data-i18n-placeholder"


def test_market_data_errors_use_the_envelope() -> None:
    from engine.research.data_availability import (
        market_data_fetch_failed,
        market_data_rate_limited,
        market_data_timeout,
    )

    timeout = http_error_payload(market_data_timeout(300))
    assert timeout["code"] == "MARKET_DATA_TIMEOUT"
    assert timeout["params"] == {"symbol_count": 300}
    assert timeout["detail"] == "TimeoutError: market data load exceeded the deadline"
    assert "300" in timeout["error"]
    assert "MARKET_DATA_TIMEOUT" in timeout["error"]

    limited = http_error_payload(market_data_rate_limited())
    assert limited["code"] == "MARKET_DATA_RATE_LIMITED"
    assert limited["params"] == {}
    assert limited["detail"]

    failed = http_error_payload(market_data_fetch_failed("002460.SZ"))
    assert failed["code"] == "MARKET_DATA_FETCH_FAILED"
    assert failed["params"] == {"symbol": "002460.SZ"}
    assert "002460.SZ" in failed["error"]


def test_user_facing_error_params_round_trip() -> None:
    error = UserFacingError("DATA_EMPTY_PRICES", "数据源未返回行情，请检查标的和网络。", params={})
    payload = http_error_payload(error)
    assert payload["params"] == {}
    assert payload["code"] == "DATA_EMPTY_PRICES"
