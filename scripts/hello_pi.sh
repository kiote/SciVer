#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODEL="${1:-pi/github-copilot/gpt-5.4}"

if ! command -v pi >/dev/null 2>&1; then
  echo "error: pi CLI not found in PATH" >&2
  exit 1
fi

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r hello_world/requirements-pi-hello.txt

python main.py \
  --model "$MODEL" \
  --data_path hello_world/sample.json \
  --max_num 1 \
  --prompt cot \
  --output_dir outputs

OUTPUT_BASENAME="$(basename "$MODEL")"
OUTPUT_JSON="outputs/sample_cot/${OUTPUT_BASENAME}.json"
EVAL_JSON="processed_outputs/sample_cot/${OUTPUT_BASENAME}.json"
SNAPSHOT_DIR="hello_world/results"
mkdir -p "$SNAPSHOT_DIR"

python acc_evaluation.py --output_dir outputs/sample_cot

cp "$OUTPUT_JSON" "$SNAPSHOT_DIR/${OUTPUT_BASENAME}.inference.json"
cp "$EVAL_JSON" "$SNAPSHOT_DIR/${OUTPUT_BASENAME}.eval.json"

echo
echo "Hello-world inference written to: $OUTPUT_JSON"
echo "Evaluation written to: $EVAL_JSON"
echo "Committed snapshots updated in: $SNAPSHOT_DIR/"
