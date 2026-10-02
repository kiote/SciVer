#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v pi >/dev/null || { echo 'Install Pi CLI and authenticate to github-copilot first.' >&2; exit 1; }
command -v pdftotext >/dev/null || { echo 'Install Poppler first (brew install poppler on macOS).' >&2; exit 1; }
command -v pdftoppm >/dev/null || { echo 'Install Poppler first (brew install poppler on macOS).' >&2; exit 1; }
python3 -m venv .venv
.venv/bin/python -m pip install --quiet -r benchmarks/requirements.txt
MODEL="${1:-$(.venv/bin/python -c 'from utils.constant import DEFAULT_MODEL; print(DEFAULT_MODEL)')}"
THINKING="${2:-$(.venv/bin/python -c 'from utils.constant import DEFAULT_PI_THINKING; print(DEFAULT_PI_THINKING)')}"

.venv/bin/python -m examples.attention_is_all_you_need.prepare
.venv/bin/python main.py \
  --model "$MODEL" --thinking "$THINKING" \
  --data_path data/attention_is_all_you_need/claims.json \
  --max_num -1 --output_dir outputs/attention_article
.venv/bin/python -m examples.attention_is_all_you_need.report \
  --input "outputs/attention_article/claims_cot/$(basename "$MODEL").json"
