#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p outputs/hello_cot
cp hello_world/sample_with_response.json outputs/hello_cot/fake-model.json
python3 acc_evaluation.py --output_dir outputs/hello_cot

echo "Evaluation written to processed_outputs/hello_cot/fake-model.json"
