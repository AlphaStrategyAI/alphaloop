from __future__ import annotations

import pytest


@pytest.fixture
def browser_page():
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    playwright = sync_playwright().start()
    try:
        browser = playwright.chromium.launch(headless=True)
    except Exception as exc:  # noqa: BLE001 - skip when browsers are missing
        playwright.stop()
        pytest.skip(f"Chromium is not available: {exc}")
    page = browser.new_page()
    try:
        yield page
    finally:
        browser.close()
        playwright.stop()
