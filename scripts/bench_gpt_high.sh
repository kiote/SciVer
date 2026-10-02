#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v pi >/dev/null || { echo 'Install Pi CLI and log in to github-copilot first.' >&2; exit 1; }
pi auth check --provider github-copilot
python3 -m venv .venv
.venv/bin/python -m pip install -r benchmarks/requirements.txt
.venv/bin/python -m unittest discover -s tests -v

MODELS=(pi/github-copilot/gpt-5.4 pi/github-copilot/gpt-5.5 pi/github-copilot/gpt-6.1-sol)
.venv/bin/python -u -m benchmarks.run \
  --models "${MODELS[@]}" --thinking high \
  --results-dir benchmarks/results/gpt_high "$@"
.venv/bin/python -m benchmarks.run \
  --models "${MODELS[@]}" --results-dir benchmarks/results/gpt_high --summarize-only
