# Skill and HTTP name OHLCV rejection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Overnight-lab Skill forbids `alphaloop fetch` as ingest, and `POST /v1/datasets` returns `ohlcv` for bar-table CSV.

**Architecture:** Skill copy plus an HTTP test on the existing `cache_dataset_bytes` rejection. No ingest-logic change unless the HTTP path regresses.

**Tech Stack:** pytest, urllib, packaged Skill markdown.

**Spec:** `docs/requirements/2026-08-20-skill-ohlcv.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not change `fetch_data` I/O. Do not convert OHLCV to wide close-only. No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs. Do not restyle chrome.

---

### Task 1: Skill + HTTP lock

**Files:**
- Modify: `src/alphaloop/skills/overnight-lab/SKILL.md`
- Modify: `docs/webui.md` (one sentence)
- Test: `tests/skills/test_overnight_lab_skill.py`, `tests/runtime/test_http.py`

- [ ] **Step 1: Failing tests**

Add to `tests/skills/test_overnight_lab_skill.py`:

```python
def test_skill_forbids_fetch_as_overnight_ingest():
    text = _skill_text().lower()
    assert "alphaloop fetch" in text
    assert "heritage" in text
    assert "ohlcv" in text
    assert "alphaloop dataset" in text
```

Add to `tests/runtime/test_http.py` after the wide CSV upload test:

```python
def test_http_dataset_upload_rejects_ohlcv_without_a_job(tmp_path):
    import pandas as pd

    store = JobStore(tmp_path / "state.db", tmp_path)
    api = JobAPI(store, Supervisor(store, tmp_path, FakeWorker()), tmp_path)
    server = start_http_server(api, DEFAULT_HOST, 0)
    host, port = server.server_address[:2]
    idx = pd.bdate_range("2018-01-01", periods=5)
    frame = pd.DataFrame(
        {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1_000_000,
        },
        index=idx,
    )
    blob = frame.to_csv().encode("utf-8")
    try:
        req = Request(
            f"http://{host}:{port}/v1/datasets",
            data=blob,
            headers={"Content-Type": "text/csv"},
            method="POST",
        )
        with pytest.raises(HTTPError) as exc:
            urlopen(req)
        assert exc.value.code == 400
        err = exc.value.read().decode("utf-8").lower()
        assert "ohlcv" in err
        assert "found" not in err
        assert api.list_jobs()["jobs"] == []
    finally:
        server.shutdown()
```

- [ ] **Step 2: FAIL**

```bash
python3 -m pytest tests/skills/test_overnight_lab_skill.py::test_skill_forbids_fetch_as_overnight_ingest tests/runtime/test_http.py::test_http_dataset_upload_rejects_ohlcv_without_a_job -v
```

Expected: FAIL (skill missing fetch/ohlcv). HTTP may already pass if ingest is wired.

- [ ] **Step 3: Implement**

Skill Forbidden (or Workflow step 3): do not use `alphaloop fetch` as
overnight ingest; it is heritage per-symbol OHLCV; cache parquet or
wide close-only CSV with `alphaloop dataset`.

`docs/webui.md` dataset picker sentence: per-symbol OHLCV is rejected.

If HTTP test fails, fix only the error path (should already propagate).

- [ ] **Step 4: PASS**

```bash
python3 -m pytest tests/skills/test_overnight_lab_skill.py tests/runtime/test_http.py::test_http_dataset_upload_caches_csv_without_a_job tests/runtime/test_http.py::test_http_dataset_upload_rejects_ohlcv_without_a_job tests/runtime/test_cli_jobs.py::test_dataset_rejects_ohlcv_csv -v
```

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/skills/overnight-lab/SKILL.md docs/webui.md tests/skills/test_overnight_lab_skill.py tests/runtime/test_http.py docs/plans/2026-08-20-skill-ohlcv.md
git commit -m "feat(skills): forbid alphaloop fetch as overnight ingest"
```
