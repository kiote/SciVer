"""Paper-independent offline reports: coverage, source claims, candidates and reviewer decisions."""
import base64
import hashlib
import html
import json
import os
import re
from collections import Counter
from pathlib import Path
from urllib.parse import quote

from examples.report_assets import CSS, JS
from paper_review.schema import coverage, digest, review_decision
from paper_review.language import POLICY, reader_label, reader_summary
from paper_review.store import OUT, ROOT, approved, read_json


def e(value):
    return html.escape(str(value), quote=True)


def csp_hash(value):
    return base64.b64encode(hashlib.sha256(value.encode()).digest()).decode()


def reader_claims(state):
    """Valid dismissals stay in the audit ledger, never in the reader-facing HTML."""
    return [claim for claim in state.get('claims', []) if review_decision(claim) != 'dismissed']


def page_ranges(numbers):
    numbers = sorted(set(numbers))
    groups = []
    for number in numbers:
        if groups and number == groups[-1][-1] + 1:
            groups[-1].append(number)
        else:
            groups.append([number])
    return ', '.join(str(g[0]) if len(g) == 1 else f'{g[0]}–{g[-1]}' for g in groups) or 'none'


def review_scope(document, state, cov):
    pages = [p['page'] for p in cov['pages'] if not p['excluded']]
    if cov['automated_checks_complete']:
        checked = f"The check covers the reported statements on pages {page_ranges(pages)}. It compares them with the paper's text, tables, and figures."
    else:
        checked = (f"This review is not finished. Both reading passes cover {cov['audited_pages']} of {cov['in_scope_pages']} selected pages. "
                   f"{cov['not_checked']} statements still need a check.")
        if state.get('task_errors'):
            checked += f" {len(state['task_errors'])} processing tasks also need attention."
    grouped = {}
    for page in cov['pages']:
        if page['excluded']:
            grouped.setdefault(page['exclusion_reason'], []).append(page['page'])
    excluded = [(page_ranges(numbers), reason) for reason, numbers in grouped.items()]
    return checked, excluded


def action_fields(summary):
    evidence = ''.join(f'<li>{e(text)}</li>' for text in summary['evidence'])
    actions = ''.join(f'<li>{e(text)}</li>' for text in summary['actions'])
    replacement = (f'<details><summary>Proposed replacement text</summary><div class="inside"><p>{e(summary["replacement"])}</p><p class="tiny">Check this text before you use it.</p></div></details>' if summary.get('replacement') else '')
    return (f'<div class="action-fields"><h4>Problem</h4><p>{e(summary["problem"])}</p>'
            f'<h4>Evidence</h4><ul>{evidence}</ul><h4>Effect</h4><p>{e(summary["effect"])}</p>'
            f'<h4>Action</h4><ol>{actions}</ol></div>{replacement}')


def build(path, document, state):
    target = (OUT / document["id"] / "report.html").resolve()
    if not target.is_relative_to(OUT.resolve()):
        raise ValueError("Report path escapes the review output directory")
    content_state = {k: v for k, v in state.items() if k != "last_requested_tasks"}
    fingerprint = digest({"view": "reader-action-first-"+POLICY, "document": document, "state": content_state, "renderer": Path(__file__).read_bytes().hex(), "css": CSS, "js": JS})
    stamp = target.with_suffix(".cache.json")
    if target.exists() and stamp.exists() and read_json(stamp).get("signature") == fingerprint:
        print(f"Reusing unchanged report: {target.relative_to(ROOT.resolve())}")
        return target
    cov = coverage(document, state)
    model = state.get("analysis_config", {}).get("model", "Not run")
    scope_note, scope_exclusions = review_scope(document, state, cov)
    completion_note = ('The internal check is complete. Some statements need evidence outside this paper.' if cov['automated_checks_complete'] else 'The review is not complete. Do not use it as a check of the full paper.')
    exclusion_notes = ''.join(f'<li>Pages {e(pages)}: {e(reason)}</li>' for pages, reason in scope_exclusions)
    relative = lambda p: quote(Path(os.path.relpath(p, target.parent)).as_posix(), safe="/")
    cards = []
    quote_budget = 90
    claims = reader_claims(state)
    stop = set('the and for that this with from are was were has have had can may its our their these those into than only all not but such through between across which where while model models'.split())
    tokens = lambda text: {w.lower() for w in re.findall(r'[^\W\d_][\w-]{2,}', text) if 3 <= len(w) <= 32 and w.lower() not in stop}
    frequencies = Counter(word for c in claims for word in tokens(c['text']))
    ordered = sorted(claims, key=lambda c: (0 if review_decision(c) == 'confirmed' else 1 if c.get('verification',{}).get('status') in {'contradicted','ambiguous'} else 2 if c.get('verification') else 3, c['id']))
    for claim in ordered:
        verification = claim.get("verification", {})
        status = verification.get("status", "not_checked")
        decision = review_decision(claim)
        reviewer = claim.get('review',{}).get('reviewer_type','human')
        kind = "confirmed" if decision == "confirmed" and reviewer == 'human' else "candidate" if status in {"contradicted", "ambiguous"} and decision != "dismissed" else "other"
        decision_label = ('The assistant checked the source. A person must review the proposed change.' if decision == 'confirmed' and reviewer == 'assistant' else 'A person checked the source.' if decision == 'confirmed' else 'More evidence is required.' if decision == 'needs_evidence' else 'The evidence changed. Repeat the source check.' if decision.startswith('stale') else 'A person must review this result.')
        summary, summary_origin = reader_summary(claim, decision)
        refs = sorted({int(ref.split('-')[0][1:]) for ref in claim["source_unit_ids"] + verification.get("evidence_unit_ids", [])})
        links = " · ".join(f'<a href="#p{p:03d}">Page {p}</a>' for p in refs)
        calculations = ''.join(f'<p class="hash">{e(json.dumps(c, ensure_ascii=False))}</p>' for c in verification.get("calculations", []))
        review_note = claim.get('review',{}).get('note','') if decision in {'confirmed','needs_evidence'} else ''
        words = claim['text'].split()
        shown = min(len(words), 12, quote_budget)
        quote_budget -= shown
        excerpt = ' '.join(words[:shown]) + (' …' if shown < len(words) else '') if shown else 'Source excerpt omitted; inspect the linked prepared page.'
        topic = ' · '.join(sorted(tokens(claim['text']), key=lambda word: (frequencies[word], word))[:5]) or claim.get('kind','source claim')
        cards.append(f'''<article class="card check" data-kind="{kind}" id="{e(claim['id'])}">
          <span class="badge {'issue' if kind != 'other' else 'supported'}">{e(reader_label(claim,decision))}</span>
          <h3>{e(summary['title'])}</h3><p class="tiny">{e(decision_label)}</p>
          {action_fields(summary)}<p class="tiny">Read the source: {links}</p>
          <details><summary>Original check record (optional)</summary><div class="inside">
          <p class="hash">{e(claim['id'])} · {e(status)} · {e(decision)}</p><p>{e(excerpt)}</p>
          <p class="tiny">Topic keywords: {e(topic)}. {('The actions are proposed. Check the source before you use them.' if summary_origin != 'reviewed' else 'The source check supports this action plan.')}</p>
          <div class="model-output">{e(verification.get('explanation','Not checked yet'))}<p>{e(review_note)}</p>{calculations}</div></div></details></article>''')
    page_rows, page_views = [], []
    for page, progress in zip(document["pages"], cov["pages"]):
        n = page["number"]
        consent = approved(page, state)
        if progress['excluded']:
            page_rows.append(f'<tr><td><a href="#p{n:03d}">{n}</a></td><td>{len(page["units"])}</td><td>Not sent (excluded)</td><td colspan="3">Excluded from configured checks: {e(progress["exclusion_reason"])}</td></tr>')
        else:
            page_rows.append(f'<tr><td><a href="#p{n:03d}">{n}</a></td><td>{len(page["units"])}</td><td>{"approved" if consent else "input review required"}</td><td>{"done" if progress["primary"] else "pending"}</td><td>{"done" if progress["audit"] else "pending"}</td><td>{"OCR/visual coverage required" if page["needs_ocr"] else progress["unreadable_units"]}</td></tr>')
        image_link = relative(path / page["image"])
        audit = {x['unit_id']: x for x in state.get('passes',{}).get(f'audit-{n}',{}).get('units',[])}
        text_units = ''.join(f'<p class="tiny">{e(u["id"])} · {e(u.get("section_hint",""))} · {e(audit.get(u["id"],{}).get("disposition","not inventoried"))} · PDF bounds {e(u["bbox"])}</p>' for u in page['units'])
        page_views.append(f'''<details class="evidence" id="p{n:03d}"><summary>Prepared page {n} · {'approved' if consent else 'not approved for provider calls'}</summary>
          <div class="inside"><p class="tiny">{e('; '.join(page['privacy_warnings']) or 'Inspect manually: automated redaction cannot guarantee removal of sensitive content.')}</p>
          <img loading="lazy" src="{image_link}" alt="Prepared source page {n}">
          <details><summary>Extracted source units and second-pass dispositions</summary><div class="inside">{text_units or 'No usable text; OCR/visual coverage required.'}</div></details></div></details>''')
    reviewed = [c for c in claims if review_decision(c) not in {'pending human review','stale decision — re-review needed','invalid confirmation — re-review needed'}]
    groups = {}
    for claim in reviewed:
        key = claim.get('review',{}).get('issue_id') or claim['id']
        groups.setdefault(key, []).append(claim)
    review_cards = []
    def group_key(pair):
        group = pair[1]
        selected = next((c for c in group if c.get('review',{}).get('presentation')),group[0])
        summary,_ = reader_summary(selected,review_decision(selected))
        return (0 if review_decision(selected) == 'confirmed' else 1, summary['title'])
    group_order = sorted(groups.items(), key=group_key)
    for key, group in group_order:
        decision = review_decision(group[0])
        actor = group[0].get('review',{}).get('reviewer_type','human')
        selected = next((c for c in group if c.get('review',{}).get('presentation')),group[0])
        summary,_ = reader_summary(selected,review_decision(selected))
        related = ' · '.join(f'<a href="#{e(c["id"])}">Check {i+1}</a>' for i,c in enumerate(group))
        pages = sorted({int(ref.split('-')[0][1:]) for c in group for ref in c['source_unit_ids']+c.get('verification',{}).get('evidence_unit_ids',[])})
        sources = ' · '.join(f'<a href="#p{p:03d}">Page {p}</a>' for p in pages)
        review_cards.append(f'<article class="card"><span class="badge {"issue" if decision == "confirmed" else "control"}">{e(reader_label(selected,decision))}</span><h3>{e(summary["title"])}</h3>{action_fields(summary)}<p class="tiny">Read the source: {sources}</p><p class="tiny">Related checks: {related}. {"The assistant checked the source. A person must approve the final change." if actor == "assistant" else "A person checked the source."}</p></article>')
    proposed_cards = []
    for claim in claims:
        if review_decision(claim) != 'pending human review' or claim.get('verification',{}).get('status') not in {'contradicted','ambiguous'} or not claim.get('verification',{}).get('reader_summary'):
            continue
        summary,_ = reader_summary(claim,'pending human review')
        pages = sorted({int(ref.split('-')[0][1:]) for ref in claim['source_unit_ids']+claim.get('verification',{}).get('evidence_unit_ids',[])})
        sources = ' · '.join(f'<a href="#p{p:03d}">Page {p}</a>' for p in pages)
        proposed_cards.append(f'<article class="card"><span class="badge control">Check the source before you edit</span><h3>{e(summary["title"])}</h3>{action_fields(summary)}<p class="tiny">This is a proposed action, not a confirmed error. Read the source: {sources}</p></article>')
    proposed_section = (f'<details id="proposed-actions"><summary>Other points to check: {len(proposed_cards)} proposed actions</summary><div class="inside">'+''.join(proposed_cards)+'</div></details>') if proposed_cards else ''
    errors = ''.join(f'<li>{e(key)}: {e(value)}</li>' for key,value in state.get('task_errors',{}).items())
    status_counts = {}
    for claim in claims:
        name = claim.get('verification',{}).get('status','not_checked')
        status_counts[name] = status_counts.get(name,0)+1
    active_unresolved = sum(c.get('verification',{}).get('status') in {'ambiguous','insufficient_evidence','requires_external_verification'} for c in claims)
    sections = sorted({u.get('section_hint','Unassigned') for p in document['pages'] for u in p['units']})
    policy = f"default-src 'none'; img-src 'self' file: data:; style-src 'sha256-{csp_hash(CSS)}'; script-src 'sha256-{csp_hash(JS)}'; base-uri 'none'; form-action 'none'"
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
      <meta http-equiv="Content-Security-Policy" content="{e(policy)}"><title>{e(document['title'])} — review coverage</title><style>{CSS}</style></head><body data-live="{'true' if state.get('execution',{}).get('state') == 'running' else 'false'}">
      <header class="top"><div class="brand">SciVer / generic paper review</div><button id="print-report">Print / save PDF</button></header>
      <div class="layout"><nav class="nav"><a href="#overview">Overview</a><a href="#review-notes">Problems and actions</a><a href="#coverage">Review scope</a><a href="#claims">Full check list</a><a href="#evidence">Prepared page images</a><a href="#limits">Limits & next steps</a></nav><main>
      <section id="overview"><div class="eyebrow">{e(document['id'])}</div><h1>{e(document['title'])}</h1><div class="notice"><strong>{e(completion_note)}</strong><br>An automated review cannot prove that every error was found. A person must review the findings.</div>
      <div class="stats"><div class="stat"><strong>{cov['primary_pages']}/{cov['in_scope_pages']}</strong><span>Selected pages read<br>{cov['excluded_pages']} pages outside this review</span></div><div class="stat"><strong>{cov['audited_pages']}/{cov['in_scope_pages']}</strong><span>Selected pages read again</span></div><div class="stat"><strong>{cov['verified']}/{cov['claims']}</strong><span>Checks completed<br>not a score for the paper</span></div><div class="stat"><strong>{cov['source_checked_issue_groups']}</strong><span>Issue groups checked at the source<br>{cov['candidate_findings']} points still need a person to review them</span></div></div>
      <p class="tiny">{active_unresolved} active checks need more evidence or a clearer statement. {cov['not_checked']} checks are not complete.</p></section>
      <section id="review-notes"><h2>Problems and actions</h2><p class="muted">Read these source-checked issues and questions first. Check the proposed changes before you edit the paper. Related checks form one issue.</p>{''.join(review_cards) or '<p>No action plans have been checked against the source. Review the proposed points before you edit the paper.</p>'}{proposed_section}</section>
      <section id="coverage"><h2>Review scope</h2><div class="card"><p><strong>{e(scope_note)}</strong></p>
      <p>This review checks for differences within the paper. It does not validate cited studies, raw data, or code. It does not repeat the experiments.</p>
      {('<details><summary>Material outside this review</summary><div class="inside"><ul>'+exclusion_notes+'</ul></div></details>') if scope_exclusions else ''}</div>
      <details id="technical-audit"><summary>Technical audit details (optional)</summary><div class="inside"><p class="tiny">For checking processing completeness or debugging—not required to read the findings. Reading-pass completion is not a scientific correctness certificate.</p>
      <p class="hash">Execution: {e(state.get('execution',{}).get('state','not started'))} · Mode: {e(state.get('execution',{}).get('mode','legacy partial pilot'))} · Configured model: {e(model)} · Status codes: {e(json.dumps(status_counts))}</p>
      <details><summary>Detected section hints ({len(sections)})</summary><div class="inside">{''.join('<p>'+e(s)+'</p>' for s in sections)}</div></details>
      <div class="table-scroll"><table><thead><tr><th>Page</th><th>Units</th><th>Input consent</th><th>Extraction</th><th>Second pass</th><th>Unreadable</th></tr></thead><tbody>{''.join(page_rows)}</tbody></table></div><ul>{errors}</ul></div></details></section>
      <section><details id="claims"><summary>Full check list: {len(claims)} active records (optional)</summary><div class="inside">
      <p class="muted">Use this list only if you need the individual check records. A proposed action is not proof of an error.</p>
      <p><strong>Label guide:</strong> “Check this difference” means the statement and evidence may disagree. “Clarify this statement” means the scope or meaning is not clear. “Add missing evidence” means this check lacks evidence. “Check other sources” means the cited study, code, or data is required. “No conflict found” does not prove that the experiment is correct.</p>
      <div class="filters"><button class="filter" data-filter="all" aria-pressed="true">All active checks</button><button class="filter" data-filter="candidate" aria-pressed="false">Points to review</button><button class="filter" data-filter="confirmed" aria-pressed="false">Human source checks</button><button class="filter" data-filter="other" aria-pressed="false">Other checks</button></div>
      <p id="filter-status" class="tiny" aria-live="polite">{len(claims)} active checks shown</p><div class="checks">{''.join(cards) or '<p>No active checks to display.</p>'}</div></div></details></section>
      <section id="evidence"><h2>Read the source pages</h2><div class="notice">Use these pages to check the evidence. Before a new analysis, inspect the text and images for private information. Automatic masks do not guarantee its removal.</div>{''.join(page_views)}</section>
      <section id="limits"><h2>Review limits</h2><div class="card"><p>This review checks reported statements against the supplied evidence. It does not repeat experiments or prove theorems. It does not prove cause and effect. Statements that need other sources, code, or data remain open.</p>
      <p>Review each proposed change against the source. Obtain missing evidence before you decide. Approve a change only after that check.</p>
      <p>Source excerpts are limited to 90 words across the report. Complete source text stays in the private workspace; page images are linked locally rather than bundled for redistribution. No automated third-party literature retrieval is performed.</p>
      <p><a href="{relative(path / 'prepared.pdf')}">Inspect complete prepared PDF locally</a> · <a href="{relative(path / 'document.json')}">Prepared source units (private workspace)</a> · <a href="{relative(path / 'state.json')}">Complete claim inventory and review state (private)</a></p>
      <p>Model tasks are cached by source, evidence, prompt and model configuration. Resume does not needlessly rerun completed tasks. Provider-level retries may still consume quota.</p><p>Original source SHA256: <span class="hash">{e(document['source_sha256'])}</span></p>
      <p class="tiny">Source: {e(document['source_reference'])}. Workspace/report stay in ignored data/outputs directories. Do not publish without a content/privacy review. Scanned/sparse pages currently require an OCR adapter or manual review.</p></div></section>
      <footer class="footer">This report uses STE-inspired writing rules. Formal ASD-STE100 compliance has not been verified. The report is not a correctness score for the paper.</footer></main></div>
      <dialog id="image-viewer" aria-labelledby="image-title"><div class="dialog-top"><strong id="image-title"></strong><button id="close-image">Close</button></div><div class="image-scroll"><img id="large-image" alt=""></div></dialog><script>{JS}</script></body></html>'''
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page, encoding="utf-8")
    stamp.write_text(json.dumps({"signature": fingerprint})+'\n')
    print(f"Review report: {target.relative_to(ROOT.resolve())}")
    return target
