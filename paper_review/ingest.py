"""Generic local/HTTPS PDF ingestion with source IDs and reviewable input redaction."""
import re
from urllib.parse import urlsplit, urlunsplit

import requests

from paper_review.schema import digest
from paper_review.store import project_path, read_json, write_json

CONTACT = re.compile(r"\b[^\s@]+@[^\s@]+\.[A-Za-z]{2,}\b|\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b|/Users/[^\s]+|/home/[^\s]+|github_pat_[A-Za-z0-9_]+|gh[pousr]_[A-Za-z0-9]{15,}|sk-[A-Za-z0-9_-]{20,}|Bearer\s+[A-Za-z0-9_./+-]{20,}")


def prepare(source, project_id=None, title=None, redactions=()):
    import pymupdf
    if str(source).startswith("https://"):
        parts = urlsplit(str(source))
        if parts.username or parts.password:
            raise ValueError("Authenticated URLs are not supported")
        response = requests.get(str(source), stream=True, timeout=90)
        response.raise_for_status()
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > 50*1024*1024:
                raise ValueError("PDF download exceeds 50 MiB")
            chunks.append(chunk)
        content = b"".join(chunks)
        # Never persist signed query strings, passwords or personal source paths.
        reference = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    else:
        from pathlib import Path
        content = Path(source).read_bytes()
        reference = "Local PDF (original source path not stored)"
    if len(content) > 50*1024*1024 or not content.startswith(b"%PDF-"):
        raise ValueError("Expected a PDF smaller than 50 MiB")
    sha = digest(content)
    project_id = project_id or "paper-"+sha[:12]
    target = project_path(project_id)
    config = {"source_sha256": sha, "redactions": list(redactions), "ingest_version": 2,
              "parser": pymupdf.VersionBind, "dpi": 180, "title": title or project_id,
              "reader_language_policy": "ste-inspired-v1"}
    if (target / "document.json").exists():
        previous = read_json(target / "document.json")
        if previous["ingest_config"] == config:
            print(f"Reusing prepared workspace: {project_id}")
            return project_id
        raise ValueError("Existing project differs; use a new project ID rather than overwrite its review")
    target.mkdir(parents=True, exist_ok=True)
    (target / "original.pdf").write_bytes(content)
    doc = pymupdf.open(stream=content, filetype="pdf")
    if doc.is_encrypted or not 1 <= len(doc) <= 500:
        raise ValueError("Encrypted PDFs and documents over 500 pages are not supported")
    pages = []
    section_hint = "Unassigned / front matter"
    for index, page in enumerate(doc):
        raw = page.get_text()
        warnings, rectangles = [], []
        if index == 0:
            abstracts = page.search_for("Abstract")
            if abstracts:
                rectangles.append(pymupdf.Rect(0, 0, page.rect.width, min(r.y0 for r in abstracts)))
                warnings.append("First-page pre-abstract title/author block masked")
            else:
                warnings.append("No abstract anchor: inspect author/name content manually")
        terms = list(redactions) + [m.group(0) for m in CONTACT.finditer(raw)]
        for term in set(terms):
            if term:
                rectangles.extend(page.search_for(term))
        for rect in rectangles:
            page.add_redact_annot(rect, fill=(1, 1, 1))
        if rectangles:
            page.apply_redactions()
            warnings.append(f"{len(rectangles)} redaction regions applied; this is not a PII guarantee")
        units = []
        for block in page.get_text("blocks"):
            if block[6] != 0:
                continue
            text = block[4].strip()
            if text:
                first_line = text.splitlines()[0].strip()
                if len(first_line) < 120 and (re.match(r"^\d+(?:\.\d+)*\s+[A-Z]", first_line)
                                             or first_line.lower() in {"abstract", "references", "bibliography", "appendix"}):
                    section_hint = first_line
                units.append({"id": f"p{index+1:03d}-u{len(units)+1:03d}", "page": index+1,
                              "role": "text", "section_hint": section_hint, "bbox": [round(v, 2) for v in block[:4]], "text": text})
        needs_ocr = len(" ".join(u["text"] for u in units)) < 40
        units.append({"id": f"p{index+1:03d}-visual", "page": index+1, "role": "visual",
                      "section_hint": section_hint, "bbox": [0, 0, round(page.rect.width,2), round(page.rect.height,2)],
                      "text": "Full-page visual evidence; tables, diagrams, equations and captions may not be fully represented by text blocks."})
        if needs_ocr:
            warnings.append("Text layer missing/sparse: OCR or visual coverage review required")
        image = f"pages/p{index+1:03d}.jpg"
        (target / "pages").mkdir(exist_ok=True)
        scale = min(2.5, 2000/page.rect.width, 2000/page.rect.height)
        pixels = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
        blob = pixels.tobytes("jpeg", jpg_quality=85)
        (target / image).write_bytes(blob)
        pages.append({"number": index+1, "units": units, "image": image,
                      "image_sha256": digest(blob), "needs_ocr": needs_ocr, "privacy_warnings": warnings})
    doc.set_metadata({})
    doc.del_xml_metadata()
    for name in doc.embfile_names():
        doc.embfile_del(name)
    doc.save(target / "prepared.pdf", garbage=4, deflate=True)
    doc.close()
    document = {"schema_version": 1, "id": project_id, "title": config["title"],
                "source_reference": reference, "source_sha256": sha, "ingest_config": config,
                "pages": pages, "privacy": "Review prepared text/images before approving any provider calls. Regex redaction cannot guarantee removal of names, IDs or sensitive content."}
    write_json(target / "document.json", document)
    write_json(target / "state.json", {"passes": {}, "claims": [], "approved_pages": {}})
    print(f"Prepared {project_id}: {len(pages)} pages, {sum(len(p['units']) for p in pages)} source units. No model calls; inputs are not yet approved.")
    return project_id
