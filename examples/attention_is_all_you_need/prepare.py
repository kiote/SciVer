"""Prepare self-authored claim checks from a pinned Attention Is All You Need PDF."""
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/attention_is_all_you_need"
PDF_URL = "https://arxiv.org/pdf/1706.03762v7"
PDF_SHA256 = "bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697"
DPI = 216
# PDF point coordinates; bounds include captions but exclude adjacent sections.
CROPS = {
    "table1": {"page": 6, "box": [100, 68, 522, 205]},
    "table2": {"page": 8, "box": [100, 68, 522, 256]},
    "table3": {"page": 9, "box": [100, 68, 522, 398]},
    "section6_1": {"page": 8, "box": [100, 394, 522, 649]},
}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def extract_section(text, start, end):
    match = re.search(start + r"(.*?)" + end, text, re.S)
    if not match:
        raise ValueError("Expected section boundaries not found in the pinned PDF")
    body = match.group(1).strip()
    # The table is supplied as an actual PDF crop, not retyped into context.
    if "Table 3: Variations on the Transformer" in body:
        a = body.index("Table 3: Variations on the Transformer")
        b = body.index("development set, newstest2013. We used beam search", a)
        body = body[:a] + body[b:]
    return body


def build_claims():
    paper = "data/attention_is_all_you_need/paper.json"
    image = lambda key: f"data/attention_is_all_you_need/{key}.png"
    claims = [
        {"sample_id": "attention-direct-1", "claim_type": "direct", "label": True,
         "claim": "Table 2 reports a BLEU score of 28.4 for Transformer (big) on the English-to-German newstest2014 test.",
         "type": "table", "item": "2", "section": ["6.1"], "image_path": image("table2")},
        {"sample_id": "attention-direct-2", "claim_type": "direct", "label": False,
         "claim": "Table 3 lists N = 12 for the base Transformer configuration.",
         "type": "table", "item": "3", "section": ["6.2"], "image_path": image("table3")},
        {"sample_id": "attention-parallel-1", "claim_type": "parallel", "label": True,
         "claim": "Table 1 lists O(n) sequential operations for recurrent layers, while Table 2 reports 27.3 English-to-German BLEU for Transformer (base model).",
         "item1_type": "table", "item1": "1", "item1_path": image("table1"),
         "item2_type": "table", "item2": "2", "item2_path": image("table2"), "section": ["4", "6.1"]},
        {"sample_id": "attention-parallel-2", "claim_type": "parallel", "label": False,
         "claim": "Table 2 and the prose in Section 6.1 report the same numerical English-to-French BLEU score for the big Transformer model.",
         "item1_type": "table", "item1": "2", "item1_path": image("table2"),
         # In this repo 'chart' selects the generic image/caption store. This is a text crop, not a chart.
         "item2_type": "chart", "item2": "section6.1", "item2_path": image("section6_1"), "section": ["6.1"]},
        {"sample_id": "attention-sequential-1", "claim_type": "sequential", "label": True,
         "claim": "Using the base/big training-cost entries printed in Table 2 and their parameter counts in Table 3, dividing FLOPs by parameter count gives roughly 2.1 times as many training FLOPs per parameter for big as for base.",
         "item1_type": "table", "item1": "2", "item1_path": image("table2"),
         "item2_type": "table", "item2": "3", "item2_path": image("table3"), "section": ["6.1", "6.2"]},
        {"sample_id": "attention-sequential-2", "claim_type": "sequential", "label": False,
         "claim": "The printed values in Tables 2 and 3 imply that big has a lower training FLOP count per parameter than base, after dividing each Table 2 training cost by its corresponding Table 3 parameter count.",
         "item1_type": "table", "item1": "2", "item1_path": image("table2"),
         "item2_type": "table", "item2": "3", "item2_path": image("table3"), "section": ["6.1", "6.2"]},
        {"sample_id": "attention-analytical-1", "claim_type": "analytical", "label": True,
         "claim": "Comparing just the polynomial factors in Table 1, ignoring hidden Big-O constants, n = 128 and d = 512 make the self-attention factor n squared times d equal to one quarter of the recurrent factor n times d squared. This is a comparison of the expressions, not measured wall-clock time.",
         "type": "table", "item": "1", "section": ["4"], "image_path": image("table1")},
        {"sample_id": "attention-analytical-2", "claim_type": "analytical", "label": False,
         "claim": "For fixed d, doubling n multiplies the self-attention polynomial factor in Table 1 by two and the recurrent polynomial factor by four.",
         "type": "table", "item": "1", "section": ["4"], "image_path": image("table1")},
    ]
    for claim in claims:
        claim["paper_path"] = paper
    return claims


def prepare():
    for tool in ("pdftotext", "pdftoppm"):
        if not shutil.which(tool):
            raise RuntimeError(f"Install Poppler first: missing {tool}")
    DATA.mkdir(parents=True, exist_ok=True)
    pdf = DATA / "paper.pdf"
    if not pdf.exists():
        response = requests.get(PDF_URL, timeout=90)
        response.raise_for_status()
        if not response.content.startswith(b"%PDF-"):
            raise ValueError("Source did not return a PDF")
        pdf.write_bytes(response.content)
    actual = hashlib.sha256(pdf.read_bytes()).hexdigest()
    if actual != PDF_SHA256:
        raise ValueError("PDF checksum differs from the pinned article; review before proceeding")
    subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", str(pdf), str(DATA / "paper.txt")], check=True)
    text = (DATA / "paper.txt").read_text().replace("\f", "\n")
    # Remove standalone PDF footer page numbers before delimiting body sections.
    text = re.sub(r"(?m)^\s*\d+\s*$", "", text)
    sections = [
        {"section_id": "4", "section_name": "4 Why Self-Attention",
         "text": extract_section(text, r"\n4\s+Why Self-Attention\s*\n", r"\n5\s+Training\s*\n")},
        {"section_id": "6.1", "section_name": "6.1 Machine Translation",
         "text": extract_section(text, r"\n6\.1\s+Machine Translation\s*\n", r"\n6\.2\s+Model Variations\s*\n")},
        {"section_id": "6.2", "section_name": "6.2 Model Variations",
         "text": extract_section(text, r"\n6\.2\s+Model Variations\s*\n", r"\n6\.3\s+English Constituency Parsing\s*\n")},
    ]
    if "41.0" not in sections[1]["text"]:
        raise ValueError("Expected Section 6.1 value was not found")

    for page in sorted({x["page"] for x in CROPS.values()}):
        prefix = DATA / f"page{page}"
        subprocess.run(["pdftoppm", "-f", str(page), "-l", str(page), "-r", str(DPI),
                        "-singlefile", "-png", str(pdf), str(prefix)], check=True)
    crop_hashes = {}
    for name, info in CROPS.items():
        with Image.open(DATA / f"page{info['page']}.png") as page_image:
            bounds = tuple(round(v * DPI / 72) for v in info["box"])
            crop = page_image.crop(bounds).convert("RGB")
            crop.save(DATA / f"{name}.png")
        crop_hashes[name] = hashlib.sha256((DATA / f"{name}.png").read_bytes()).hexdigest()

    paper = {"sections": sections,
             "tables": {
                 "1": {"capture": "Table 1 (PDF page 6): Maximum path lengths, per-layer complexity and minimum sequential operations for layer types; n is sequence length and d is representation dimension."},
                 "2": {"capture": "Table 2 (PDF page 8): BLEU scores on English-to-German and English-to-French newstest2014 and estimated training costs (FLOPs)."},
                 "3": {"capture": "Table 3 (PDF page 9): Transformer architecture variations; metrics on English-to-German newstest2013 development set, and parameter counts in millions. Unlisted values match the base configuration."}},
             "image_paths": {"section6.1": {"caption": "Text excerpt (not a chart) from Section 6.1 Machine Translation, PDF page 8."}}}
    write_json(DATA / "paper.json", paper)
    write_json(DATA / "claims.json", build_claims())
    renderer = subprocess.run(["pdftoppm", "-v"], capture_output=True, text=True, check=True)
    provenance = {"title": "Attention Is All You Need", "arxiv_id": "1706.03762v7",
                  "url": PDF_URL, "pdf_sha256": actual,
                  "renderer": (renderer.stderr or renderer.stdout).splitlines()[0], "dpi": DPI,
                  "crops": CROPS, "crop_sha256": crop_hashes,
                  "labels": "Self-authored, source-checked demonstration; not official SciVer annotations",
                  "source_issue": "Table 2 prints EN-FR big BLEU 41.8, whereas Section 6.1 prose prints 41.0"}
    write_json(ROOT / "examples/attention_is_all_you_need/source.json", provenance)
    print("Prepared 8 self-authored claims and 4 original PDF crops.")
    print("Inputs: data/attention_is_all_you_need/claims.json")
    return DATA / "claims.json"


if __name__ == "__main__":
    prepare()
