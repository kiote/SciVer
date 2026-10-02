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
pi/github-copilot/gpt-5.4
```

You can override the model explicitly:

```bash
bash scripts/hello_pi.sh pi/github-copilot/gpt-5.4
```

What it does:
- creates/updates `.venv`
- installs the minimal Python deps from `hello_world/requirements-pi-hello.txt`
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

## Option 2: test with the repo's other backends

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

## Option 3: evaluation-only smoke test

```bash
bash hello_world/run_eval_only.sh
```

Expected result file:
- `processed_outputs/hello_cot/fake-model.json`

Because this toy set includes only the `direct` subset, the other subset scores will be `null`.
