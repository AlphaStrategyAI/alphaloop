from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys

import pytest

from alphaloop.runtime.client import JobClient
from alphaloop.runtime.daemon import spawn_detached_daemon
from tests.runtime.test_supervisor import _cached_spec


def test_submit_survives_parent_exit(tmp_path):
    meta = spawn_detached_daemon(tmp_path, "127.0.0.1", 0)
    try:
        client = JobClient(f"http://{meta['host']}:{meta['port']}")
        child = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import json, sys; "
                    "from alphaloop.contracts.research_spec import ResearchSpec; "
                    "from alphaloop.runtime.client import JobClient; "
                    "spec = ResearchSpec.from_dict(json.loads(sys.argv[2])); "
                    "print(JobClient(sys.argv[1]).create_run(spec)['run_id'])"
                ),
                client.base_url,
                json.dumps(_cached_spec().to_dict()),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        run_id = child.stdout.strip()
        fetched = client.get_run(run_id)
        assert fetched["run_id"] == run_id
    finally:
        os.kill(meta["pid"], signal.SIGTERM)


def test_detached_start_fails_when_child_cannot_bind(tmp_path):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as blocker:
        blocker.bind(("127.0.0.1", 0))
        blocker.listen()
        port = blocker.getsockname()[1]

        with pytest.raises(RuntimeError):
            spawn_detached_daemon(tmp_path, "127.0.0.1", port)

    assert not (tmp_path / ".alphaloop" / "daemon.json").exists()
