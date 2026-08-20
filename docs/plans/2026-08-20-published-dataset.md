# Published example dataset YAML Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Published getting-started YAML declares `ds_example` like Load example, and the CLI list shows `alphaloop dataset`.

**Architecture:** Docs-only. Same hash lock as `EXAMPLE_SPEC`. Tests compute `hash_bytes` of the packaged parquet.

**Tech Stack:** pytest static reads of `README.md` and `docs/index.md`.

**Spec:** `docs/requirements/2026-08-20-published-dataset.md`

## Global Constraints

- Do not invent `FOUND`. Do not change Help / `HOST_CONSTRAINT` / EXAMPLE_SPEC.
- Do not auto-submit. No FakeWorker in morning e2e. Do not unfreeze `webui/`.
- Do not shrink DSR `N`. Do not start soak jobs. Do not restyle console chrome.

---

### Task 1: Published YAML + CLI list

**Files:**
- Modify: `README.md`, `docs/index.md`
- Test: `tests/test_package_identity.py`

- [ ] **Step 1: Failing tests**

Add to `tests/test_package_identity.py`:

```python
def test_published_example_yaml_declares_example_dataset():
    from importlib.resources import files

    from alphaloop.contracts.artifacts import hash_bytes

    digest = hash_bytes(
        files("alphaloop.runtime.example_dataset")
        .joinpath("prices.parquet")
        .read_bytes()
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    home = (ROOT / "docs" / "index.md").read_text(encoding="utf-8")
    for text in (readme, home):
        assert "dataset_id: ds_example" in text
        assert f"sha256: {digest}" in text
        assert "alphaloop dataset" in text
    assert "If the spec declares a dataset" not in readme
    assert "A spec must declare a content-addressed `dataset`" in readme
```

Keep `test_published_home_is_overnight_lab`. It may also assert
`alphaloop dataset` in `docs/index.md`.

- [ ] **Step 2: FAIL**

```bash
python3 -m pytest tests/test_package_identity.py::test_published_example_yaml_declares_example_dataset -v
```

Expected: FAIL (`dataset_id: ds_example` missing).

- [ ] **Step 3: Implement**

Append to both YAML fences:

```yaml
dataset:
  dataset_id: ds_example
  sha256: 03796e74d7eed2595bc882cd345ae7967b1622848a618e437e0847d7bc66bc55
```

Use the digest already locked in `EXAMPLE_SPEC` / the packaged parquet
(do not invent a new hash). Confirm with:

```bash
python3 -c "from importlib.resources import files; from alphaloop.contracts.artifacts import hash_bytes; print(hash_bytes(files('alphaloop.runtime.example_dataset').joinpath('prices.parquet').read_bytes()))"
```

`docs/index.md` quick-start bash (the list that already has preview):

```bash
alphaloop dataset prices.parquet
alphaloop preview --spec spec.yaml
alphaloop submit --spec spec.yaml
```

`README.md` bash list: add `alphaloop dataset PATH` before preview.

Replace README optional-dataset paragraph with:

```
A spec must declare a content-addressed `dataset`. `alphaloop start`
installs the packaged `ds_example` snapshot so the example YAML can
preview. Cache any other parquet with `alphaloop dataset PATH`. Missing
or mismatched snapshots do not synthesize prices.
```

Optional one-line note under the YAML: the example `dataset` matches
Load example; start copies those bytes.

- [ ] **Step 4: Tests pass**

```bash
python3 -m pytest tests/test_package_identity.py::test_published_example_yaml_declares_example_dataset tests/test_package_identity.py::test_published_home_is_overnight_lab tests/runtime/test_static_console.py::test_packaged_example_dataset_matches_load_example_hash -v
```

- [ ] **Step 5: Commit**

```bash
git commit -m "docs: declare ds_example in published getting-started YAML"
```
