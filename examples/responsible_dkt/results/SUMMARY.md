# Neural-Symbolic Knowledge Tracing: Injecting Educational Knowledge into Deep Learning for Responsible Learner Modelling: claim-checking demonstration

Source: [arXiv 2604.08263v1](https://arxiv.org/pdf/2604.08263v1).
Model configuration: **github-copilot/gpt-5.5, high reasoning**.

**8/8 matched the predefined labels; 0 invalid verdicts.**

These are self-authored demonstrations, not official SciVer examples. Model training-data overlap is unknown.

| Check | Type | Expected | Model verdict | Matched |
|---|---|---|---|---|
| rdkt-direct-1 | direct | entailed | yes | yes |
| rdkt-direct-2 | direct | refuted | no | yes |
| rdkt-parallel-1 | parallel | entailed | yes | yes |
| rdkt-parallel-2 | parallel | refuted | no | yes |
| rdkt-sequential-1 | sequential | entailed | yes | yes |
| rdkt-sequential-2 | sequential | refuted | no | yes |
| rdkt-analytical-1 | analytical | entailed | yes | yes |
| rdkt-analytical-2 | analytical | refuted | no | yes |

## Checks

**rdkt-direct-1**: In Table 4, Responsible-DKT with 10% training data and Full sequence length has AUC 0.88 and accuracy 0.85.

**rdkt-direct-2**: Table 5 reports a late-stage prediction error of 11.98% for Classic-DKT at sequence length 50.

**rdkt-parallel-1**: For Full sequences, Table 5 reports lower early-stage error for Responsible-DKT than Classic-DKT (14.35% versus 18.92%), and Table 6 also reports lower inconsistency for Responsible-DKT (0.36 versus 0.44).

**rdkt-parallel-2**: For Full sequences, Responsible-DKT has both a lower middle-stage error in Table 5 and lower volatility in Table 6 than BaseNS-DKT.

**rdkt-sequential-1**: Using the printed Full-sequence values, replacing Classic-DKT with Responsible-DKT reduces early-stage error in Table 5 by about 24.2% relative to Classic-DKT, while reducing inconsistency in Table 6 by about 18.2% relative to Classic-DKT; the first relative reduction is larger.

**rdkt-sequential-2**: Table 5 reports errors as percentages while Table 6 reports inconsistency as proportions. Converting Table 6's Full-sequence inconsistency values from 0.44 for Classic-DKT to 0.36 for Responsible-DKT into percentages gives a decrease of about 18.2 percentage points.

**rdkt-analytical-1**: Table 6 provides a counterexample to equating the lowest volatility with the lowest inconsistency: for Full sequences, BaseNS-DKT has lower volatility than Responsible-DKT (0.11 versus 0.17) but higher inconsistency (0.44 versus 0.36).

**rdkt-analytical-2**: In every matching training-ratio and sequence-length setting printed in Table 4, Responsible-DKT has strictly higher accuracy than Classic-DKT.

## Source review and limitations

The universal accuracy claim is not supported by every printed Table 4 setting: at 10% training ratio and N=10, Responsible-DKT accuracy is **0.78** versus Classic-DKT **0.84**; at 50% and N=10 both are **0.83**.
This is a scoped check of reported table values, not a reproduction of the experiments, a significance test, or a rejection of the paper's AUC findings.
The drop from inconsistency 0.44 to 0.36 is **8 percentage points**, or about **18.2% relative reduction**—these are different quantities.
Only aggregate tables and selected metric/results prose are provided. Author/contact lists, bibliographic citations and individual-student examples are excluded.
The eight checks and labels were authored from the source before inference; they are not official SciVer annotations or a whole-paper audit.

Original PDF, extracted body text and PDF crops remain in ignored local `data/`.
Full model responses and selected model/reasoning metadata are in the adjacent inference JSON.
