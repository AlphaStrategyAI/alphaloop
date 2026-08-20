#!/usr/bin/env bash
set -euo pipefail

# Idempotent Cloud Agent bootstrap for the AlphaStrategy suite workspace.
#
# Resolves paths from this script's own location, so it works whether the
# install command runs from the repo root or from a multi-repo workspace
# root (Cloud Agent runs `install` from /workspace, with repos checked out
# under repos/<name>). Installs alphaloop and puts its console script on
# PATH, and does the same for the companion `alphastrategy` execution desk
# when that repo is checked out alongside this one. Starts no servers.

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
alphaloop_root="$(dirname "${script_dir}")"
workspace_root="$(dirname "${alphaloop_root}")"

python3 -m pip install --upgrade pip

install_editable() {
  # $1 = project directory containing pyproject.toml
  local project_dir="$1"
  local ok=0
  for i in 1 2 3 4 5; do
    if (cd "${project_dir}" && python3 -m pip install -e ".[dev]"); then
      ok=1
      break
    fi
    echo "pip install failed for ${project_dir} (attempt ${i}), retrying..."
    sleep $((i * 5))
  done
  if [ "${ok}" -ne 1 ]; then
    echo "pip install -e .[dev] failed for ${project_dir} after 5 attempts"
    exit 1
  fi
}

link_console_script() {
  # This image installs user scripts to ~/.local/bin, which is not on PATH.
  local name="$1"
  if ! command -v "${name}" >/dev/null 2>&1; then
    local script="${HOME}/.local/bin/${name}"
    if [ -x "${script}" ]; then
      if [ -w /usr/local/bin ]; then
        ln -sfn "${script}" "/usr/local/bin/${name}"
      elif command -v sudo >/dev/null 2>&1; then
        sudo ln -sfn "${script}" "/usr/local/bin/${name}"
      fi
    fi
  fi
}

install_editable "${alphaloop_root}"
link_console_script alphaloop
command -v alphaloop >/dev/null
python3 -c "import alphaloop; print('alphaloop', alphaloop.__version__)"

# Companion execution desk, present in the AlphaStrategy suite workspace.
# Optional: a standalone alphaloop checkout has no sibling alphastrategy.
alphastrategy_root="${workspace_root}/alphastrategy"
if [ -f "${alphastrategy_root}/pyproject.toml" ]; then
  install_editable "${alphastrategy_root}"
  link_console_script alphastrategy
  command -v alphastrategy >/dev/null
  python3 -c "import alphastrategy; print('alphastrategy', getattr(alphastrategy, '__version__', 'ok'))"
fi
