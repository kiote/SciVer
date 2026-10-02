"""Download only the assets for a pinned, label-balanced 16-example SciVer slice."""
import hashlib
import json
from collections import Counter
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image

REPO = "chengyewang/SciVer"
REVISION = "5695ac384d247ae5df2a7b73568dc63d189296b0"
SEED = 215
TYPES = ("direct", "parallel", "sequential", "analytical")
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/sciver-mini"
MANIFEST = ROOT / "benchmarks/slice16.manifest.json"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def fetch(path):
    target = DATA / path
    if not target.exists():
        url = f"https://huggingface.co/datasets/{REPO}/resolve/{REVISION}/{quote(path)}"
        response = requests.get(url, timeout=90)
        response.raise_for_status()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(response.content)
    return target


def select_indices(examples):
    selected, seen = [], set()
    for typ in TYPES:
        for label in (True, False):
            candidates = [i for i, x in enumerate(examples)
                          if x["claim_type"] == typ and x["label"] is label]
            candidates.sort(key=lambda i: sha256(f"{SEED}:{i}".encode()))
            picked = 0
            for i in candidates:
                x = examples[i]
                # Do not pick both original and perturbed versions of the same question.
                key = (x["paperid"], typ, x["request_id"])
                if key in seen:
                    continue
                selected.append(i)
                seen.add(key)
                picked += 1
                if picked == 2:
                    break
            if picked != 2:
                raise ValueError(f"Not enough distinct {typ}/{label} examples")
    return selected


def prepare():
    source = fetch("testset.json")
    examples = json.loads(source.read_bytes())
    indices = select_indices(examples)
    queries, assets = [], {}
    for index in indices:
        original = examples[index]
        # Exclude gold explanations and original/perturbed statements from inference inputs.
        fields = ("paperid", "claim_type", "claim", "label", "section", "request_id",
                  "type", "item", "item1", "item2", "item1_type", "item2_type")
        query = {k: original[k] for k in fields if k in original}
        query["sample_id"] = f"test-{index:04d}"
        for field in ("paper_path", "image_path", "item1_path", "item2_path"):
            if field not in original:
                continue
            remote = original[field].removeprefix("./SciVer/")
            if not remote.startswith(("papers/", "images/")) or ".." in Path(remote).parts:
                raise ValueError(f"Unexpected dataset asset path: {remote}")
            local = fetch(remote)
            asset = {"source_sha256": sha256(local.read_bytes())}
            if field != "paper_path":
                prepared = DATA / "prepared_images" / f"{local.stem}.jpg"
                prepared.parent.mkdir(parents=True, exist_ok=True)
                with Image.open(local) as image:
                    image = image.convert("RGB")
                    asset["original_dimensions"] = list(image.size)
                    image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                    if min(image.size) < 224:
                        scale = 224 / min(image.size)
                        image = image.resize(tuple(round(v * scale) for v in image.size),
                                             Image.Resampling.LANCZOS)
                    image.save(prepared, "JPEG", quality=90)
                    asset["prepared_dimensions"] = list(image.size)
                local = prepared
                asset["prepared_sha256"] = sha256(local.read_bytes())
            assets[remote] = asset
            query[field] = local.relative_to(ROOT).as_posix()
        queries.append(query)

    manifest = {
        "dataset": REPO, "revision": REVISION, "split": "testset.json",
        "license": "cc-by-4.0", "seed": SEED,
        "source_sha256": sha256(source.read_bytes()),
        "selection": "SHA256(seed:index) ranked within type/label; 2 per label/type; no duplicate questions",
        "image_preprocessing": "RGB JPEG quality 90; longest side <=1600 then shortest side >=224",
        "examples": [{"sample_id": q["sample_id"], "source_index": i,
                      "paperid": q["paperid"], "claim_type": q["claim_type"], "label": q["label"]}
                     for i, q in zip(indices, queries)],
        "assets": assets,
    }
    if MANIFEST.exists() and json.loads(MANIFEST.read_text()) != manifest:
        raise ValueError("Downloaded/prepared assets differ from the saved manifest")
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    output = DATA / "slice16.json"
    output.write_text(json.dumps(queries, indent=2, ensure_ascii=False) + "\n")
    print(f"Prepared {len(queries)} real examples: {dict(Counter(q['claim_type'] for q in queries))}")
    print(f"Inputs: {output.relative_to(ROOT)}; manifest: {MANIFEST.relative_to(ROOT)}")
    return output


if __name__ == "__main__":
    prepare()
