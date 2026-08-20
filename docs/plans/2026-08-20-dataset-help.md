# Dataset help names parquet or CSV Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `alphaloop dataset --help` and published getting-started name parquet or wide close-only CSV and pasteable `dataset:` YAML.

**Architecture:** Argparse help strings plus README / `docs/index.md` prose. No cache or receipt logic changes.

**Tech Stack:** pytest `create_parser` / `--help` capture; static reads of README and `docs/index.md`.

**Spec:** `docs/requirements/2026-08-20-dataset-help.md`

## Global Constraints

- Do not invent `FOUND`. Do not create a job. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not change `--json` keys or cache identity. No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs. Do not restyle chrome. Do not change heritage `alphaloop fetch`.

---

### Task 1: Help + published prose

**Files:**
- Modify: `src/alphaloop/cli/jobs.py` (dataset parser help)
- Modify: `README.md`, `docs/index.md`
- Test: `tests/runtime/test_cli_jobs.py`, `tests/test_package_identity.py`

- [ ] **Step 1: Failing tests**

Add to `tests/runtime/test_cli_jobs.py`:

```python
def test_dataset_help_names_csv_and_no_job(capsys):
    parser = create_parser()
    try:
        parser.parse_args(["dataset", "--help"])
    except SystemExit as exc:
        assert exc.code == 0
    out = capsys.readouterr().out.lower()
    assert "csv" in out
    assert "parquet" in out
    assert "does not create a job" in out
```

Add to `tests/test_package_identity.py` (keep existing
`test_published_example_yaml_declares_example_dataset`):

```python
def test_published_dataset_path_names_csv_and_pasteable_yaml():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    home = (ROOT / "docs" / "index.md").read_text(encoding="utf-8")
    for text in (readme, home):
        assert "wide close-only CSV" in text
        assert "pasteable" in text.lower()
        assert "dataset:" in text
    assert "Cache any other parquet with" not in readme
```

- [ ] **Step 2: FAIL**

```bash
python3 -m pytest tests/runtime/test_cli_jobs.py::test_dataset_help_names_csv_and_no_job tests/test_package_identity.py::test_published_dataset_path_names_csv_and_pasteable_yaml -v
```

Expected: FAIL (help parquet-only; README "Cache any other parquet").

- [ ] **Step 3: Implement**

In `src/alphaloop/cli/jobs.py`, dataset parser:

```python
    dataset = subparsers.add_parser(
        "dataset",
        help="cache a local parquet or wide close-only CSV (does not create a job)",
    )
    dataset.add_argument(
        "path",
        type=Path,
        help="local parquet or wide close-only CSV",
    )
```

`README.md` prose near the example YAML: cache parquet **or** a wide
close-only CSV; stdout is pasteable `dataset:` YAML. Getting-started
comment: parquet or CSV; pasteable YAML; no job.

`docs/index.md` quick-start: same two shapes + pasteable `dataset:`
YAML. Keep `alphaloop dataset` in the bash list.

- [ ] **Step 4: PASS**

```bash
python3 -m pytest tests/runtime/test_cli_jobs.py::test_dataset_help_names_csv_and_no_job tests/test_package_identity.py::test_published_example_yaml_declares_example_dataset tests/test_package_identity.py::test_published_dataset_path_names_csv_and_pasteable_yaml tests/runtime/test_cli_jobs.py::test_dataset_caches_parquet_without_daemon tests/runtime/test_cli_jobs.py::test_dataset_caches_wide_csv_without_daemon -v
```

- [ ] **Step 5: Commit**

```bash
git add src/alphaloop/cli/jobs.py README.md docs/index.md tests/runtime/test_cli_jobs.py tests/test_package_identity.py docs/plans/2026-08-20-dataset-help.md
git commit -m "feat(cli): advertise parquet or CSV on alphaloop dataset help"
```
