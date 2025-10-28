#!/usr/bin/env bash
set -o errexit
set -o pipefail
set -o nounset

# Install Node.js dependencies without dev packages.
npm install --omit=dev

# Install the Python toolchain that powers the scraping helpers.
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "Python runtime is required by the scraping CLI" >&2
  exit 1
fi

"${PYTHON_BIN}" -m pip install --upgrade pip
"${PYTHON_BIN}" -m pip install -r requirements.txt
