# SciVer fork: paper review workflow

For a new paper, use the generic `paper_review/` system rather than writing another
paper-specific demo or HTML renderer. See `docs/paper_review_system.md` and
`scripts/paper_review.sh --help`.

## Scope and scientific honesty

- Keep labelled benchmark evaluation separate from real-paper review.
- Inventory actual authored claims; never mix invented false controls into a
  paper's inconsistency count. Visual observations are not author quotations.
- Track every page/source unit, first extraction and second coverage pass.
  Eight checked examples do not constitute whole-paper coverage.
- Preserve qualifiers, units, approximations and evidence scope. Missing evidence
  is not a contradiction. Do not infer experimental truth from internal consistency.
- Use five-way statuses, retain unresolved/external checks, and distinguish model
  candidates from explicit reviewer-confirmed findings. Coding-agent source checks
  must use `--reviewer-type assistant`, never pretend to be human review.
- Do not assert a full review when pages/units are unreadable, unprocessed or
  unverified. Automated coverage is not a completeness proof; human review remains.

## Reuse and speed

- Pin the source PDF hash. Workspaces/cache under `data/reviews/<id>/` and reports
  under `outputs/reviews/<id>/` are ignored.
- Default to the complete configured pipeline, not a tiny pilot. Intentional
  limited runs require `--partial`. A full run cannot be reported successful if
  its budget was exhausted or configured checks remain pending/failed.
- Resume cached extraction/verification rather than rerunning paid model tasks.
  Set an explicit `--max-calls` cap; do not launch an unbounded whole-paper run.
- Generate reports from saved state with `report <id>`; no new inference is needed.
- Use the shared STE-inspired report language policy in `docs/report_language.md`.
  Reader cards must state Problem / Evidence / Effect / Action in short sentences.
  Give one action per item. Keep technical names, numbers, units and qualifiers.
  Supply source-checked presentation JSON for reviewed issues; do not paste long
  raw model notes as the main reader text. Do not claim certified STE compliance.
- Reader-facing reports should lead with findings and evidence. Explain review
  scope in plain language; keep per-page units, upload-consent flags, pass counters
  and processing diagnostics inside collapsed technical audit details.
- Reader-facing reports must omit validly dismissed flags entirely, including
  claim cards, review notes, group links and filter entries. Preserve those records
  in the private audit ledger; do not make readers wade through discarded leads.
- Prefer shared reporting/assets over per-paper copies. Add tested adapters for
  missing capabilities (OCR, reference retrieval, statistics, code/data checks).

## Privacy and publication

- Inspect prepared page images/text before approving provider uploads. Do not
  auto-approve a document merely because regex redaction ran.
- Mask private names, contacts, credentials, paths and sensitive student examples
  as appropriate. Automatic masks cannot guarantee PII removal.
- Never commit source PDFs, page images, raw source text, task caches, auth files,
  environments, or session history. Review any exported responses before publishing.
- Do not include personal home paths or Git identities in public artifacts; use
  GitHub noreply metadata for new commits. Do not rewrite existing history without
  explicit approval.
- Preserve `docs/article_assessment_flow.*` as legacy benchmark/demo documentation;
  do not overwrite those diagrams unless the task specifically requires it.

Run `python -m unittest discover -s tests -v` before finalizing changes. Install
`requirements-review.txt` to include the optional PDF-ingestion tests.
