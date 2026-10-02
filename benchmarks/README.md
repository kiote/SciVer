# Real SciVer mini-benchmark

This is a **16-example exploratory comparison**, not the synthetic hello-world
and not a run of the full 2,000-example test split.

## Reproduce

Prerequisites:
- Python 3.10+; this run used Python 3.14 and the pinned `requirements.txt` here.
- Pi CLI authenticated to GitHub Copilot (`/login github-copilot` inside Pi).
- Ollama installed and running on its default loopback port (11434).
- Local memory sufficient for Qwen2.5-VL 3B/7B. This run used an Apple M3 Ultra
  with 96 GiB unified memory, Pi 1.0.0 and Ollama 0.20.0.

From the repository root:

```bash
bash scripts/bench_mini.sh
```

The script installs Python dependencies, downloads missing Qwen models (~9 GB
combined), downloads **only selected dataset assets**, runs tests and all three
models, then generates the comparison. The default hosted model is now
**GPT-5.5/high** (from `utils/constant.py`), alongside the two local Qwen models.
Future default runs are saved under `benchmarks/results/default/` so the original
GPT-5.4/medium comparison stays unchanged. Sixteen hosted calls use your Copilot
quota. It does not copy/export credentials.

To resume an interrupted run with matching inputs and settings:

```bash
bash scripts/bench_mini.sh --resume
```

To regenerate the summary from saved responses without calling any model:

```bash
.venv/bin/python -m benchmarks.run --summarize-only
```

Individual backends:

```bash
.venv/bin/python -m benchmarks.run --models ollama/qwen2.5vl:3b ollama/qwen2.5vl:7b
.venv/bin/python -m benchmarks.run --models pi/github-copilot/gpt-5.5
```

To reproduce or summarize the historical GPT-5.4/medium comparison explicitly:

```bash
.venv/bin/python -m benchmarks.run --models pi/github-copilot/gpt-5.4 ollama/qwen2.5vl:3b ollama/qwen2.5vl:7b \
  --thinking medium --results-dir benchmarks/results
# Add --summarize-only to reuse the saved responses without model calls.
```

`--model` in `main.py`, `--models` here, and `--thinking` are explicit overrides.
Without overrides, both inference and the default mini-benchmark use GPT-5.5/high.
The separate `bench_gpt_high.sh` intentionally lists older/newer models as
comparison controls; it is not the general default runner.

## High-reasoning GPT comparison

Run GPT-5.4, GPT-5.5 and GPT-6.1-sol at **high** reasoning on the exact same
frozen 16 examples, preserving the original medium/local runs:

```bash
bash scripts/bench_gpt_high.sh
# Reuse matching completed responses or resume a saved prefix:
bash scripts/bench_gpt_high.sh --resume
```

This makes 48 hosted calls on a fresh run. It does not install or run local
models. New results go to [`results/gpt_high/SUMMARY.md`](results/gpt_high/SUMMARY.md)
and per-model JSON in that directory. The existing medium/local results are
not overwritten. An existing file with different input/settings fingerprints
is rejected; use a separate `--results-dir` for a new configuration.

Observed single-run results (unchanged published labels):

| Model | Reasoning | Correct | Accuracy | Median seconds |
|---|---|---:|---:|---:|
| GPT-5.4 (previous baseline) | medium | 11/16 | 68.75% | 10.2 |
| GPT-5.4 | high | 12/16 | 75.0% | 12.4 |
| GPT-5.5 | high | 14/16 | 87.5% | 9.0 |
| GPT-6.1-sol | high | 13/16 | 81.25% | 9.3 |

All 48 high-run responses completed without errors, truncation or invalid
verdicts. Their input, system prompt and manifest hashes were checked against
the previous medium baseline. Pi's effective model and high reasoning setting
are checked after every session reset. The provider did not supply separate
`responseModel`/`providerThinkingLevel` fields, so model IDs refer to the Pi
configurations requested—not independently attested upstream identities.

All three high configurations correctly rejected the eight refuted claims.
GPT-5.5 accepted 6/8 entailed claims; GPT-6.1-sol 5/8; GPT-5.4 high 4/8. The two
GPT-5.5 disagreements are `test-1593` (partial phase-specific evidence vs a full
S→Se→Te trend) and `test-0160` (the apparent 400-vs-200 gold-label error).

These are single draws: the medium-to-high change is not an isolated causal
estimate, and the one-example gap between GPT-5.5 and GPT-6.1-sol does not
establish a reliable ranking. No prompt changes, label corrections, or
100-example expansion are included in this comparison.

## Dataset and selection

Source: [chengyewang/SciVer](https://huggingface.co/datasets/chengyewang/SciVer),
CC BY 4.0. Attribution: Wang, Chengye; Shen, Yifei; Kuang, Zexi; Cohan, Arman;
Zhao, Yilun. *SciVer: Evaluating Foundation Models for Multimodal Scientific
Claim Verification*, ACL 2025, https://aclanthology.org/2025.acl-long.420/.

`slice16.manifest.json` pins dataset revision
`5695ac384d247ae5df2a7b73568dc63d189296b0`, source and asset SHA256 hashes,
selection seed 215, exact test indices, and image processing.

- Four examples per type: direct, parallel, sequential, analytical.
- Two entailed and two refuted per type (8/8 overall).
- Ranked deterministically by SHA256(seed:index) within each type/label.
- Do not select both versions of a mirrored original/perturbed question.
- No sample selection based on model outcomes.
- Send only the claim, selected paper sections, captions, and one/two images.
  Gold labels, explanations and alternative statements are **not** sent.

## Method

All three models use the same upstream `COT_PROMPT` templates and neutral
verification system instruction. Input hashes are saved in each result file,
and comparison generation refuses mismatched inputs. Pi sends JPEG image
blocks; Ollama sends their identical base64 bytes through its native chat API.
Providers can still preprocess images internally.

Pi: the original GPT-5.4 baseline uses medium reasoning; the follow-up GPT
comparison uses high reasoning. All run through Copilot, with a separate conversation per example.
No tools, extensions, skills, prompt templates, project context or prior session
history. Provider errors and deadlines are checked rather than saving blank
answers as successes.

Ollama: Qwen2.5-VL 3B and 7B, Q4_K_M; temperature 0, seed 215, context 32768,
output cap 2048. Model digests and runtime versions are saved. Model tags and
hosted models may change; fixed seeds do **not** guarantee byte-identical output.

Evaluation uses the final explicit `yes`/`no`, not a substring anywhere in the
explanation. Empty, ambiguous, malformed, errored and truncated answers count as
wrong. The old substring metric is also recorded for transparency.

Latency is single-run wall time per example, including uploads and model loads
(and Pi session reset). It is **not** a controlled hardware/speed benchmark;
the hosted model executes remotely. No repeated accuracy trials were run.

## Results and limitations

See [`results/SUMMARY.md`](results/SUMMARY.md) for the original medium/local
comparison and [`results/gpt_high/SUMMARY.md`](results/gpt_high/SUMMARY.md) for
the high-reasoning follow-up. The default comparison is in
[`results/default/SUMMARY.md`](results/default/SUMMARY.md), assembled from the
already-observed GPT-5.5/high and local Qwen responses; see its provenance README.
Per-model JSON records every answer, prediction, label, latency and token count.
Summaries are computed, not hand-edited.

Small-N uncertainty is large: one example changes overall accuracy by 6.25
percentage points and a per-type score by 25 points. These results do not
establish a reliable ranking or full-benchmark performance.

One apparent annotation inconsistency was observed, **without changing the gold
label**: `test-0160` is labeled entailed for a claim that the G-Ref peak 61.36
occurs at pool size 400. Figure 10 and the accompanying paper text instead show
200. All three models answered no and are counted wrong against the published
label. Other disagreements may also involve interpretive/prompt ambiguities;
we have not systematically audited annotations.

## Privacy and artifacts

Downloaded paper JSON/images, environments and general runtime outputs stay in
ignored `data/`, `.venv/`, `outputs/` and `processed_outputs/`. Public result
artifacts contain only dataset IDs, model answers, labels, input hashes, anonymous
runtime versions and timings—not user account names, session IDs, auth files,
absolute local paths or credentials. No accountant data is used. Review generated
responses for sensitive content before committing/publishing them.
