# Attention Is All You Need: real-article demonstration

Source: Vaswani et al. (2017), *Attention Is All You Need*,
[arXiv 1706.03762v7](https://arxiv.org/pdf/1706.03762v7).

This example downloads the actual PDF, crops its tables, prepares a small set of
source-grounded claims, and runs the existing SciVer inference pipeline with the
repository default **GPT-5.5/high via Pi/Copilot**.

## Run

Prerequisites: Python 3.10+, authenticated Pi CLI, and Poppler's `pdftotext` and
`pdftoppm` (macOS: `brew install poppler`; Ubuntu/Debian: `apt install poppler-utils`).
From the repository root:

```bash
bash scripts/attention_pi.sh
```

An explicit model/reasoning override is optional:

```bash
bash scripts/attention_pi.sh pi/github-copilot/gpt-5.4 high
```

A fresh run makes eight hosted inference calls and may consume Copilot quota.
It does not change your Pi settings or export any credentials.

## What it tests

Eight predefined, self-authored claims: one entailed and one refuted example for
each of the four SciVer-style reasoning types.

- **Direct:** read a reported BLEU score and a layer-count entry.
- **Parallel:** combine table facts and compare a table against the paper's prose.
- **Sequential:** derive training FLOPs per parameter from two tables.
- **Analytical:** substitute values into complexity expressions and check scaling.

The source PDF revision and SHA256 are pinned in `prepare.py`. Table 1 (PDF page
6), Table 2 (page 8), Table 3 (page 9), and a Section 6.1 paragraph crop (page 8)
are rendered directly from the PDF at 216 DPI. They are not recreated tables.
Source provenance, crop bounds and hashes are recorded in `source.json`.

Relevant body sections 4, 6.1 and 6.2 are extracted into `paper.json`. Table 3's
text block is removed from the context so its values are supplied through the
image. The repo expands a section selector to its top-level section, so selecting
6.1 also includes the extracted 6.2 context. Gold labels are not sent to the model.

The `chart` storage key for the Section 6.1 image is a schema convention: that
attachment is a paragraph screenshot, explicitly captioned as text, not a chart.

## Findings and limitations

The pinned PDF has a visible source discrepancy: **Table 2 gives 41.8 EN-FR BLEU
for Transformer (big), whereas Section 6.1 says 41.0**. The parallel-2 claim asks
whether the values agree. Neither value is silently corrected, and this example
does not establish which experimental result is authoritative.

These claims were authored and labeled for this demonstration before inference;
they are **not official SciVer annotations, an independent benchmark, or a
comprehensive fact-check of the paper**. The paper is famous and may be present
in model training data. A good score here does not establish generalization to
unseen papers or prove that image input is necessary for every answer.

## Artifacts

- `data/attention_is_all_you_need/paper.pdf` — downloaded PDF (gitignored)
- `data/attention_is_all_you_need/paper.json` — extracted context/captions (gitignored)
- `data/attention_is_all_you_need/claims.json` — runnable SciVer-style inputs (gitignored)
- `data/attention_is_all_you_need/table*.png` — actual PDF crops (gitignored)
- `data/attention_is_all_you_need/section6_1.png` — original prose image (gitignored)
- `outputs/attention_article/claims_cot/gpt-5.5.json` — raw inference output (gitignored)
- `results/SUMMARY.md` — human-readable checks
- `results/gpt-5.5.inference.json` — every claim, response and selected configuration
- `results/gpt-5.5.eval.json` — per-type and overall label agreement
- `results/gpt-5.5.checks.json` — parsed verdicts and prompt/submitted-image hashes

Original PDF/text/images stay in ignored local data rather than being redistributed
in the code repository. No private datasets, account identities or session history
are used. Review generated responses before publishing them.
