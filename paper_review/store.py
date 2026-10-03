import json
import re
from pathlib import Path

from paper_review.schema import digest

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "data/reviews"
OUT = ROOT / "outputs/reviews"


def project_path(project_id):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,80}", project_id):
        raise ValueError("Use a simple lowercase project ID, not a path")
    path = (WORK / project_id).resolve()
    if not path.is_relative_to(WORK.resolve()):
        raise ValueError("Project path escapes review workspace")
    return path


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def load(project_id):
    path = project_path(project_id)
    document = read_json(path / "document.json")
    if document.get("id") != project_id:
        raise ValueError("Document ID does not match the review workspace")
    if digest((path / "original.pdf").read_bytes()) != document["source_sha256"]:
        raise ValueError("Original PDF changed since ingestion")
    state = read_json(path / "state.json") if (path / "state.json").exists() else {"passes": {}, "claims": [], "approved_pages": {}}
    for page in document["pages"]:
        image = (path / page["image"]).resolve()
        if not image.is_relative_to(path) or digest(image.read_bytes()) != page["image_sha256"]:
            raise ValueError("Prepared page image changed; re-ingest and review inputs")
    return path, document, state


def page_signature(page):
    return digest(page)


def excluded(page, state):
    record = state.get("page_exclusions", {}).get(str(page["number"]), {})
    return record if record.get("page_sha256") == page_signature(page) else None


def approved(page, state):
    return state.get("approved_pages", {}).get(str(page["number"])) == page_signature(page)


def save(path, state):
    write_json(path / "state.json", state)
