# CLI dataset pasteable YAML receipt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `alphaloop dataset` human stdout is pasteable `dataset:` YAML plus Cached and the locked no-alpha line.

**Architecture:** Change `format_dataset_receipt` only. `--json` unchanged. No job created.

**Tech Stack:** pytest, existing CLI `run_dataset`.

**Spec:** `docs/requirements/2026-08-20-dataset-yaml.md`

## Global Constraints

- Do not invent `FOUND`. Do not create a job. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not change `--json` keys. No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs. Do not restyle chrome.

---

### Task 1: Receipt YAML

**Files:**
- Modify: `src/alphaloop/runtime/dataset_cache.py` (`format_dataset_receipt`)
- Modify: `docs/cli.md`, `src/alphaloop/skills/overnight-lab/SKILL.md`
- Test: `tests/runtime/test_cli_jobs.py`, `tests/runtime/test_dataset_cache.py`

- [x] **Step 1: Failing tests**

Update `test_dataset_caches_parquet_without_daemon` expected lines:

```python
    assert captured.out.splitlines() == [
        "dataset:",
        f"  dataset_id: {dataset_id}",
        f"  sha256: {digest}",
        f"Cached: {cached}",
        DATASET_NO_ALPHA,
    ]
```

Add:

```python
def test_format_dataset_receipt_is_pasteable_yaml():
    from alphaloop.runtime.dataset_cache import DATASET_NO_ALPHA, format_dataset_receipt

    text = format_dataset_receipt(
        dataset_id="ds_abc",
        sha256="deadbeef",
        cached_path="/tmp/prices.parquet",
    )
    assert text.splitlines() == [
        "dataset:",
        "  dataset_id: ds_abc",
        "  sha256: deadbeef",
        "Cached: /tmp/prices.parquet",
        DATASET_NO_ALPHA,
    ]
    assert "FOUND" not in text
```

CSV CLI test: `assert "dataset_id: ds_" in captured.out` (replace startswith if needed).

- [x] **Step 2: FAIL**

```bash
python3 -m pytest tests/runtime/test_cli_jobs.py::test_dataset_caches_parquet_without_daemon tests/runtime/test_dataset_cache.py::test_format_dataset_receipt_is_pasteable_yaml -v
```

- [x] **Step 3: Implement**

```python
def format_dataset_receipt(
    *, dataset_id: str, sha256: str, cached_path: str
) -> str:
    return (
        "\n".join(
            [
                "dataset:",
                f"  dataset_id: {dataset_id}",
                f"  sha256: {sha256}",
                f"Cached: {cached_path}",
                DATASET_NO_ALPHA,
            ]
        )
        + "\n"
    )
```

Docs: default stdout is pasteable `dataset:` YAML, then `Cached:`, then the no-alpha sentence. Skill: paste that block into the spec.

- [x] **Step 4: Tests pass**

```bash
python3 -m pytest tests/runtime/test_cli_jobs.py::test_dataset_caches_parquet_without_daemon tests/runtime/test_cli_jobs.py::test_dataset_json_payload tests/runtime/test_cli_jobs.py::test_dataset_caches_wide_csv_without_daemon tests/runtime/test_dataset_cache.py::test_format_dataset_receipt_is_pasteable_yaml -v
```

- [x] **Step 5: Commit**

```bash
git commit -m "feat(cli): print pasteable dataset YAML from alphaloop dataset"
```
