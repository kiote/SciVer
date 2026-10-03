"""Prepare aggregate-table claim checks for Hooshyar et al.'s 2026 DKT preprint."""
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/responsible_dkt"
TITLE = "Neural-Symbolic Knowledge Tracing: Injecting Educational Knowledge into Deep Learning for Responsible Learner Modelling"
PDF_URL = "https://arxiv.org/pdf/2604.08263v1"
PDF_SHA256 = "5c3972aa216dbed2eeb7eb29c79be64c4ff5425bf2481aa85f32123c4fa16073"
DPI = 216
CROPS = {
    "table4": {"page": 18, "box": [70, 68, 542, 555]},
    "table5": {"page": 19, "box": [70, 74, 542, 262]},
    "table6": {"page": 19, "box": [70, 274, 542, 465]},
}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def extract_body(text, start, end):
    match = re.search(start + r"(.*?)" + end, text, re.S)
    if not match:
        raise ValueError("Expected section boundaries not found in pinned PDF")
    body = match.group(1)
    body = re.sub(r"(?m)^\s*arXiv Template\s+A P REPRINT\s*$", "", body)
    body = re.sub(r"(?m)^\s*\d+\s*$", "", body)
    # Bibliographic citations are unnecessary for these numeric checks. Exclude names/contact links.
    body = re.sub(r"\[[^\]]+\]", "", body)
    return body.strip()


def build_claims():
    image = lambda number: f"data/responsible_dkt/table{number}.png"
    shared_sections = ["3.4.1", "4.2"]
    claims = [
        {"sample_id": "rdkt-direct-1", "claim_type": "direct", "label": True,
         "claim": "In Table 4, Responsible-DKT with 10% training data and Full sequence length has AUC 0.88 and accuracy 0.85.",
         "type": "table", "item": "4", "image_path": image(4)},
        {"sample_id": "rdkt-direct-2", "claim_type": "direct", "label": False,
         "claim": "Table 5 reports a late-stage prediction error of 11.98% for Classic-DKT at sequence length 50.",
         "type": "table", "item": "5", "image_path": image(5)},
        {"sample_id": "rdkt-parallel-1", "claim_type": "parallel", "label": True,
         "claim": "For Full sequences, Table 5 reports lower early-stage error for Responsible-DKT than Classic-DKT (14.35% versus 18.92%), and Table 6 also reports lower inconsistency for Responsible-DKT (0.36 versus 0.44).",
         "item1_type": "table", "item1": "5", "item1_path": image(5),
         "item2_type": "table", "item2": "6", "item2_path": image(6)},
        {"sample_id": "rdkt-parallel-2", "claim_type": "parallel", "label": False,
         "claim": "For Full sequences, Responsible-DKT has both a lower middle-stage error in Table 5 and lower volatility in Table 6 than BaseNS-DKT.",
         "item1_type": "table", "item1": "5", "item1_path": image(5),
         "item2_type": "table", "item2": "6", "item2_path": image(6)},
        {"sample_id": "rdkt-sequential-1", "claim_type": "sequential", "label": True,
         "claim": "Using the printed Full-sequence values, replacing Classic-DKT with Responsible-DKT reduces early-stage error in Table 5 by about 24.2% relative to Classic-DKT, while reducing inconsistency in Table 6 by about 18.2% relative to Classic-DKT; the first relative reduction is larger.",
         "item1_type": "table", "item1": "5", "item1_path": image(5),
         "item2_type": "table", "item2": "6", "item2_path": image(6)},
        {"sample_id": "rdkt-sequential-2", "claim_type": "sequential", "label": False,
         "claim": "Table 5 reports errors as percentages while Table 6 reports inconsistency as proportions. Converting Table 6's Full-sequence inconsistency values from 0.44 for Classic-DKT to 0.36 for Responsible-DKT into percentages gives a decrease of about 18.2 percentage points.",
         "item1_type": "table", "item1": "5", "item1_path": image(5),
         "item2_type": "table", "item2": "6", "item2_path": image(6)},
        {"sample_id": "rdkt-analytical-1", "claim_type": "analytical", "label": True,
         "claim": "Table 6 provides a counterexample to equating the lowest volatility with the lowest inconsistency: for Full sequences, BaseNS-DKT has lower volatility than Responsible-DKT (0.11 versus 0.17) but higher inconsistency (0.44 versus 0.36).",
         "type": "table", "item": "6", "image_path": image(6)},
        {"sample_id": "rdkt-analytical-2", "claim_type": "analytical", "label": False,
         "claim": "In every matching training-ratio and sequence-length setting printed in Table 4, Responsible-DKT has strictly higher accuracy than Classic-DKT.",
         "type": "table", "item": "4", "image_path": image(4)},
    ]
    for claim in claims:
        claim["paper_path"] = "data/responsible_dkt/paper.json"
        claim["section"] = list(shared_sections)
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
            raise ValueError("Expected a PDF")
        pdf.write_bytes(response.content)
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    if digest != PDF_SHA256:
        raise ValueError("Source PDF differs from the pinned version")
    subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", str(pdf), str(DATA / "paper.txt")], check=True)
    text = (DATA / "paper.txt").read_text().replace("\f", "\n")
    sections = [
        {"section_id": "3.4.1", "section_name": "3.4.1 Evaluation",
         "text": extract_body(text, r"\n3\.4\.1\s+Evaluation\s*\n", r"\n3\.4\.2\s+Interpretability\s*\n")},
        {"section_id": "4.2", "section_name": "4.2 Quantitative analysis of model performances",
         "text": extract_body(text, r"\n4\.2\s+Quantitative analysis of model performances\s*\n",
                              r"\n4\.3\s+Qualitative analysis of model performances")},
    ]
    for page in sorted({c["page"] for c in CROPS.values()}):
        subprocess.run(["pdftoppm", "-f", str(page), "-l", str(page), "-r", str(DPI), "-singlefile", "-png",
                        str(pdf), str(DATA / f"page{page}")], check=True)
    image_hashes = {}
    for name, spec in CROPS.items():
        with Image.open(DATA / f"page{spec['page']}.png") as page:
            crop = page.crop(tuple(round(v * DPI / 72) for v in spec["box"])).convert("RGB")
            crop.save(DATA / f"{name}.png")
        image_hashes[name] = hashlib.sha256((DATA / f"{name}.png").read_bytes()).hexdigest()
    paper = {"sections": sections, "image_paths": {}, "tables": {
        "4": {"capture": "Table 4 (PDF page 18): Performance of BaseNS-DKT, Responsible-DKT and Classic-DKT across training ratios (10, 50, 100%) and sequence lengths (10, 50, 100, Full). N denotes sequence length."},
        "5": {"capture": "Table 5 (PDF page 19): Early-, middle- and late-stage prediction error by sequence length; all values are percentages."},
        "6": {"capture": "Table 6 (PDF page 19): Volatility and inconsistency of mastery trajectories; both metrics are proportions on a 0–1 scale."},
    }}
    write_json(DATA / "paper.json", paper)
    write_json(DATA / "claims.json", build_claims())
    renderer = subprocess.run(["pdftoppm", "-v"], capture_output=True, text=True, check=True)
    provenance = {"title": TITLE, "credit": "Danial Hooshyar et al. (2026)", "arxiv_id": "2604.08263v1",
                  "submitted": "2026-04-09", "status": "preprint", "url": PDF_URL, "pdf_sha256": digest,
                  "renderer": (renderer.stderr or renderer.stdout).splitlines()[0], "dpi": DPI,
                  "crops": CROPS, "crop_sha256": image_hashes,
                  "context_sections": [s["section_id"] for s in sections],
                  "privacy": "Only aggregate tables and selected body text are sent. Author/contact lists, references, bibliographic citations and individual-student examples are excluded.",
                  "labels": "Self-authored and source-checked before inference; not official SciVer annotations"}
    write_json(ROOT / "examples/responsible_dkt/source.json", provenance)
    print("Prepared 8 claim checks using aggregate Tables 4–6 and sections 3.4.1/4.2.")
    return DATA / "claims.json"


if __name__ == "__main__":
    prepare()
