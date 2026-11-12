#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

command -v python3 >/dev/null 2>&1 || {
  echo "Python 3.12+ is required. Install it from python.org or your approved package source." >&2
  exit 1
}

python3 scripts/check-toolchain.py
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"

echo "Bootstrap complete. Activate with: source .venv/bin/activate"
