# Reader report language policy

All generic paper reports use the shared `paper_review/language.py` policy and
`paper_review/report.py` renderer. Do not create a paper-specific wording engine.

## Basis and limits

The policy follows public ASD-STE100 principles: short sentences, one topic per
sentence, active voice and consistent terms. Technical names, values, units and
source qualifiers stay unchanged.

Official public guidance:
- https://asd-ste100.org/about_STE.html
- https://asd-ste100.org/STE_faq.html
- https://asd-ste100.org/ (current standard: Issue 9, 15 January 2025)

The official standard includes writing rules and an approved dictionary. This
repository does not contain that dictionary or a formal compliance checker.
Therefore reports say **STE-inspired**, not certified ASD-STE100 compliant.

## Main reading flow

1. Show **Problems and actions** first.
2. Group duplicate flagged statements as one issue.
3. Use a short title and the fields **Problem / Evidence / Effect / Action**.
4. Show exact source-page links.
5. Keep proposed changes conditional until the source check supports them.
6. Keep the complete check list and original technical records collapsed.
7. Never show validly dismissed flags in the reader-facing HTML.
8. Keep a short scope/limits note visible. Do not turn an internal-source check
   into a claim that the experiments or whole paper are correct.

## Project validation rules

These are mechanical project checks, not a complete STE language audit:

- Title: at most 12 words.
- Description sentence: at most 25 words.
- Problem/effect: at most two short sentences.
- Evidence: one statement per list item.
- Instruction: at most 20 words; one action sentence per list item.
- Start each action with a clear action verb.
- Do not replace specific scientific terms with inaccurate simple synonyms.
- Do not invent evidence, source values, errors or corrective actions.

## Clear result labels

| Internal code | Reader wording |
|---|---|
| supported | No conflict found |
| contradicted, not source-reviewed | Check this difference |
| ambiguous | Clarify this statement |
| insufficient_evidence | Add missing evidence |
| requires_external_verification | Check other sources |
| not_checked | Check not complete |
| source-reviewed difference | Difference checked against the source |
| reviewer requests evidence | More evidence is required |

“No conflict found” is not proof of experimental correctness. Proposed actions
are suggestions until checked. Raw codes remain only in optional technical data.

## Future analyses

New ingestion workspaces record `reader_language_policy: ste-inspired-v1`.
Their verifier must return a validated `reader_summary` with the same fields.
Malformed/long summaries receive a budget-counted repair attempt; they are not
silently accepted. This adds reader wording to future checks, not a separate
unbounded model-writing job.

Existing completed analyses keep their original verification prompt/cache. They
can be rendered with safe short-language templates without new inference calls.
For concrete reviewed issues, supply a source-checked presentation JSON:

```json
{
  "title": "Limit the comparison claim.",
  "problem": "The claim includes conditions that the table does not support.",
  "evidence": ["The linked table contains an exception."],
  "effect": "The reader can infer a stronger result than the evidence supports.",
  "actions": ["Check the exception.", "State the conditions for the comparison."]
}
```

```bash
bash scripts/paper_review.sh adjudicate my-paper c-ID \
  --decision confirmed --reviewer-type assistant --issue-id comparison-scope \
  --note 'Source values checked.' --presentation data/reader-plan.json
```

Presentation data is stored with the reviewer decision. It is used only while
that decision matches the current verification fingerprint. If evidence changes,
the old plan does not automatically remain a reviewed correction.

The report renderer prefers reviewed presentation text over an unreviewed model
summary. It preserves the original source, verdicts and long explanations in the
private audit record. No manuscript or source data is changed by the report.
