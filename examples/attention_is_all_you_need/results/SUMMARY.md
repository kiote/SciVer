# Attention Is All You Need: claim-checking demonstration

Source: [arXiv 1706.03762v7](https://arxiv.org/pdf/1706.03762v7).
Model configuration: **github-copilot/gpt-5.5, high reasoning**.

**8/8 matched the predefined labels; 0 invalid verdicts.**

These are self-authored demonstrations, not official SciVer examples. The paper is widely known and may be in model training data.

| Check | Type | Expected | Model verdict | Matched |
|---|---|---|---|---|
| attention-direct-1 | direct | entailed | yes | yes |
| attention-direct-2 | direct | refuted | no | yes |
| attention-parallel-1 | parallel | entailed | yes | yes |
| attention-parallel-2 | parallel | refuted | no | yes |
| attention-sequential-1 | sequential | entailed | yes | yes |
| attention-sequential-2 | sequential | refuted | no | yes |
| attention-analytical-1 | analytical | entailed | yes | yes |
| attention-analytical-2 | analytical | refuted | no | yes |

## Checks

**attention-direct-1**: Table 2 reports a BLEU score of 28.4 for Transformer (big) on the English-to-German newstest2014 test.

**attention-direct-2**: Table 3 lists N = 12 for the base Transformer configuration.

**attention-parallel-1**: Table 1 lists O(n) sequential operations for recurrent layers, while Table 2 reports 27.3 English-to-German BLEU for Transformer (base model).

**attention-parallel-2**: Table 2 and the prose in Section 6.1 report the same numerical English-to-French BLEU score for the big Transformer model.

**attention-sequential-1**: Using the base/big training-cost entries printed in Table 2 and their parameter counts in Table 3, dividing FLOPs by parameter count gives roughly 2.1 times as many training FLOPs per parameter for big as for base.

**attention-sequential-2**: The printed values in Tables 2 and 3 imply that big has a lower training FLOP count per parameter than base, after dividing each Table 2 training cost by its corresponding Table 3 parameter count.

**attention-analytical-1**: Comparing just the polynomial factors in Table 1, ignoring hidden Big-O constants, n = 128 and d = 512 make the self-attention factor n squared times d equal to one quarter of the recurrent factor n times d squared. This is a comparison of the expressions, not measured wall-clock time.

**attention-analytical-2**: For fixed d, doubling n multiplies the self-attention polynomial factor in Table 1 by two and the recurrent polynomial factor by four.

## Source consistency check

The downloaded PDF's Table 2 shows EN-FR BLEU **41.8** for Transformer (big), whereas its Section 6.1 prose shows **41.0**.
The parallel-2 check asks whether those numbers agree. This detects a discrepancy; it does not determine which experimental number is authoritative.

PDF, selected body text and original PDF crops remain in ignored `data/attention_is_all_you_need/`.
Full model responses and selected model/reasoning metadata are in the adjacent inference JSON.
