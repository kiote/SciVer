# SciVer mini-benchmark results

16 real test examples; 4 per reasoning type; 8 entailed / 8 refuted.

**Exploratory only:** not the full SciVer benchmark or an estimate with useful statistical precision.

| Model | Reasoning | Correct | Accuracy | Direct | Parallel | Sequential | Analytical | Median seconds | Invalid/errors |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| pi/github-copilot/gpt-5.4 | high | 12/16 | 75.0% | 4/4 | 3/4 | 2/4 | 3/4 | 12.4 | 0/0 |
| pi/github-copilot/gpt-5.5 | high | 14/16 | 87.5% | 4/4 | 4/4 | 3/4 | 3/4 | 9.0 | 0/0 |
| pi/github-copilot/gpt-6.1-sol | high | 13/16 | 81.2% | 4/4 | 4/4 | 3/4 | 2/4 | 9.3 | 0/0 |

Final-answer parsing is strict; malformed/empty/failed/truncated answers count as wrong.
Latencies include image encoding/upload, model loading, and provider latency; no warm-only claim.
Pi uses Copilot, the reasoning levels shown above, isolated conversations, no tools/personal resources.
Local hardware: Apple M3 Ultra, 96 GiB unified memory. Hosted Pi execution is not hardware-comparable.
Prompt and submitted-image hashes are saved; Pi/providers can still apply their own preprocessing.
Published labels are unchanged, including the apparent annotation inconsistency in test-0160.
Dataset: [chengyewang/SciVer](https://huggingface.co/datasets/chengyewang/SciVer), CC BY 4.0; see slice manifest for revision.
