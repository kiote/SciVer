#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
if ! .venv/bin/python -c 'import pymupdf, requests, PIL' >/dev/null 2>&1; then
  .venv/bin/python -m pip install -r requirements-review.txt
fi
exec .venv/bin/python -m paper_review "$@"
