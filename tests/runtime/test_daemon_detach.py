from __future__ import annotations

import os
import signal
import time

from alphaloop.runtime.client import JobClient
from alphaloop.runtime.daemon import spawn_detached_daemon
from tests.runtime.test_supervisor import _spec


def test_submit_survives_parent_exit(tmp_path):
    meta = spawn_detached_daemon(tmp_path, "127.0.0.1", 0)
    try:
        client = JobClient(f"http://{meta['host']}:{meta['port']}")
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                client.healthz()
                break
            except Exception:
                time.sleep(0.1)
        else:
            raise AssertionError("daemon did not start")
        created = client.create_run(_spec())
        os.kill(os.getpid(), 0)  # parent still here; job must already be persisted
        fetched = client.get_run(created["run_id"])
        assert fetched["run_id"] == created["run_id"]
    finally:
        os.kill(meta["pid"], signal.SIGTERM)
