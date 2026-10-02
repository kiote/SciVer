# Hello world smoke test

This folder contains a minimal 1-example SciVer-style sample.

## Files
- `paper.json` — tiny fake paper metadata
- `sample.json` — one `direct` claim-verification example
- `fig1.png` — placeholder image
- `sample_with_response.json` — fake model output for evaluation testing

## Option 1: reproducible end-to-end hello world via Pi

Use the helper script:

```bash
bash scripts/hello_pi.sh
```

By default it runs with:

```bash
pi/github-copilot/gpt-5.5
```

Reasoning defaults to **high**. Both defaults come from `utils/constant.py`,
not your current Pi session or personal Pi settings. The run checks Pi's selected
model, image capability and reasoning level; it fails rather than silently using
a different configuration.

You can override both explicitly:

```bash
bash scripts/hello_pi.sh pi/github-copilot/gpt-5.4 medium
```

For any SciVer input file, omitting `--model` selects the same GPT-5.5/high default:

```bash
.venv/bin/python main.py --data_path hello_world/sample.json --max_num 1
```

Results include an `inference` object recording the selected provider, model,
reasoning level and image count. The default hello-world snapshot is
`hello_world/results/gpt-5.5.inference.json`.

What it does:
- creates/updates `.venv`
- installs the pinned minimal Python deps from `benchmarks/requirements.txt`
- runs `main.py` on `hello_world/sample.json`
- runs `acc_evaluation.py`
- copies stable result snapshots into `hello_world/results/`

This launches `pi` in RPC mode and sends the prompt plus image(s) through Pi, so the repo can reuse the same provider/account Pi is already using.

If you are running from inside Pi and want to reuse the exact current session model dynamically, this also works:

```bash
python3 main.py \
  --model pi/current \
  --data_path hello_world/sample.json \
  --max_num 1 \
  --prompt cot \
  --output_dir outputs
```

## Option 2: text-only hello world with local Laya

```bash
bash scripts/hello_laya.sh
```

By default this uses:

```bash
laya/typed-decisions
```

Notes:
- this is a **text-only baseline**, not a true multimodal run
- it expects `laya` to be installed in a Python environment
- use `LAYA_PYTHON=/path/to/python-with-laya` to choose an installed environment;
  otherwise it uses the active Python interpreter (no sibling-project dependencies)

## Option 3: multimodal hello world with local Ollama

```bash
bash scripts/hello_ollama.sh
```

Default model:

```bash
ollama/qwen2.5vl:7b
```

You can also try a smaller variant:

```bash
bash scripts/hello_ollama.sh ollama/qwen2.5vl:3b
```

This uses Ollama's local multimodal chat API with image attachments. Laya and
Ollama scripts are explicit alternative backends; they do not change the repo's
GPT-5.5/high default.

## Option 4: test with the repo's other backends

Run with any configured supported model:

```bash
python main.py \
  --model gpt-4o-mini \
  --data_path hello_world/sample.json \
  --max_num 1 \
  --prompt cot \
  --output_dir outputs
```

This requires the corresponding API credentials or local model setup.

## Option 5: evaluation-only smoke test

```bash
bash hello_world/run_eval_only.sh
```

Expected result file:
- `processed_outputs/hello_cot/fake-model.json`

Because this toy set includes only the `direct` subset, the other subset scores will be `null`.
