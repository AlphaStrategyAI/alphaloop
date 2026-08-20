# CLI dataset wide CSV Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `alphaloop dataset PATH` caches a wide close-only CSV as the same parquet snapshot as a native parquet file.

**Architecture:** `cache_dataset_file` converts `.csv` → parquet bytes, then `put_dataset_bytes`. HTTP upload stays parquet-only. Receipt unchanged.

**Tech Stack:** pandas, argparse, pytest.

**Spec:** `docs/requirements/2026-08-20-dataset-csv.md`

## Global Constraints

- Do not invent `FOUND`. Do not create a job. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not change `POST /v1/datasets`. No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs. Do not fetch the network.

---

### Task 1: CSV → parquet cache

**Files:**
- Modify: `src/alphaloop/runtime/dataset_cache.py`
- Modify: `src/alphaloop/cli/jobs.py` (`run_dataset` calls `cache_dataset_file`)
- Modify: `docs/cli.md`, `src/alphaloop/skills/overnight-lab/SKILL.md`
- Test: `tests/runtime/test_dataset_cache.py`, `tests/runtime/test_cli_jobs.py`

**Interfaces:**
- Consumes: `put_dataset_bytes(data_dir, blob) -> DatasetRef`
- Produces: `cache_dataset_file(data_dir: Path, path: Path) -> DatasetRef`

- [ ] **Step 1: Failing tests**

Add to `tests/runtime/test_dataset_cache.py`:

```python
def test_cache_dataset_file_converts_wide_csv(tmp_path):
    from alphaloop.runtime.dataset_cache import cache_dataset_file, dataset_parquet_path

    idx = pd.bdate_range("2018-01-01", periods=5)
    frame = pd.DataFrame(
        {"AAPL": 100.0, "MSFT": 100.0, "SPY": 100.0},
        index=idx,
    )
    src = tmp_path / "prices.csv"
    frame.to_csv(src)
    ref = cache_dataset_file(tmp_path, src)
    stored = pd.read_parquet(dataset_parquet_path(tmp_path, ref.dataset_id))
    assert list(stored.columns) == ["AAPL", "MSFT", "SPY"]
    assert len(stored) == 5


def test_cache_dataset_file_rejects_plain_text(tmp_path):
    from alphaloop.runtime.dataset_cache import DatasetRejected, cache_dataset_file

    src = tmp_path / "notes.txt"
    src.write_text("not a snapshot", encoding="utf-8")
    with pytest.raises(DatasetRejected, match="parquet or csv"):
        cache_dataset_file(tmp_path, src)
```

Add to `tests/runtime/test_cli_jobs.py`:

```python
def test_dataset_caches_wide_csv_without_daemon(tmp_path, capsys):
    import pandas as pd

    idx = pd.bdate_range("2018-01-01", periods=5)
    frame = pd.DataFrame(
        {"AAPL": 100.0, "MSFT": 100.0, "SPY": 100.0},
        index=idx,
    )
    src = tmp_path / "prices.csv"
    frame.to_csv(src)
    rc = main(["dataset", str(src), "--data-dir", str(tmp_path)])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.startswith("dataset_id: ds_")
    assert "FOUND" not in captured.out
    assert captured.err == ""


def test_dataset_rejects_unreadable_csv(tmp_path, capsys):
    src = tmp_path / "broken.csv"
    src.write_text("this is not tabular\n{{{", encoding="utf-8")
    rc = main(["dataset", str(src), "--data-dir", str(tmp_path)])
    captured = capsys.readouterr()
    assert rc == 2
    assert "csv" in captured.err
    assert "FOUND" not in captured.out
```

Existing `test_dataset_rejects_non_parquet` must still pass (`parquet` in stderr).

- [ ] **Step 2: FAIL**

```bash
python3 -m pytest tests/runtime/test_dataset_cache.py::test_cache_dataset_file_converts_wide_csv tests/runtime/test_cli_jobs.py::test_dataset_caches_wide_csv_without_daemon -v
```

Expected: FAIL (`cache_dataset_file` not defined / CSV rejected as parquet).

- [ ] **Step 3: Implement**

In `dataset_cache.py`:

```python
import io


def parquet_bytes_from_csv(blob: bytes) -> bytes:
    try:
        frame = pd.read_csv(io.BytesIO(blob), index_col=0)
        if frame.empty or frame.shape[1] == 0:
            raise DatasetRejected("dataset snapshot is empty")
        frame.index = pd.to_datetime(frame.index)
        frame = frame.apply(pd.to_numeric)
        buf = io.BytesIO()
        frame.to_parquet(buf)
        out = buf.getvalue()
    except DatasetRejected:
        raise
    except (OSError, ValueError, TypeError, pd.errors.ParserError) as exc:
        raise DatasetRejected("dataset snapshot csv is unreadable") from exc
    if not out.startswith(PARQUET_MAGIC):
        raise DatasetRejected("dataset snapshot must be parquet")
    return out


def cache_dataset_file(data_dir: Path, path: Path) -> DatasetRef:
    blob = Path(path).read_bytes()
    if blob.startswith(PARQUET_MAGIC):
        return put_dataset_bytes(data_dir, blob)
    if Path(path).suffix.lower() == ".csv":
        return put_dataset_bytes(data_dir, parquet_bytes_from_csv(blob))
    raise DatasetRejected("dataset snapshot must be parquet or csv")
```

`run_dataset`: replace `put_dataset_bytes(Path(args.data_dir), blob)` with
`cache_dataset_file(Path(args.data_dir), path)` (do not `read_bytes` twice;
`cache_dataset_file` reads the file). Keep the not-a-file branch.

Docs: `docs/cli.md` — PATH may be parquet or a wide close-only CSV
(DatetimeIndex, columns = asset ids). Skill: `alphaloop dataset PATH`
accepts that CSV shape; does not create a job.

- [ ] **Step 4: Tests pass**

```bash
python3 -m pytest tests/runtime/test_dataset_cache.py tests/runtime/test_cli_jobs.py::test_dataset_caches_parquet_without_daemon tests/runtime/test_cli_jobs.py::test_dataset_caches_wide_csv_without_daemon tests/runtime/test_cli_jobs.py::test_dataset_rejects_non_parquet tests/runtime/test_cli_jobs.py::test_dataset_rejects_unreadable_csv tests/runtime/test_dataset_upload.py -v
```

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(cli): cache wide close-only CSV via alphaloop dataset"
```
