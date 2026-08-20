# Console dataset CSV picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Morning `#field-dataset-file` and `POST /v1/datasets` cache a wide close-only CSV without creating a job.

**Architecture:** `JobAPI.put_dataset` uses `cache_dataset_bytes` (parquet magic or CSV convert). Picker `accept` includes `.csv`. CLI stdout unchanged.

**Tech Stack:** JobAPI, daemon POST, packaged HTML, pytest, Playwright.

**Spec:** `docs/requirements/2026-08-20-console-dataset-csv.md`

## Global Constraints

- Do not invent `FOUND`. Do not auto-submit. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not change CLI dataset receipt. No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs. Do not restyle chrome.

---

### Task 1: HTTP + picker

**Files:**
- Modify: `src/alphaloop/runtime/dataset_cache.py` (`cache_dataset_bytes`)
- Modify: `src/alphaloop/runtime/api.py` (`put_dataset`)
- Modify: `src/alphaloop/webui/static/index.html` (accept + label)
- Modify: `docs/webui.md`
- Test: `tests/runtime/test_dataset_cache.py`, `tests/runtime/test_http.py`, `tests/runtime/test_static_console.py`, `tests/e2e/test_morning_console.py`

**Interfaces:**
- Consumes: `put_dataset_bytes`, `parquet_bytes_from_csv`
- Produces: `cache_dataset_bytes(data_dir: Path, blob: bytes) -> DatasetRef`

- [ ] **Step 1: Failing tests**

```python
def test_cache_dataset_bytes_converts_wide_csv(tmp_path):
    from alphaloop.runtime.dataset_cache import cache_dataset_bytes, dataset_parquet_path

    idx = pd.bdate_range("2018-01-01", periods=5)
    frame = pd.DataFrame({"AAPL": 100.0, "MSFT": 100.0, "SPY": 100.0}, index=idx)
    blob = frame.to_csv().encode("utf-8")
    ref = cache_dataset_bytes(tmp_path, blob)
    stored = pd.read_parquet(dataset_parquet_path(tmp_path, ref.dataset_id))
    assert list(stored.columns) == ["AAPL", "MSFT", "SPY"]


def test_cache_dataset_bytes_rejects_plain_text(tmp_path):
    from alphaloop.runtime.dataset_cache import DatasetRejected, cache_dataset_bytes

    with pytest.raises(DatasetRejected, match="parquet or csv"):
        cache_dataset_bytes(tmp_path, b"not parquet")
```

HTTP: POST CSV body to `/v1/datasets` returns 201 and `list_jobs` empty.

Static: `accept` on `#field-dataset-file` contains `.csv`; label contains `CSV` or `csv`.

E2E in `test_dataset_file_picker_fills_identity_without_creating_a_job` sibling:

```python
def test_dataset_csv_picker_fills_identity_without_creating_a_job(real_daemon, browser_page, tmp_path):
    import pandas as pd

    idx = pd.bdate_range("2018-01-01", periods=20)
    frame = pd.DataFrame({"AAPL": 100.0, "MSFT": 100.0, "SPY": 100.0}, index=idx)
    csv_path = tmp_path / "prices.csv"
    frame.to_csv(csv_path)
    page = browser_page
    _open_morning(page, real_daemon["base_url"])
    page.set_input_files("#field-dataset-file", str(csv_path))
    page.wait_for_function(
        """() => {
            const id = document.getElementById('field-dataset-id');
            const sha = document.getElementById('field-dataset-sha256');
            return id && sha && id.value.startsWith('ds_') && sha.value.length === 64;
        }""",
        timeout=10000,
    )
    assert page.locator("#job-list button").count() == 0
    assert page.locator("#submit-job").is_disabled()
```

- [ ] **Step 2: FAIL**

```bash
python3 -m pytest tests/runtime/test_dataset_cache.py::test_cache_dataset_bytes_converts_wide_csv tests/runtime/test_static_console.py::test_packaged_console_dataset_csv_accept -v
```

- [ ] **Step 3: Implement**

`cache_dataset_bytes`: PAR1 → `put_dataset_bytes`; else convert CSV or `DatasetRejected("dataset snapshot must be parquet or csv")`.

`JobAPI.put_dataset` calls `cache_dataset_bytes`.

HTML: `accept=".parquet,.csv,application/octet-stream,text/csv"`; label `Dataset parquet or CSV`.

- [ ] **Step 4: Tests pass**

```bash
python3 -m pytest tests/runtime/test_dataset_cache.py tests/runtime/test_http.py::test_http_dataset_upload_caches_parquet_without_a_job tests/runtime/test_http.py::test_http_dataset_upload_caches_csv_without_a_job tests/runtime/test_static_console.py::test_packaged_console_dataset_csv_accept tests/runtime/test_dataset_upload.py -v
```

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(webui): accept wide close-only CSV in the dataset picker"
```
