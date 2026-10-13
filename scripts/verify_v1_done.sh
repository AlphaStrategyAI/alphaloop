#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 -m pytest tests/test_deterministic_reviewer.py tests/test_v1_acceptance.py tests/test_export_pack.py tests/test_pit_verifier.py tests/test_verifiers.py tests/test_loop_runtime.py -q

if [[ "${ALPHALOOP_ACCEPTANCE_NETWORK:-}" == "1" ]]; then
  python3 -m pytest tests/test_v1_honest_path.py::test_v1_mean_reversion_reaches_completed_real_ports -v
else
  echo "Skipping network acceptance (set ALPHALOOP_ACCEPTANCE_NETWORK=1 to run Done #1 network path)"
fi
