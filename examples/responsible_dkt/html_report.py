"""Build an offline, evidence-linked HTML review from the saved Responsible-DKT run."""
import argparse
import base64
import hashlib
import html
import json
import os
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote

from acc_evaluation import parse_verdict
from examples.responsible_dkt.prepare import ROOT, DATA, PDF_SHA256, build_claims
from model_inference.pi_rpc import _query_images, SYSTEM_PROMPT
from utils.constant import COT_PROMPT, DEFAULT_MODEL
from utils.input_processing import prepare_qa_text_input

EXAMPLE = ROOT / "examples/responsible_dkt"
PAPER_QUOTE = (
    "Regardless of sequence length or training ratio, Responsible-DKT outperforms the other models "
    "in terms of AUC, accuracy, and—most importantly—minority-class recall and F1-score."
)
# Source origin is explicit: a rejected test control is NOT automatically an error in the paper.
PAPER_RELATED = {"rdkt-analytical-2"}
NEGATIVE_CONTROLS = {"rdkt-direct-2", "rdkt-parallel-2", "rdkt-sequential-2"}

# Manually transcribed and checked against the pinned Table 4 image. Not inferred from GPT output.
TABLE4 = [
    (10, "10",  ".78", ".84", ".80", ".73"),
    (10, "50",  ".84", ".83", ".85", ".73"),
    (10, "100", ".82", ".78", ".87", ".74"),
    (10, "Full", ".85", ".81", ".88", ".76"),
    (50, "10",  ".83", ".83", ".86", ".75"),
    (50, "50",  ".86", ".83", ".87", ".75"),
    (50, "100", ".84", ".80", ".88", ".75"),
    (50, "Full", ".86", ".82", ".90", ".78"),
    (100, "10",  ".85", ".82", ".86", ".75"),
    (100, "50",  ".86", ".84", ".88", ".76"),
    (100, "100", ".84", ".81", ".88", ".76"),
    (100, "Full", ".86", ".84", ".89", ".80"),
]

CSS = """
:root{--bg:#f5f6fa;--ink:#182339;--muted:#5b667b;--line:#dce2ec;--purple:#5144bd;--teal:#087f77;--amber:#965b12;--soft-amber:#fff6e6;--green:#166348;--red:#a32936}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:24px}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}a{color:var(--purple);text-underline-offset:3px}a:hover{text-decoration-thickness:2px}button{font:inherit;cursor:pointer}button:focus-visible,a:focus-visible,summary:focus-visible{outline:3px solid #6b63de;outline-offset:4px}
.top{max-width:1260px;margin:auto;padding:27px 32px;display:flex;align-items:center;justify-content:space-between;gap:18px}.brand{font-size:14px;font-weight:750;letter-spacing:.1em;text-transform:uppercase}.top button,.filter{border:1px solid var(--line);background:white;color:var(--ink);border-radius:9px;padding:8px 15px}.layout{max-width:1260px;margin:auto;padding:0 32px 60px;display:grid;grid-template-columns:180px minmax(0,1fr);gap:38px}.nav{position:sticky;top:25px;align-self:start;padding-top:10px;font-size:14px}.nav a{display:block;padding:10px 0;color:var(--muted);text-decoration:none}.nav a:hover{color:var(--purple)}.nav .label{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);font-weight:700;margin-bottom:10px}
.eyebrow{font-size:12px;letter-spacing:.1em;font-weight:750;text-transform:uppercase;color:var(--purple)}h1{font-size:clamp(30px,4.2vw,48px);line-height:1.15;letter-spacing:-.035em;max-width:780px;margin:14px 0 18px}h2{font-size:27px;line-height:1.3;letter-spacing:-.025em;margin:0 0 18px}h3{font-size:19px;line-height:1.35;margin:0 0 12px}p{margin:0 0 16px}.muted{color:var(--muted)}.paper-title{font-size:17px;max-width:820px}.meta{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0 25px}.pill{border:1px solid var(--line);border-radius:50px;padding:4px 12px;font-size:12px;background:white}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:26px 0}.stat{border:1px solid var(--line);border-radius:13px;background:white;padding:17px}.stat strong{display:block;font-size:30px;line-height:1.2;margin-bottom:9px}.stat span{display:block;font-size:12px;line-height:1.5;color:var(--muted)}.notice{border-left:4px solid var(--purple);padding:15px 19px;background:#ecebfa;border-radius:0 9px 9px 0;margin-bottom:34px;font-size:14px}.notice strong{color:#393087}
section{margin:40px 0}.card{background:white;border:1px solid var(--line);border-radius:16px;padding:26px;margin:18px 0}.finding{border-top:4px solid #d4a051}.badge{display:inline-block;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;padding:4px 9px;border-radius:5px;margin-bottom:13px}.badge.issue{color:var(--amber);background:var(--soft-amber)}.badge.control{color:#4d4e99;background:#f0f0fc}.badge.supported{color:var(--green);background:#eaf5ef}.verdict{font-weight:650}.source-quote{margin:18px 0 23px;padding:20px 22px;border-left:3px solid #d4a051;background:#fcf8ef;font-size:17px;line-height:1.7}.source-quote footer{font-size:12px;color:var(--muted);margin-top:12px}.counter-grid{display:grid;grid-template-columns:1fr 1fr;gap:15px}.counter{padding:20px;background:#f7f8fc;border:1px solid var(--line);border-radius:10px}.counter .setting{font-size:13px;font-weight:700}.counter .conclusion{font-size:13px;margin:7px 0 0;color:var(--muted)}svg{display:block;width:100%;height:auto;margin:9px 0}.rbar{fill:var(--purple)}.cbar{fill:var(--teal)}.track{fill:#e3e7ef}.chart-label{font-size:12px;fill:var(--ink)}.chart-tick{font-size:10px;fill:var(--muted)}.key{display:flex;gap:18px;margin:14px 0 7px;font-size:12px;color:var(--muted)}.key span:before{content:"";display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:6px}.key .r:before{background:var(--purple)}.key .c:before{background:var(--teal)}
.callout{padding:16px 19px;background:#eaf5ef;border:1px solid #cfe5d9;border-radius:9px;font-size:14px;margin-top:20px}.callout.warn{background:var(--soft-amber);border-color:#eed9b8}.suggestion{padding:18px 20px;border:1px dashed #b9b3de;border-radius:10px;margin-top:22px}.suggestion .label{font-size:11px;font-weight:750;letter-spacing:.08em;color:var(--purple);text-transform:uppercase;margin-bottom:8px}.suggestion p{margin-bottom:7px}.suggestion small{color:var(--muted)}
details{border:1px solid var(--line);border-radius:9px;margin:15px 0;background:#fff}summary{cursor:pointer;padding:13px 17px;font-size:14px;font-weight:650}.inside{padding:3px 18px 18px}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.04em}tbody tr:last-child td{border-bottom:none}.table-scroll{overflow-x:auto}.exception{background:#fff3e9}.tie{background:#f0effa}.negative{color:var(--red);font-weight:750}.positive{color:var(--green)}.tiny{font-size:12px;color:var(--muted)}
.filters{display:flex;flex-wrap:wrap;gap:8px;margin:20px 0}.filter{font-size:12px}.filter[aria-pressed=true]{color:white;background:var(--purple);border-color:var(--purple)}.checks{display:grid;grid-template-columns:1fr 1fr;gap:16px}.check{margin:0;padding:22px}.check .claim{font-size:15px;line-height:1.6}.check .id{font-size:11px;color:var(--muted);margin-bottom:10px}.check details{margin-bottom:0}.model-output{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;line-height:1.7}.origin-note{font-size:12px;color:var(--muted);margin-bottom:12px}.status{display:flex;flex-wrap:wrap;gap:10px;align-items:center;font-size:12px;color:var(--muted);margin:16px 0 9px}.matched{color:var(--green);font-weight:700}.evidence img{display:block;max-width:100%;height:auto;cursor:zoom-in;border:1px solid var(--line);border-radius:7px;background:white}.evidence figcaption{font-size:12px;line-height:1.6;color:var(--muted);margin-top:12px}.evidence figure{margin:5px 0}.evidence:target{border-color:var(--purple);box-shadow:0 0 0 3px #e4e1f8}.steps{list-style:none;padding:0;counter-reset:step}.steps li{position:relative;padding:0 0 22px 49px;counter-increment:step}.steps li:before{content:counter(step);position:absolute;left:0;top:0;background:#e7e5f7;border-radius:50%;width:29px;height:29px;color:var(--purple);font-weight:750;font-size:13px;display:grid;place-items:center}.steps strong{display:block;margin-bottom:3px}.steps p{font-size:14px;color:var(--muted);margin:0}.hash{font:11px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace;overflow-wrap:anywhere;color:var(--muted)}.link-list{display:flex;flex-wrap:wrap;gap:10px 23px;font-size:13px}.footer{font-size:12px;color:var(--muted);border-top:1px solid var(--line);padding-top:20px;margin-top:30px}dialog{width:min(96vw,1600px);max-height:94vh;border:1px solid var(--line);border-radius:12px;padding:18px}dialog::backdrop{background:#132039b3}.dialog-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:15px}.dialog-top button{background:#f3f4f8;border:1px solid var(--line);border-radius:7px;padding:7px 12px}.image-scroll{overflow:auto;max-height:80vh}.image-scroll img{display:block;max-width:none;height:auto}[hidden]{display:none!important}
@media(max-width:960px){.layout{grid-template-columns:1fr;max-width:900px;gap:0}.nav{position:static;display:flex;flex-wrap:wrap;gap:0 18px;padding:0 0 24px}.nav .label{display:none}.nav a{font-size:12px}.stats{grid-template-columns:repeat(2,1fr)}}
@media(max-width:620px){.top,.layout{padding-left:19px;padding-right:19px}.top{padding-top:20px}.brand{font-size:11px}.top button{font-size:12px}.card{padding:19px}.checks,.counter-grid{grid-template-columns:1fr}.stats{gap:9px}.stat{padding:14px}h1{font-size:34px}h2{font-size:23px}.source-quote{padding:16px;font-size:15px}}
@media print{body{background:white;font-size:11pt}.top button,.nav,.filters,dialog{display:none!important}.layout{display:block;padding:0;max-width:none}.top{padding:0 0 14px}.stats{grid-template-columns:repeat(4,1fr)}.card,.counter{break-inside:avoid;box-shadow:none}.checks{display:block}.check{margin-bottom:15px}.check[hidden]{display:block!important}h1{font-size:27pt}a{color:inherit}.evidence img{max-height:none}.footer{margin-top:16px}}
"""

JS = """
const cards = [...document.querySelectorAll('[data-kind]')];
document.querySelectorAll('[data-filter]').forEach(button => {
  button.addEventListener('click', () => {
    document.querySelectorAll('[data-filter]').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
    cards.forEach(card => { card.hidden = button.dataset.filter !== 'all' && card.dataset.kind !== button.dataset.filter; });
    const count = cards.filter(card => !card.hidden).length;
    document.getElementById('filter-status').textContent = `${count} checks shown`;
  });
});
function revealHash() {
  const target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
  if (target && target.tagName === 'DETAILS') target.open = true;
}
window.addEventListener('hashchange', revealHash);
revealHash();
const dialog = document.getElementById('image-viewer');
document.querySelectorAll('.evidence img').forEach(image => {
  image.tabIndex = 0;
  const show = () => {
    const enlarged = document.getElementById('large-image');
    enlarged.src = image.src;
    enlarged.alt = image.alt;
    document.getElementById('image-title').textContent = image.alt;
    dialog.showModal();
  };
  image.addEventListener('click', show);
  image.addEventListener('keydown', event => { if (event.key === 'Enter') show(); });
});
document.getElementById('close-image').addEventListener('click', () => dialog.close());
document.getElementById('print-report').addEventListener('click', () => window.print());
"""


def escape(value):
    return html.escape(str(value), quote=True)


def inline_hash(text):
    return base64.b64encode(hashlib.sha256(text.encode()).digest()).decode()


def origin(row):
    if row["sample_id"] in PAPER_RELATED:
        return "paper", "Source-related accuracy check", "Paraphrases actual wording in section 4.2; the paper excerpt is shown above."
    if row["sample_id"] in NEGATIVE_CONTROLS:
        return "control", "Designed negative control", "Deliberately false test claim authored for this run. Not an error attributed to the paper's authors."
    return "supported", "Supported test claim", "Source-grounded test claim authored before inference; not a verbatim quotation from the paper."


def accuracy_rows():
    rows = []
    for train, length, responsible, classic, ra, ca in TABLE4:
        r, c = Decimal(responsible), Decimal(classic)
        rows.append({"training": train, "length": length, "responsible": r, "classic": c,
                     "delta_pp": (r-c)*100, "r_auc": Decimal(ra), "c_auc": Decimal(ca)})
    return rows


def bar_chart(title, responsible, classic):
    r, c = float(responsible)*100, float(classic)*100
    return f'''<svg viewBox="0 0 360 102" role="img" aria-label="{escape(title)}: Responsible-DKT {r:.0f}%, Classic-DKT {c:.0f}% accuracy">
    <title>{escape(title)}; zero-based 0–100% accuracy scale</title>
    <text x="0" y="15" class="chart-label">Responsible</text><rect x="88" y="3" width="228" height="17" rx="3" class="track"/><rect x="88" y="3" width="{r*2.28:.2f}" height="17" rx="3" class="rbar"/><text x="325" y="16" class="chart-label">{r:.0f}%</text>
    <text x="0" y="47" class="chart-label">Classic</text><rect x="88" y="35" width="228" height="17" rx="3" class="track"/><rect x="88" y="35" width="{c*2.28:.2f}" height="17" rx="3" class="cbar"/><text x="325" y="48" class="chart-label">{c:.0f}%</text>
    <text x="88" y="75" class="chart-tick">0%</text><text x="199" y="75" class="chart-tick">50%</text><text x="299" y="75" class="chart-tick">100%</text></svg>'''


def load_bundle(model):
    records = json.loads((EXAMPLE / f"results/{model}.inference.json").read_text())
    checks = json.loads((EXAMPLE / f"results/{model}.checks.json").read_text())
    source = json.loads((EXAMPLE / "source.json").read_text())
    expected = build_claims()
    if len(records) != len(expected) or len(checks["examples"]) != len(expected):
        raise ValueError("Cannot report an incomplete run")
    if source["arxiv_id"] != "2604.08263v1" or checks["paper"] != source["arxiv_id"]:
        raise ValueError("Unexpected paper revision")
    if hashlib.sha256((DATA / "paper.pdf").read_bytes()).hexdigest() != PDF_SHA256:
        raise ValueError("PDF provenance mismatch")
    paper = json.loads((DATA / "paper.json").read_text())
    text = " ".join(next(s["text"] for s in paper["sections"] if s["section_id"] == "4.2").split())
    if PAPER_QUOTE not in text:
        raise ValueError("Quoted source wording not found in extracted paper text")
    model_settings = records[0]["inference"]
    for record, definition, result in zip(records, expected, checks["examples"]):
        if any(record[k] != definition[k] for k in ("sample_id", "claim", "claim_type", "label")):
            raise ValueError("Saved claims differ from predefined checks")
        predicted = parse_verdict(record["response"])
        if result["sample_id"] != record["sample_id"] or result["prediction"] != predicted or result["expected"] != record["label"]:
            raise ValueError("Parsed verdicts differ from stored checks")
        if any(record["inference"][k] != model_settings[k] for k in ("provider", "model", "thinking")):
            raise ValueError("Mixed model configurations")
        _, prompt = prepare_qa_text_input(model, record, COT_PROMPT)
        images = _query_images(record)
        if hashlib.sha256(prompt.encode()).hexdigest() != result["prompt_sha256"]:
            raise ValueError("Prompt changed since inference")
        if [hashlib.sha256(base64.b64decode(b["data"])).hexdigest() for b in images] != result["image_sha256"]:
            raise ValueError("Submitted images changed since inference")
    if hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest() != checks["system_prompt_sha256"]:
        raise ValueError("System prompt changed since inference")
    for key, digest in source["crop_sha256"].items():
        if hashlib.sha256((DATA / f"{key}.png").read_bytes()).hexdigest() != digest:
            raise ValueError("Original PDF crop changed")
    return records, checks, source


def render_report(records, checks, source, images, output):
    if not output.resolve().is_relative_to(ROOT):
        raise ValueError("Keep the report inside the repo so local evidence links do not expose home paths")
    rows = accuracy_rows()
    wins = sum(r["delta_pp"] > 0 for r in rows)
    auc_wins = sum(r["r_auc"] > r["c_auc"] for r in rows)
    matched = sum(parse_verdict(r["response"]) is not None and parse_verdict(r["response"]) == r["label"] for r in records)
    if matched != checks["correct"] or len(records) != checks["n"]:
        raise ValueError("Report totals do not match saved verdicts")
    selected = records[0]["inference"]
    e = escape
    relative = lambda path: quote(Path(os.path.relpath(path, output.parent)).as_posix(), safe="/")

    row_html = []
    for r in rows:
        css = "exception" if r["delta_pp"] < 0 else "tie" if r["delta_pp"] == 0 else ""
        sign = "negative" if r["delta_pp"] < 0 else "positive" if r["delta_pp"] > 0 else ""
        row_html.append(f'<tr class="{css}"><td>{r["training"]}%</td><td>{e(r["length"])}</td><td>{r["responsible"]:.2f}</td><td>{r["classic"]:.2f}</td><td class="{sign}">{r["delta_pp"]:+.1f} pp</td><td>{r["r_auc"]:.2f} / {r["c_auc"]:.2f}</td></tr>')
    controls = sum(origin(r)[0] == "control" for r in records)
    supported = sum(origin(r)[0] == "supported" for r in records)
    paper_count = sum(origin(r)[0] == "paper" for r in records)
    card_html = []
    for record in records:
        kind, label, explanation = origin(record)
        prediction = parse_verdict(record["response"])
        result_text = "No explicit verdict" if prediction is None else "Supported / yes" if prediction else "Refuted / no"
        expected_text = "entailed" if record["label"] else "refuted"
        ok = prediction is not None and prediction == record["label"]
        tables = [int(record["item"])] if "item" in record else [int(record["item1"]), int(record["item2"])]
        links = " · ".join(f'<a href="#table{number}">Table {number}</a>' for number in tables)
        badge_class = "issue" if kind == "paper" else kind
        # Escape before adding minimal bold markup; model text is never executed as HTML/JS.
        response = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', e(record["response"]))
        card_html.append(f'''<article class="card check" data-kind="{kind}" id="{e(record['sample_id'])}">
          <span class="badge {badge_class}">{label}</span><div class="id">{e(record['sample_id'])} · {e(record['claim_type'])}</div>
          <p class="origin-note">{explanation}</p><p class="claim">{e(record['claim'])}</p>
          <div class="status"><span class="verdict">{result_text}</span><span>Expected: {expected_text}</span><span class="{'matched' if ok else 'negative'}">{'Matched test label' if ok else 'Did not match test label'}</span></div>
          <p class="tiny">Evidence: {links}</p><details><summary>Read the saved model explanation</summary><div class="inside model-output">{response}</div></details></article>''')
    evidence_html = []
    evidence_names = {"table4": "Table 4 · Performance across training ratios and sequence lengths", "table5": "Table 5 · Early, middle and late error rates", "table6": "Table 6 · Volatility and inconsistency"}
    for key, title in evidence_names.items():
        page = source["crops"][key]["page"]
        data_url = "data:image/png;base64," + base64.b64encode(images[key]).decode()
        evidence_html.append(f'''<details class="evidence" id="{key}"><summary>{e(title)} — PDF page {page}</summary><div class="inside"><figure>
          <img src="{data_url}" alt="{e(title)}" loading="lazy" title="Click or press Enter to inspect at full resolution">
          <figcaption>Actual PDF crop; not a reconstructed table. Click the image for full resolution. <a href="{relative(DATA / 'paper.pdf')}#page={page}">Open local PDF on page {page}</a> · <a href="https://arxiv.org/pdf/2604.08263v1#page={page}" target="_blank" rel="noopener noreferrer">Public source</a><br>Crop SHA256: <span class="hash">{e(source['crop_sha256'][key])}</span></figcaption>
          </figure></div></details>''')
    source_quote = e(PAPER_QUOTE)
    date = datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC")
    policy = f"default-src 'none'; img-src data:; script-src 'sha256-{inline_hash(JS)}'; style-src 'sha256-{inline_hash(CSS)}'; base-uri 'none'; form-action 'none'"

    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{e(policy)}">
<title>Responsible-DKT — evidence review</title><style>{CSS}</style></head><body>
<header class="top"><div class="brand">SciVer / article evidence review</div><button id="print-report" type="button">Print / save PDF</button></header>
<div class="layout"><nav class="nav" aria-label="Report sections"><div class="label">In this report</div>
<a href="#overview">Overview</a><a href="#finding">Source inconsistency</a><a href="#checks">All eight checks</a><a href="#evidence">Original table images</a><a href="#method">How we checked</a><a href="#provenance">Limits & provenance</a></nav>
<main><div id="overview"><div class="eyebrow">Responsible-DKT · targeted review</div>
<h1>One accuracy claim needs qualification.</h1>
<p class="paper-title">{e(source['title'])}</p><p class="muted">{e(source['credit'])} · preprint submitted 9 April 2026</p>
<div class="meta"><span class="pill">arXiv 2604.08263v1</span><span class="pill">{e(selected['model'])} / {e(selected['thinking'])} reasoning</span><span class="pill">Aggregate evidence only</span></div>
<div class="stats"><div class="stat"><strong>{paper_count}</strong><span>Source-related wording issue<br>accuracy generalization</span></div><div class="stat"><strong>{controls}</strong><span>Designed negative controls<br>not author mistakes</span></div><div class="stat"><strong>{supported}</strong><span>Supported test claims<br>tables and arithmetic</span></div><div class="stat"><strong>{matched}/{len(records)}</strong><span>Matched predefined labels<br>not a score for the paper</span></div></div>
<div class="notice"><strong>Important distinction.</strong> Four test claims were refuted, but <strong>only one is tied to an actual statement in the paper</strong>. The other three were deliberately false controls created before inference. This is not a whole-paper audit.</div></div>

<section id="finding"><h2>What inconsistency was found?</h2><article class="card finding"><span class="badge issue">Source wording needs qualification</span>
<h3>“Higher accuracy in every setting” is too broad for Table 4.</h3>
<p>The paper's section 4.2 makes a universal performance statement. We checked its <strong>accuracy</strong> component against matching Responsible-DKT and Classic-DKT rows.</p>
<blockquote class="source-quote">“{source_quote}”<footer>Exact excerpt · section 4.2 · PDF page 17 · <a href="{relative(DATA / 'paper.pdf')}#page=17">inspect the source</a></footer></blockquote>
<div class="key"><span class="r">Responsible-DKT</span><span class="c">Classic-DKT</span></div>
<div class="counter-grid"><div class="counter"><div class="setting">10% training data · sequence length 10</div>{bar_chart('10% training / sequence length 10', '.78', '.84')}<p class="conclusion"><strong>Counterexample:</strong> accuracy is 6 percentage points lower, not higher.</p></div>
<div class="counter"><div class="setting">50% training data · sequence length 10</div>{bar_chart('50% training / sequence length 10', '.83', '.83')}<p class="conclusion"><strong>Tie:</strong> both are 0.83, so “strictly higher” does not apply.</p></div></div>
<p class="tiny">Bar charts use a zero-based 0–100% accuracy scale. Derived values are transcribed from <a href="#table4">the original Table 4 image</a>; they are not invented model estimates.</p>
<div class="callout"><strong>Keep the distinction between metrics.</strong> Responsible-DKT has higher reported accuracy in <strong>{wins}/12</strong> matched settings and higher reported AUC in <strong>{auc_wins}/12</strong>. The accuracy exceptions do not negate the separate AUC advantage. Neither comparison is a statistical significance test.</div>
<details><summary>Show all 12 matched Table 4 comparisons</summary><div class="inside"><div class="table-scroll"><table><thead><tr><th>Training</th><th>Length</th><th>Responsible accuracy</th><th>Classic accuracy</th><th>Difference</th><th>AUC: Responsible / Classic</th></tr></thead><tbody>{''.join(row_html)}</tbody></table></div><p class="tiny">Accuracy is shown as a proportion; differences are percentage points. Highlighted rows are the lower-accuracy case and the tie. Manually transcribed and checked against the pinned PDF crop.</p></div></details>
<div class="suggestion"><div class="label">Suggested narrower wording · reviewer suggestion</div><p>In the reported settings, Responsible-DKT achieved higher AUC than Classic-DKT throughout, and higher accuracy in 10 of 12 matched settings, with one tie and one lower-accuracy case.</p><small>This suggestion concerns this table comparison only. No manuscript text has been changed.</small></div>
<details><summary>How GPT-5.5 explained this check</summary><div class="inside model-output">{e(next(r['response'] for r in records if r['sample_id'] == 'rdkt-analytical-2'))}</div></details>
</article></section>

<section id="checks"><h2>Which claims were checked?</h2><p class="muted">Each card states where the claim came from, the expected label, the model's actual verdict and the evidence used. “Refuted” is a verdict on that claim—not automatically an allegation about the paper.</p>
<div class="filters" role="group" aria-label="Filter checks"><button class="filter" data-filter="all" aria-pressed="true">All {len(records)}</button><button class="filter" data-filter="paper" aria-pressed="false">Source-related {paper_count}</button><button class="filter" data-filter="control" aria-pressed="false">Negative controls {controls}</button><button class="filter" data-filter="supported" aria-pressed="false">Supported checks {supported}</button></div>
<p class="tiny" id="filter-status" aria-live="polite">{len(records)} checks shown</p><div class="checks">{''.join(card_html)}</div>
<div class="card"><h3>A percentage-point trap used as a test control</h3><p>Table 6's Full-sequence inconsistency changes from <strong>0.44 to 0.36</strong>. That means 44% to 36%:</p>
<div class="table-scroll"><table><tbody><tr><td>Absolute decrease</td><td>(0.44 − 0.36) × 100</td><td><strong>8 percentage points</strong></td></tr><tr><td>Relative decrease</td><td>(0.44 − 0.36) ÷ 0.44 × 100</td><td><strong>≈18.2%</strong></td></tr></tbody></table></div>
<p class="tiny">The deliberately false claim called this “18.2 percentage points.” GPT rejected it correctly. <strong>We did not find that mistaken wording in the paper.</strong></p></div></section>

<section id="evidence"><h2>Inspect the original evidence</h2><p class="muted">These are the aggregate-table crops used to construct the checks. The submitted images were JPEG-encoded versions of these same crops; their hashes are saved with the run. Click a table heading, then click the image to zoom.</p>{''.join(evidence_html)}</section>

<section id="method"><h2>How were the inconsistencies checked?</h2><div class="card"><ol class="steps">
<li><strong>Pin the public source.</strong><p>Download arXiv 2604.08263v1 and verify its PDF SHA256. Do not silently substitute another revision.</p></li>
<li><strong>Select the relevant evidence.</strong><p>Render Tables 4–6 directly from PDF pages 18–19 at 216 DPI. Supply metric definitions from section 3.4.1 and results prose from section 4.2.</p></li>
<li><strong>Define the eight checks before inference.</strong><p>The coding assistant authored and source-checked four entailed and four refuted claims. Three refuted claims are deliberate controls; the accuracy check paraphrases actual source wording. There was no independent expert annotation.</p></li>
<li><strong>Run the configured model on isolated inputs.</strong><p>{e(selected['provider'])}/{e(selected['model'])}, {e(selected['thinking'])} reasoning. One fresh conversation per claim, no tools or personal context. Gold labels are not supplied to the model.</p></li>
<li><strong>Parse the final verdict and retain the explanation.</strong><p>Score the explicit final yes/no, not stray words in the explanation. Saved verdicts agree with all eight predefined labels; that is label agreement on this small demonstration, not experimental validation.</p></li>
<li><strong>Cross-check source cells and arithmetic.</strong><p>Inspect the actual table rows, test the universal accuracy claim with counterexamples, and distinguish proportions, percentages and percentage points.</p></li></ol></div></section>

<section id="provenance"><h2>What this report does—and does not—establish</h2><div class="card"><p><strong>Established within the reported table:</strong> there is a lower-accuracy case and a tie that require qualification of a universal accuracy statement.</p>
<p><strong>Not established:</strong> whether the training code is correct, the data split is leakage-free, effects are statistically significant, learner support is effective, or the paper's broader findings are invalid. The full paper has not been exhaustively checked. Model training-data overlap is unknown.</p>
<p><strong>Privacy:</strong> only aggregate tables and selected body text are used. Author/contact lists, bibliographic citations and individual-student examples are excluded. This local HTML contains no trackers, remote fonts or external scripts.</p>
<details><summary>Reproducibility and saved artifacts</summary><div class="inside"><p class="tiny">PDF SHA256</p><p class="hash">{e(source['pdf_sha256'])}</p><p class="tiny">Renderer: {e(source['renderer'])} · 216 DPI · model configuration is recorded by Pi, not independently attested by the upstream provider.</p>
<div class="link-list"><a href="{relative(EXAMPLE / ('results/' + selected['model'] + '.inference.json'))}">Full saved responses</a><a href="{relative(EXAMPLE / ('results/' + selected['model'] + '.checks.json'))}">Verdicts & input hashes</a><a href="{relative(EXAMPLE / 'source.json')}">Source & crop provenance</a><a href="https://arxiv.org/abs/2604.08263v1" target="_blank" rel="noopener noreferrer">Public paper record</a></div></div></details></div></section>
<footer class="footer">Generated {date} from the saved run; no new inference calls. Targeted source-consistency review, not peer review or a whole-paper correctness score. The local report and embedded source images remain under ignored <code>outputs/</code>.</footer>
</main></div><dialog id="image-viewer" aria-labelledby="image-title"><div class="dialog-top"><strong id="image-title">Original table</strong><button id="close-image" type="button">Close</button></div><div class="image-scroll"><img id="large-image" alt=""></div></dialog>
<script>{JS}</script></body></html>'''


def build_report(output, model=None):
    model = model or DEFAULT_MODEL.rsplit("/", 1)[-1]
    records, checks, source = load_bundle(model)
    images = {key: (DATA / f"{key}.png").read_bytes() for key in ("table4", "table5", "table6")}
    output = output.resolve()
    page = render_report(records, checks, source, images, output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")
    print(f"HTML report: {output.relative_to(ROOT) if output.is_relative_to(ROOT) else output.name}")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/responsible_dkt/report.html")
    parser.add_argument("--model", default=None, help="Saved model ID, e.g. gpt-5.5; no new inference calls")
    args = parser.parse_args()
    build_report(args.output, args.model)
