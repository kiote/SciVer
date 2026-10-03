"""CLI for a generic PDF review; all provider calls require approved prepared inputs."""
import argparse
import json
import webbrowser
from pathlib import Path

from paper_review.ingest import prepare
from paper_review.pipeline import run
from paper_review.report import build
from paper_review.schema import coverage, digest
from paper_review.language import validate_summary
from paper_review.store import WORK, excluded, load, page_signature, save
from utils.constant import DEFAULT_MODEL, DEFAULT_PI_THINKING


def page_numbers(value, count):
    if value == "all":
        return set(range(1, count+1))
    selected = set()
    for part in value.split(','):
        if '-' in part:
            a,b = map(int, part.split('-',1))
            selected.update(range(a,b+1))
        else:
            selected.add(int(part))
    if not selected or min(selected)<1 or max(selected)>count:
        raise ValueError("Page selection is empty or outside the document")
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    ingest = sub.add_parser("ingest", help="Prepare any local PDF/HTTPS PDF URL; no model calls")
    ingest.add_argument("source")
    ingest.add_argument("--id", default=None)
    ingest.add_argument("--title", default=None)
    ingest.add_argument("--redact", action="append", default=[], help="Additional private literal to mask; kept only in ignored workspace")
    approve = sub.add_parser("approve-inputs", help="Explicitly acknowledge inspection of selected prepared images/text")
    approve.add_argument("project")
    approve.add_argument("--pages", default="all")
    analyze = sub.add_parser("run", help="Resume budgeted extraction/audit/verification; no gold labels")
    analyze.add_argument("project")
    analyze.add_argument("--pages", default="all")
    analyze.add_argument("--max-calls", type=int, default=200, help="Safety cap on new tasks; a full run exits paused/incomplete if exhausted")
    analyze.add_argument("--partial", action="store_true", help="Explicitly allow an intentionally limited stage/page run")
    analyze.add_argument("--stage", choices=("all", "extract", "verify"), default="all")
    analyze.add_argument("--batch-size", type=int, default=8, choices=range(1,13))
    analyze.add_argument("--workers", type=int, default=2, choices=range(1,5))
    analyze.add_argument("--model", default=DEFAULT_MODEL)
    analyze.add_argument("--thinking", default=DEFAULT_PI_THINKING, choices=("low","medium","high","xhigh","max"))
    exclude = sub.add_parser("exclude-pages", help="Explicitly scope out unprocessed non-scientific pages; never silently skip")
    exclude.add_argument("project")
    exclude.add_argument("--pages", required=True)
    exclude.add_argument("--reason", required=True)
    report = sub.add_parser("report", help="Rebuild cached generic HTML without provider calls")
    report.add_argument("project")
    report.add_argument("--open", action="store_true")
    status = sub.add_parser("status")
    status.add_argument("project")
    sub.add_parser("list", help="List all paper workspaces and their review coverage; no model calls")
    review = sub.add_parser("adjudicate", help="Record a reviewer decision, not a model confidence score")
    review.add_argument("project")
    review.add_argument("claim")
    review.add_argument("--decision", required=True, choices=("confirmed","dismissed","needs_evidence"))
    review.add_argument("--note", required=True)
    review.add_argument("--presentation", type=Path, default=None,
                        help="Optional short-language Problem/Evidence/Effect/Actions JSON for the reader report")
    review.add_argument("--issue-id", default=None, help="Group related flagged claims into one reviewed issue")
    review.add_argument("--reviewer-type", choices=('human','assistant'), default='human',
                        help="Use assistant for coding-agent source checks; do not impersonate human review")
    cov = sub.add_parser("approve-coverage", help="Explicit human coverage acknowledgement; never automatic")
    cov.add_argument("project")
    args = parser.parse_args()
    try:
        if args.command == "list":
            projects = []
            for folder in sorted(WORK.glob('*')):
                if not (folder / 'document.json').exists():
                    continue
                _, document, state = load(folder.name)
                progress = coverage(document, state)
                projects.append({"id": folder.name, "title": document["title"], "pages": progress["total_pages"],
                                 "audited_pages": progress["audited_pages"], "claims": progress["claims"],
                                 "verified": progress["verified"], "confirmed_findings": progress["confirmed_findings"],
                                 "status": progress["label"]})
            print(json.dumps(projects, indent=2, ensure_ascii=False))
            return
        if args.command == "ingest":
            identifier = prepare(args.source, args.id, args.title, args.redact)
            path, document, state = load(identifier)
            build(path, document, state)
            return
        path, document, state = load(args.project)
        if args.command == "approve-inputs":
            pages = page_numbers(args.pages, len(document["pages"]))
            for p in document["pages"]:
                if p["number"] in pages:
                    state.setdefault("approved_pages", {})[str(p["number"])] = page_signature(p)
            save(path, state)
            print(f"Recorded input-review acknowledgement for {len(pages)} pages. This is not an automatic PII guarantee.")
        elif args.command == "exclude-pages":
            numbers = page_numbers(args.pages, len(document['pages']))
            if not args.reason.strip():
                raise ValueError("An explicit scope reason is required")
            for number in numbers:
                if f'primary-{number}' in state.get('passes', {}) or f'audit-{number}' in state.get('passes', {}):
                    raise ValueError("Cannot scope out an already analysed page; use a new project to avoid outcome-based exclusions")
            for page in document['pages']:
                if page['number'] in numbers:
                    state.setdefault('page_exclusions', {})[str(page['number'])] = {'reason':args.reason,'page_sha256':page_signature(page)}
            state.pop('coverage_approval',None)
            save(path,state)
        elif args.command == "run":
            pages = page_numbers(args.pages, len(document["pages"]))
            all_scope = {p['number'] for p in document['pages'] if not excluded(p,state)}
            if not args.partial and (not all_scope.issubset(pages) or args.stage != 'all'):
                raise ValueError("Default runs require all configured stages and in-scope pages. Use --partial for an intentional limited run.")
            run(path, document, state, pages, args.max_calls, args.model, args.thinking,
                stage=args.stage, batch_size=args.batch_size, workers=args.workers)
            state['execution']['mode']='partial' if args.partial else 'full'
            save(path,state)
        elif args.command == "adjudicate":
            claim = next(c for c in state["claims"] if c["id"] == args.claim)
            if args.decision == "confirmed" and (claim.get("verification",{}).get("status") not in {"contradicted","ambiguous"} or claim["origin"] != "paper_statement"):
                raise ValueError("Only a grounded authored-statement candidate can become a confirmed finding")
            presentation = validate_summary(json.loads(args.presentation.read_text())) if args.presentation else None
            claim["review"] = {"decision": args.decision, "note": args.note, "reviewer_type": args.reviewer_type,
                               "issue_id": args.issue_id or claim['id'],
                               "verification_sha256": digest(claim.get("verification",{}))}
            if presentation is not None:
                claim['review']['presentation']=presentation
            save(path,state)
        elif args.command == "approve-coverage":
            progress = coverage(document,state)
            if not progress["inventory_complete"]:
                raise ValueError("Extraction/audit is incomplete or contains unreadable pages/units")
            state["coverage_approval"] = digest({"passes":state.get("passes",{}), "claims":[c["id"] for c in state["claims"]], "exclusions":state.get('page_exclusions',{})})
            save(path,state)
        elif args.command == "status":
            print(json.dumps(coverage(document,state),indent=2))
            return
        target = build(path,document,state)
        if args.command == 'run' and not args.partial and not coverage(document,state)['automated_checks_complete']:
            parser.exit(3, 'INCOMPLETE: configured checks remain pending/failed. Review the report and resume; no successful full-run completion is claimed.\n')
        if args.command == "report" and args.open:
            webbrowser.open(target.as_uri())
    except (ValueError,PermissionError,FileNotFoundError,StopIteration) as exc:
        # No raw provider dumps or credentials; paths remain local, not public snapshots.
        parser.exit(2, f"Review stopped: {type(exc).__name__}: {exc}\n")


if __name__ == "__main__":
    main()
