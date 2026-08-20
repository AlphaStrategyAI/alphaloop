# Fetch help is heritage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `alphaloop fetch --help` says heritage per-symbol OHLCV, not overnight dataset ingest.

**Architecture:** Argparse `help` / `description` plus a short `docs/cli.md` heritage section. `fetch_data` unchanged.

**Tech Stack:** argparse, pytest `create_parser`.

**Spec:** `docs/requirements/2026-08-20-fetch-heritage.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not change `fetch_data` I/O. Do not convert OHLCV to wide close-only. No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs. Do not restyle chrome.

---

### Task 1: Help + cli.md

**Files:**
- Modify: `src/alphaloop/cli/main.py` (fetch parser)
- Modify: `docs/cli.md`
- Test: `tests/test_package_identity.py`

- [ ] **Step 1: Failing tests**

Add to `tests/test_package_identity.py`:

```python
def test_fetch_help_is_heritage_not_overnight_dataset(capsys):
    parser = create_parser()
    try:
        parser.parse_args(["fetch", "--help"])
    except SystemExit as exc:
        assert exc.code == 0
    out = capsys.readouterr().out.lower()
    assert "heritage" in out
    assert "ohlcv" in out
    assert "dataset" in out
    assert "获取数据" not in capsys.readouterr().out
    parent = parser.format_help().lower()
    assert "heritage" in parent
```

Do not assert `获取数据` via a second `readouterr` after the first
already consumed stdout. Assert on `out` only:

```python
    assert "heritage" in out
    assert "ohlcv" in out
    assert "dataset" in out
    parent = parser.format_help().lower()
    assert "fetch" in parent
    # fetch one-liner
    assert "heritage" in parent
```

`create_parser().format_help()` includes all subparser helps, including
loop's heritage. Tighten: parse parent help for the fetch line, or
call `fetch --help` only and also:

```python
    top = create_parser().format_help()
    assert "heritage per-symbol" in top.lower() or "heritage per-symbol ohlcv" in top.lower()
```

Simplest lock:

```python
def test_fetch_help_is_heritage_not_overnight_dataset(capsys):
    parser = create_parser()
    try:
        parser.parse_args(["fetch", "--help"])
    except SystemExit as exc:
        assert exc.code == 0
    out = capsys.readouterr().out.lower()
    assert "heritage" in out
    assert "ohlcv" in out
    assert "dataset" in out
    assert "获取数据" not in out
    assert "found" not in out
    parent = parser.format_help().lower()
    assert "heritage per-symbol ohlcv" in parent
```

- [ ] **Step 2: FAIL**

```bash
python3 -m pytest tests/test_package_identity.py::test_fetch_help_is_heritage_not_overnight_dataset -v
```

Expected: FAIL (`heritage` missing).

- [ ] **Step 3: Implement**

In `src/alphaloop/cli/main.py`:

```python
    fetch_parser = subparsers.add_parser(
        "fetch",
        help="heritage per-symbol OHLCV download (not overnight dataset ingest)",
        description=(
            "Heritage per-symbol OHLCV download. Not the overnight-lab "
            "snapshot path; use alphaloop dataset with parquet or wide "
            "close-only CSV. Does not claim alpha."
        ),
    )
```

Leave fetch flags and `fetch_data` unchanged.

`docs/cli.md`: add `## alphaloop fetch (heritage)` after the loop
section. Overnight-lab lead list unchanged.

- [ ] **Step 4: PASS**

```bash
python3 -m pytest tests/test_package_identity.py::test_fetch_help_is_heritage_not_overnight_dataset tests/test_package_identity.py::test_loop_help_is_heritage_not_find_alpha tests/test_cli.py::test_cli_fetch_calls_yahoo tests/test_cli.py::test_cli_help_exits_cleanly -v
```

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/cli/main.py docs/cli.md tests/test_package_identity.py docs/plans/2026-08-20-fetch-heritage.md
git commit -m "feat(cli): mark alphaloop fetch help as heritage OHLCV"
```
