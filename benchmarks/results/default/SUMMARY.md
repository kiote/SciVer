# SciVer mini-benchmark results

16 real test examples; 4 per reasoning type; 8 entailed / 8 refuted.

**Exploratory only:** not the full SciVer benchmark or an estimate with useful statistical precision.

| Model | Reasoning | Correct | Accuracy | Direct | Parallel | Sequential | Analytical | Median seconds | Invalid/errors |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| pi/github-copilot/gpt-5.5 | high | 14/16 | 87.5% | 4/4 | 4/4 | 3/4 | 3/4 | 9.0 | 0/0 |
| ollama/qwen2.5vl:3b | n/a | 9/16 | 56.2% | 3/4 | 1/4 | 3/4 | 2/4 | 7.0 | 0/0 |
| ollama/qwen2.5vl:7b | n/a | 9/16 | 56.2% | 3/4 | 2/4 | 2/4 | 2/4 | 10.5 | 0/0 |

Final-answer parsing is strict; malformed/empty/failed/truncated answers count as wrong.
Latencies include image encoding/upload, model loading, and provider latency; no warm-only claim.
Pi uses Copilot, the reasoning levels shown above, isolated conversations, no tools/personal resources.
Qwen models use Ollama Q4_K_M quantization, temperature 0, seed 215, context 32768, output cap 2048.
Local hardware: Apple M3 Ultra, 96 GiB unified memory. Hosted Pi execution is not hardware-comparable.
Prompt and submitted-image hashes are saved; Pi/providers can still apply their own preprocessing.
Published labels are unchanged, including the apparent annotation inconsistency in test-0160.
Dataset: [chengyewang/SciVer](https://huggingface.co/datasets/chengyewang/SciVer), CC BY 4.0; see slice manifest for revision.
