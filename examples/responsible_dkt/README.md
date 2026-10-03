# Responsible-DKT: recent-paper demonstration

Source: Danial Hooshyar et al., *Neural-Symbolic Knowledge Tracing: Injecting
Educational Knowledge into Deep Learning for Responsible Learner Modelling*,
[arXiv 2604.08263v1](https://arxiv.org/abs/2604.08263v1), submitted **9 April 2026**.
This is a preprint; no journal publication status is assumed.

See [RECENT_PAPERS.md](RECENT_PAPERS.md) for the verified recent-publication
shortlist, publication/revision dates, and source provenance. This paper was
selected because its PDF is openly available and it contains suitable aggregate
performance tables—not because it is the latest journal article in the list.

## Reproduce

Prerequisites: Python 3.10+, authenticated Pi CLI, and Poppler (`pdftotext`,
`pdftoppm`; macOS: `brew install poppler`). From the repository root:

```bash
bash scripts/responsible_dkt_pi.sh
```

The default comes from `utils/constant.py`: **GPT-5.5/high via Pi/Copilot**.
A fresh run makes eight hosted inference calls. An explicit override is optional:

```bash
bash scripts/responsible_dkt_pi.sh pi/github-copilot/gpt-5.4 high
```

## Human-readable browser report

Generate a self-contained HTML review from the saved responses, without new model
calls, and open it locally:

```bash
.venv/bin/python -m examples.responsible_dkt.html_report
open outputs/responsible_dkt/report.html   # macOS
```

The report includes the exact source wording, all 12 matched Table 4 accuracy/AUC
comparisons, original table images, model explanations, calculations and limits.
Filters distinguish the one source-related wording issue from the three deliberately
false controls and four supported test claims. Images can be enlarged, and the
report supports printing/saving as PDF. It uses no external scripts/fonts/trackers.

PDF/source/prompt/image hashes are checked against the saved run before rendering.
The HTML and embedded paper crops remain in ignored `outputs/`; they are not
published automatically. Keep the generated report inside the repo so evidence
links remain relative rather than exposing personal home-directory paths.

## Evidence and method

The arXiv revision and PDF SHA256 are pinned in `prepare.py`. The script renders
actual PDF crops at 216 DPI:

- Table 4, PDF page 18: model performance across training ratios/sequence lengths.
- Table 5, page 19: early/middle/late error rates, in percentages.
- Table 6, page 19: volatility/inconsistency, as proportions.

Only metric definitions (section 3.4.1) and quantitative-results prose (section
4.2) accompany the images. Title/author/contact lists, bibliographic citations,
reference lists and individual-student examples are excluded from model inputs.
No private research files or private learner data are used. All source access is
through the public arXiv PDF.

Eight claims and their labels were authored and checked against the source before
inference: two per SciVer-style reasoning type, with four entailed/four refuted.
These are **not official SciVer examples** and do not form an independent,
representative model-quality benchmark. Gold labels are not sent to the model;
each claim gets a separate conversation with tools/personal context disabled.
Model training-data overlap is unknown.

## Observed result

GPT-5.5/high matched **8/8** predefined labels, with no invalid verdicts. See
[results/SUMMARY.md](results/SUMMARY.md), full responses in
`results/gpt-5.5.inference.json`, and parsed verdict/input hashes in
`results/gpt-5.5.checks.json`.

Some useful checks:

- Responsible-DKT at 10% training data and Full sequence length: AUC **0.88**,
  accuracy **0.85** (Table 4).
- Classic-DKT late-stage error at sequence length 50: **10.48%**, not 11.98%
  (Table 5); 11.98% belongs to Responsible-DKT.
- Full-sequence inconsistency from Classic-DKT **0.44** to Responsible-DKT
  **0.36** is a decrease of **8 percentage points**, or about **18.2% relative**.
- Lowest volatility and lowest inconsistency are not the same ranking (Table 6).

### Scoped source-consistency finding

The broad accuracy statement in section 4.2 needs qualification against Table 4.
At **10% training ratio / N=10**, Responsible-DKT has accuracy **0.78**, while
Classic-DKT has **0.84**. At **50% / N=10**, both have **0.83**. Thus the claim of
strictly higher accuracy in *every* reported setting is not supported by the
printed table, even though the reported AUC advantage is a separate matter.

This checks internal consistency of the reported numbers. It **does not**
reproduce model training, audit the raw data, test statistical significance,
validate causal interpretations, or invalidate the paper's overall findings.

## Local/private artifacts

The original PDF, extracted source text, crops and runnable input JSON stay in
ignored `data/responsible_dkt/`. General inference outputs stay in ignored
`outputs/responsible_dkt/`. The example folder holds only preparation/reporting
code, public bibliographic provenance and reviewed result snapshots. Public
coauthor/contact lists are not copied here. Review responses before publishing.
