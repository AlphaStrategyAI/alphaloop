# CLI dataset cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `alphaloop dataset PATH` caches parquet into `{data_dir}/datasets/ds_<sha16>/prices.parquet` without creating a job or inventing `FOUND`.

**Architecture:** Offline `put_dataset_bytes` (same writer as `POST /v1/datasets`). No daemon. Four-line receipt plus `--json`. Fail closed with exit 2.

**Tech Stack:** argparse, `dataset_cache.put_dataset_bytes`, pytest.

**Spec:** `docs/requirements/2026-08-20-cli-dataset.md`

## Global Constraints

- Do not invent `FOUND`. Do not create a job. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not change `POST /v1/datasets` or the console file picker. No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs. Do not restyle console chrome.

---

### Task 1: `alphaloop dataset PATH`

**Files:**
- Modify: `src/alphaloop/runtime/dataset_cache.py` (receipt helper)
- Modify: `src/alphaloop/cli/jobs.py` (parser + `run_dataset`)
- Modify: `src/alphaloop/cli/main.py` (dispatch `dataset`)
- Modify: `docs/cli.md`, `src/alphaloop/skills/overnight-lab/SKILL.md`
- Test: `tests/runtime/test_cli_jobs.py`

**Interfaces:**
- Consumes: `put_dataset_bytes(data_dir, blob) -> DatasetRef`, `dataset_parquet_path(data_dir, dataset_id) -> Path`, `DatasetRejected`
- Produces: `format_dataset_receipt(*, dataset_id: str, sha256: str, cached_path: str) -> str` ending in newline; `DATASET_NO_ALPHA` locked sentence; `run_dataset(args) -> int`

- [ ] **Step 1: Failing tests**

Add to `tests/runtime/test_cli_jobs.py`:

```python
def test_parser_has_dataset_command():
    parser = create_parser()
    assert "dataset" in parser.format_help()


def test_dataset_caches_parquet_without_daemon(tmp_path, capsys):
    from alphaloop.contracts.artifacts import hash_bytes
    from alphaloop.runtime.dataset_cache import (
        DATASET_NO_ALPHA,
        dataset_parquet_path,
    )
    from alphaloop.runtime.example_dataset import example_dataset_bytes

    blob = example_dataset_bytes()
    src = tmp_path / "prices.parquet"
    src.write_bytes(blob)
    rc = main(["dataset", str(src), "--data-dir", str(tmp_path)])
    captured = capsys.readouterr()
    assert rc == 0
    digest = hash_bytes(blob)
    dataset_id = "ds_" + digest[:16]
    cached = dataset_parquet_path(tmp_path, dataset_id)
    assert cached.read_bytes() == blob
    assert captured.out.splitlines() == [
        f"dataset_id: {dataset_id}",
        f"sha256: {digest}",
        f"Cached: {cached}",
        DATASET_NO_ALPHA,
    ]
    assert "FOUND" not in captured.out
    assert captured.err == ""


def test_dataset_json_payload(tmp_path, capsys):
    from alphaloop.contracts.artifacts import hash_bytes
    from alphaloop.runtime.dataset_cache import dataset_parquet_path
    from alphaloop.runtime.example_dataset import example_dataset_bytes

    blob = example_dataset_bytes()
    src = tmp_path / "prices.parquet"
    src.write_bytes(blob)
    rc = main(["dataset", str(src), "--data-dir", str(tmp_path), "--json"])
    captured = capsys.readouterr()
    assert rc == 0
    digest = hash_bytes(blob)
    dataset_id = "ds_" + digest[:16]
    payload = json.loads(captured.out)
    assert payload == {
        "cached_path": str(dataset_parquet_path(tmp_path, dataset_id)),
        "dataset_id": dataset_id,
        "sha256": digest,
    }
    assert "research_outcome" not in payload
    assert "FOUND" not in captured.out


def test_dataset_missing_file(tmp_path, capsys):
    missing = tmp_path / "missing.parquet"
    rc = main(["dataset", str(missing), "--data-dir", str(tmp_path)])
    captured = capsys.readouterr()
    assert rc == 2
    assert captured.err == f"error: dataset file not found: {missing}\n"
    assert "FOUND" not in captured.out


def test_dataset_rejects_non_parquet(tmp_path, capsys):
    src = tmp_path / "notes.txt"
    src.write_text("not parquet", encoding="utf-8")
    rc = main(["dataset", str(src), "--data-dir", str(tmp_path)])
    captured = capsys.readouterr()
    assert rc == 2
    assert captured.err.startswith("error: ")
    assert "parquet" in captured.err
    assert "FOUND" not in captured.out
```

Also extend `test_parser_has_runtime_commands` with `assert "dataset" in parser.format_help()`.

- [ ] **Step 2: FAIL**

```bash
python3 -m pytest tests/runtime/test_cli_jobs.py::test_parser_has_dataset_command tests/runtime/test_cli_jobs.py::test_dataset_caches_parquet_without_daemon tests/runtime/test_cli_jobs.py::test_dataset_missing_file -v
```

Expected: FAIL (`dataset` not in help / unknown command).

- [ ] **Step 3: Implement**

In `src/alphaloop/runtime/dataset_cache.py`:

```python
DATASET_NO_ALPHA = (
    "This cache does not claim alpha or future profitability."
)


def format_dataset_receipt(
    *, dataset_id: str, sha256: str, cached_path: str
) -> str:
    return (
        "\n".join(
            [
                f"dataset_id: {dataset_id}",
                f"sha256: {sha256}",
                f"Cached: {cached_path}",
                DATASET_NO_ALPHA,
            ]
        )
        + "\n"
    )
```

In `src/alphaloop/cli/jobs.py` `register`:

```python
    dataset = subparsers.add_parser(
        "dataset",
        help="cache a local parquet snapshot (does not create a job)",
    )
    dataset.add_argument("path", type=Path, help="local parquet file")
    dataset.add_argument(
        "--json",
        action="store_true",
        help="print dataset identity as JSON",
    )
    _add_data_dir(dataset)
    dataset.set_defaults(func=run_dataset)
```

`run_dataset`:

```python
def run_dataset(args: argparse.Namespace) -> int:
    from alphaloop.runtime.dataset_cache import (
        DatasetRejected,
        dataset_parquet_path,
        format_dataset_receipt,
        put_dataset_bytes,
    )

    path = Path(args.path)
    if not path.is_file():
        print(f"error: dataset file not found: {path}", file=sys.stderr)
        return 2
    try:
        blob = path.read_bytes()
        ref = put_dataset_bytes(Path(args.data_dir), blob)
    except DatasetRejected as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: unable to read dataset file: {exc}", file=sys.stderr)
        return 2
    cached = dataset_parquet_path(Path(args.data_dir), ref.dataset_id)
    if args.json:
        print(
            json.dumps(
                {
                    "cached_path": str(cached),
                    "dataset_id": ref.dataset_id,
                    "sha256": ref.sha256,
                },
                sort_keys=True,
            )
        )
        return 0
    print(
        format_dataset_receipt(
            dataset_id=ref.dataset_id,
            sha256=ref.sha256,
            cached_path=str(cached),
        ),
        end="",
    )
    return 0
```

Add `"dataset"` to the overnight command set in `src/alphaloop/cli/main.py`.

Docs: overnight-lab command list in `docs/cli.md` includes `dataset`; new section after `submit` (before `preview` is also fine — place after `preview` so the one-minute path reads preview then cache-or-submit). Place **after `preview`** and before `status`. Skill step 3: cache parquet with `alphaloop dataset PATH` when not using the packaged example; does not create a job.

`docs/cli.md` section:

```
## `alphaloop dataset`

Cache a local parquet file into `{data-dir}/datasets/<dataset_id>/prices.parquet`
using the same hash identity as the morning console picker. Does **not**
create a job and does not require the daemon.

```
alphaloop dataset PATH [--data-dir DIR] [--json]
```

Default stdout is `dataset_id:`, `sha256:`, `Cached:`, and
`This cache does not claim alpha or future profitability.`
`--json` prints `{cached_path, dataset_id, sha256}`. Missing or
invalid files exit 2 on stderr. The command does not claim alpha.
```

Skill workflow step 3 insert after start: if the spec names a local parquet other than the packaged example, run `alphaloop dataset PATH` (prints `dataset_id` / `sha256`; does not create a job), then Preview.

- [ ] **Step 4: Tests pass**

```bash
python3 -m pytest tests/runtime/test_cli_jobs.py::test_parser_has_dataset_command tests/runtime/test_cli_jobs.py::test_dataset_caches_parquet_without_daemon tests/runtime/test_cli_jobs.py::test_dataset_json_payload tests/runtime/test_cli_jobs.py::test_dataset_missing_file tests/runtime/test_cli_jobs.py::test_dataset_rejects_non_parquet tests/runtime/test_cli_jobs.py::test_parser_has_runtime_commands -v
```

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(cli): cache parquet snapshots with alphaloop dataset"
```
