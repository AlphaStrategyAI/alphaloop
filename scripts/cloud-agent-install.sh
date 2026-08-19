#!/usr/bin/env bash
set -euo pipefail

# Idempotent Cloud Agent bootstrap. Installs the editable package and
# puts the alphaloop console script on PATH. Does not start servers.

python3 -m pip install --upgrade pip

ok=0
for i in 1 2 3 4 5; do
  if python3 -m pip install -e ".[dev]"; then
    ok=1
    break
  fi
  echo "pip install failed (attempt ${i}), retrying..."
  sleep $((i * 5))
done
if [ "${ok}" -ne 1 ]; then
  echo "pip install -e .[dev] failed after 5 attempts"
  exit 1
fi

# This image installs user scripts to ~/.local/bin, which is not on PATH.
if ! command -v alphaloop >/dev/null 2>&1; then
  script="${HOME}/.local/bin/alphaloop"
  if [ -x "${script}" ]; then
    if [ -w /usr/local/bin ]; then
      ln -sfn "${script}" /usr/local/bin/alphaloop
    elif command -v sudo >/dev/null 2>&1; then
      sudo ln -sfn "${script}" /usr/local/bin/alphaloop
    fi
  fi
fi

command -v alphaloop >/dev/null
python3 -c "import alphaloop; print('alphaloop', alphaloop.__version__)"
