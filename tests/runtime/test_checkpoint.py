from __future__ import annotations

from alphaloop.contracts.artifacts import RunLayout
from alphaloop.runtime.checkpoint import (
    Checkpoint,
    load_latest_complete,
    read_heartbeat,
    write_checkpoint,
    write_heartbeat,
)


def test_write_and_load_latest_complete(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.checkpoints.mkdir(parents=True)
    write_checkpoint(layout, Checkpoint(seq=1, complete=True, payload={"step": "n1"}))
    write_checkpoint(layout, Checkpoint(seq=2, complete=False, payload={"step": "n2"}))
    write_checkpoint(layout, Checkpoint(seq=3, complete=True, payload={"step": "n3"}))
    latest = load_latest_complete(layout)
    assert latest is not None
    assert latest.seq == 3
    assert latest.payload == {"step": "n3"}


def test_incomplete_only_yields_none(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.checkpoints.mkdir(parents=True)
    write_checkpoint(layout, Checkpoint(seq=1, complete=False, payload={}))
    assert load_latest_complete(layout) is None


def test_partial_tmp_file_is_ignored(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.checkpoints.mkdir(parents=True)
    write_checkpoint(layout, Checkpoint(seq=1, complete=True, payload={"ok": True}))
    (layout.checkpoints / "ckpt-2.json.tmp").write_text("{not-json", encoding="utf-8")
    latest = load_latest_complete(layout)
    assert latest is not None
    assert latest.seq == 1


def test_heartbeat_round_trip(tmp_path):
    layout = RunLayout(tmp_path / "run")
    layout.run_dir.mkdir(parents=True)
    write_heartbeat(layout, pid=99, at="2026-08-19T00:00:00+00:00")
    assert read_heartbeat(layout) == {"pid": 99, "at": "2026-08-19T00:00:00+00:00"}
