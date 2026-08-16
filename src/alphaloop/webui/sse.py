"""SSE (Server-Sent Events) generator for the v0.7.1 WebUI.

The frontend opens `new EventSource('/api/runs/<rid>/stream')` and
consumes progressively-emitted progress events. We poll
``runs/<rid>/progress.json`` every 1 second (design doc § 3.4) and
yield SSE events.

For runs that have already completed, the generator emits a single
``complete`` event and exits immediately.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import AsyncIterator


async def stream_run(run_dir: Path) -> AsyncIterator[dict]:
    """Yield SSE-shaped events for a (possibly in-flight) run.

    Each event is a dict with keys ``kind`` ('event' or 'comment') and
    ``event`` / ``data`` as appropriate. The caller wraps this in
    :class:`fastapi.responses.StreamingResponse`.
    """
    progress_file = run_dir / "progress.json"
    manifest_file = run_dir / "manifest.yaml"

    # If run is already complete, emit one complete event and exit.
    if not progress_file.exists() and manifest_file.exists():
        try:
            text = manifest_file.read_text(encoding="utf-8")
            if "finished_at:" in text and "null" not in text.split("finished_at:", 1)[1].splitlines()[0]:
                yield {
                    "event": "complete",
                    "data": json.dumps({"termination_reason": "B"}),
                }
                return
        except Exception:
            pass

    # If there's no progress file and manifest is dry-run, no events.
    if not progress_file.exists():
        yield {
            "event": "comment",
            "data": "no progress file (run may be dry-run or already finalized)",
        }
        yield {
            "event": "complete",
            "data": json.dumps({"termination_reason": "B"}),
        }
        return

    last_payload: str | None = None
    no_file_ticks = 0
    while True:
        try:
            if progress_file.exists():
                payload = progress_file.read_text(encoding="utf-8")
                if payload != last_payload:
                    yield {
                        "event": "progress",
                        "data": payload,
                    }
                    last_payload = payload
                    try:
                        parsed = json.loads(payload)
                    except Exception:
                        parsed = {}
                    if parsed.get("complete"):
                        yield {
                            "event": "complete",
                            "data": json.dumps(
                                {"termination_reason": parsed.get("termination_reason", "B")}
                            ),
                        }
                        return
                no_file_ticks = 0
            else:
                no_file_ticks += 1
                if no_file_ticks > 30:
                    yield {
                        "event": "error",
                        "data": json.dumps({"message": "progress.json missing for >30s"}),
                    }
                    return
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"message": f"{type(e).__name__}: {e}"}),
            }
            return

        # Send a heartbeat comment every loop iteration.
        yield {"event": "comment", "data": "keepalive"}
        await asyncio.sleep(1.0)
