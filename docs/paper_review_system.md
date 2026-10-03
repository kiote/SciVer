# Generic paper review system (MVP)

This workflow accepts **any local PDF or HTTPS PDF URL** without paper-specific
claim lists, crop coordinates, report code, or gold labels. It is separate from
the original SciVer labelled benchmark and the earlier eight-check demos.

It provides a resumable review workspace, two extraction passes, evidence
retrieval, five-way verification statuses, explicit human decisions, and a
paper-independent HTML coverage report. It does **not** guarantee discovery of
all errors or certify experimental validity.

## Quick start

```bash
# Prepare every page. No provider calls and no upload approval implied.
bash scripts/paper_review.sh ingest path/to/paper.pdf --id my-paper --title 'Paper title'
# Or use a publicly accessible HTTPS PDF URL:
bash scripts/paper_review.sh ingest https://arxiv.org/pdf/1706.03762v7 --id attention-review

# Inspect prepared page images/text. Report is cached and requires no model calls.
bash scripts/paper_review.sh report my-paper --open

# Only AFTER inspecting/redacting selected prepared inputs:
bash scripts/paper_review.sh approve-inputs my-paper --pages 1-5

# Request at most 10 new model tasks. Resume later with identical settings.
bash scripts/paper_review.sh run my-paper --pages 1-5 --partial --max-calls 10
bash scripts/paper_review.sh report my-paper --open
bash scripts/paper_review.sh status my-paper
```

Python 3.10+ and the authenticated Pi CLI are required for model stages. Python
PDF tooling is in `requirements-review.txt`; no per-paper Poppler scripts are
needed. Default provider configuration is GPT-5.5/high from `utils/constant.py`.
`ingest`, `list`, `status`, `report` and reviewer commands do not make model calls.

Each paper gets an independent workspace. View the collection with
`bash scripts/paper_review.sh list`; no paper-specific source code is required.
For a local PDF directory, ingestion can be batched without uploading anything:

```bash
for pdf in papers/*.pdf; do
  bash scripts/paper_review.sh ingest "$pdf"
done
bash scripts/paper_review.sh list
```

## Full-run completion contract

The default `run` executes **all configured stages on every in-scope page and
extracted claim**. Restricted page ranges or `--stage extract/verify` require an
explicit `--partial` flag. A full run exits successfully only when the completion
gate finds no pending/failed configured internal checks; otherwise it generates
the report and exits **code 3 (incomplete/paused)**. It never silently treats a
budget-limited pilot as a completed review.

For a complete internal-source run, inspect/approve every in-scope input, then:

```bash
bash scripts/paper_review.sh run my-paper --max-calls 200 --batch-size 8 --workers 2
# If the safety cap is reached, resume the identical command; completed tasks are cached.
```

The default safety cap is 200 new tasks, with two isolated workers and verification
batches of up to eight claims sharing the same retrieved evidence window. Every
claim gets its own verdict/evidence IDs; missing batch results are rejected.
Malformed structured replies receive at most one budget-counted repair attempt.
The budget counts requested tasks, including failed/repair tasks, not exact
billing or transport retries performed by Pi/providers.

Privacy approval is still mandatory. Exclusions are never automatic: after source
inspection, wholly non-scientific pages can be explicitly scoped out with reasons:

```bash
bash scripts/paper_review.sh exclude-pages my-paper --pages 1 \
  --reason 'Author/affiliation sheet only; no scientific body claims'
```

Do not exclude a first page that also contains an abstract, or a bibliography page
that also contains conclusions. Already-analysed pages cannot be excluded to
cherry-pick outcomes. Excluded pages are shown as excluded (with reasons), not
pending. External citation/data/code verification and human adjudication remain
separate unresolved work even after all configured internal checks finish.

## Pipeline and artifacts

1. **Ingest and pin source** — SHA256 of the original PDF; copy it into an ignored
   workspace; render prepared page images. Assign each text block a stable
   page/unit ID, bounding box, and heuristic section hint. A full-page visual unit
   tracks diagrams/equations/table layouts that text blocks can miss.
2. **Review inputs** — mask detectable emails/ORCIDs/home paths, additional literal
   redactions, and a first-page pre-abstract author block where detectable. Review
   every selected prepared image/text before approval. Automatic masks cannot
   guarantee PII removal. Contact/name information and sensitive examples may
   require more redaction; changing inputs invalidates existing approvals.
3. **Extract actual claims** — paper statements must match verbatim source text;
   stronger paraphrases and synthetic negative controls are rejected. Visual
   observations are explicitly distinguished from authored prose.
4. **Second coverage pass** — inventory the original page again in an isolated
   conversation without seeing the primary pass. It currently uses the same
   configured model, so shared model biases remain. Union/deduplicate claims. Both passes must
   account for every supplied unit with a claim, non-claim explanation, reference
   classification, or unreadable status. This is a coverage aid, not a proof that
   no sentence/qualifier was missed.
5. **Retrieve and verify** — select source pages, referenced table/figure captions
   and lexically relevant evidence among approved pages. Retrieval currently uses
   at most three pages per claim; evidence outside the window is not presumed
   absent from the paper. Citations/raw-data/code-dependent claims remain marked
   for external verification rather than guessed from model memory.
6. **Check arithmetic** — a whitelist calculator recomputes difference, ratio and
   relative percent change with Decimal. No model-generated code is executed.
   This checks arithmetic only; source operands still require review.
7. **Human decisions** — model contradictions/ambiguities are candidates, never
   automatically confirmed paper errors. Explicit reviewer decisions and coverage
   acknowledgements are stored separately.
8. **Render** — generic local HTML with page/section coverage, source locators,
   status counts, model justifications, candidate/confirmed separation, unresolved
   claims and prepared page images. Validly dismissed flags are omitted from the
   reader-facing HTML entirely: no cards, notes, group links or filter entries.
   They remain in the private audit ledger; processing totals still account for
   all executed checks. A changed verification invalidates its old dismissal and
   requires fresh review, without showing the historical dismissal note.
   Reader-facing scope is a short plain-language statement about what was checked
   and what was not independently validated. Per-page units, input-consent flags,
   reading-pass counters and diagnostics are collapsed technical audit details,
   not required reading for interpreting findings.
   Main reader text uses STE-inspired Problem / Evidence / Effect / Action cards
   and plain result labels, not raw model status codes. The complete check list is
   collapsed. See `docs/report_language.md` for the shared policy and validation.
   No accuracy score is invented without gold labels. Report caching avoids repeat work.

State, original/prepared PDFs, model-task caches and source units stay under
ignored `data/reviews/<id>/`; HTML/cache files under ignored
`outputs/reviews/<id>/`. Source URLs are stored without signed query strings;
local source paths are not recorded. Generated reports link source images locally
rather than bundling entire papers for redistribution. Displayed source excerpts
are limited to 90 words across a report. Inspect privacy/copyright before sharing.

## Outcomes

- `supported`: internally supported by supplied evidence, not experimental truth.
- `contradicted`: concrete conflicting source evidence.
- `ambiguous`: unclear scope/units/definitions or interpretation.
- `insufficient_evidence`: supplied/retrieved evidence cannot resolve the claim.
- `requires_external_verification`: needs raw data, code, cited literature or other
  external material.
- `not_checked`: no successful verification task yet.

## Reviewer commands

After inspecting the linked source evidence:

```bash
bash scripts/paper_review.sh adjudicate my-paper c-CLAIM_ID \
  --decision confirmed --note 'Checked the source cells; the universal wording has a counterexample.'
# Or --decision dismissed / needs_evidence

# Only after all readable pages have both valid extraction passes and after
# personally checking omissions/exclusions:
bash scripts/paper_review.sh approve-coverage my-paper
```

Only authored-statement contradiction/ambiguity candidates can be confirmed as
findings. Coding agents must pass `--reviewer-type assistant`; assistant source
checks remain visibly distinct from human-confirmed findings. A visual observation
does not become an alleged author mistake. If its
verification changes, its prior reviewer decision is cleared. Coverage approval
is fingerprinted to the current claim inventory/passes and does not attest that
all experiments are valid or all external checks are resolved.

## Scope limits and extension points

- Text-layer PDFs work now. Scanned/sparse pages remain incomplete until OCR or
  manual/visual coverage support is added; they are not silently counted covered.
- Section labels are parser hints, not a certified document outline. Complex
  tables/vector figures still need inspection through the rendered pages.
- Claim extraction/verifiers are LLM-based and can miss or misinterpret claims.
  An independent second pass and explicit source quotes reduce, not eliminate,
  these risks. Human coverage review remains necessary.
- External citation retrieval, advanced statistical checks, theorem verification,
  experiment reproduction and richer table parsing are adapters to add—not
  capabilities claimed by this MVP.
- Public source contents can contain personal information. Approval is a real
  inspection gate, not a regex-derived anonymity certificate.
- Input/config changes do not overwrite adjudicated history. Ingest/fork into a
  new project ID for a different source, redaction configuration or model run.
- Run one writer per project at a time; concurrent jobs should use separate
  project IDs. This MVP is a local CLI/workspace system, not a multi-user service.
- The report clearly says **partial review** until every in-scope page has both
  usable extraction passes and every extracted claim has a verification outcome,
  with no failed tasks. Scope exclusions are separately visible. Even
  then it says automated passes completed, not “paper verified.”

The earlier eight-claim demos remain useful regression tests, but their 8/8 label
agreement is not whole-paper coverage and is never imported as a completeness
certificate for this workflow.
