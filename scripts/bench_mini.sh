#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v pi >/dev/null || { echo 'Install Pi CLI and log in to github-copilot first.' >&2; exit 1; }
command -v ollama >/dev/null || { echo 'Install/start Ollama first.' >&2; exit 1; }
pi auth check --provider github-copilot
for model in qwen2.5vl:3b qwen2.5vl:7b; do
  if ! ollama show "$model" >/dev/null 2>&1; then
    ollama pull "$model"
  fi
done
python3 -m venv .venv
.venv/bin/python -m pip install -r benchmarks/requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -u -m benchmarks.run "$@"
.venv/bin/python -m benchmarks.run --summarize-only
