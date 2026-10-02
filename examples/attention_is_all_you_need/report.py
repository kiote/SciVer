"""Summarize a completed article demonstration; this is not a SciVer benchmark."""
import argparse
import base64
import hashlib
import json
import shutil
from pathlib import Path

from acc_evaluation import get_acc, parse_verdict
from examples.attention_is_all_you_need.prepare import ROOT, build_claims
from model_inference.pi_rpc import _query_images, SYSTEM_PROMPT
from utils.constant import COT_PROMPT
from utils.input_processing import prepare_qa_text_input

RESULTS = ROOT / "examples/attention_is_all_you_need/results"


def summarize(input_path):
    records = json.loads(input_path.read_text())
    expected = build_claims()
    if len(records) != len(expected):
        raise ValueError("Refusing to score an incomplete article run")
    for actual, source in zip(records, expected):
        for field in ("sample_id", "claim", "claim_type", "label"):
            if actual.get(field) != source[field]:
                raise ValueError("Run does not match the predefined article checks")
        if not actual.get("response"):
            raise ValueError("Empty response in article run")
    configurations = [r["inference"] for r in records]
    selected = configurations[0]
    if any(any(c[k] != selected[k] for k in ("provider", "model", "thinking")) for c in configurations):
        raise ValueError("Run contains different model configurations")
    model = selected["model"]
    metrics = get_acc(records)
    RESULTS.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(input_path, RESULTS / f"{model}.inference.json")
    (RESULTS / f"{model}.eval.json").write_text(json.dumps(metrics, indent=2) + "\n")

    details, invalid = [], 0
    for record in records:
        verdict = parse_verdict(record["response"])
        correct = verdict is not None and verdict == record["label"]
        invalid += verdict is None
        _, prompt = prepare_qa_text_input(model, record, COT_PROMPT)
        images = _query_images(record)
        details.append({"sample_id": record["sample_id"], "claim_type": record["claim_type"],
                        "claim": record["claim"], "expected": record["label"], "prediction": verdict,
                        "correct": correct, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                        "image_sha256": [hashlib.sha256(base64.b64decode(b["data"])).hexdigest() for b in images]})
    report = {"paper": "1706.03762v7", "model": f"{selected['provider']}/{model}",
              "thinking": selected["thinking"], "system_prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
              "n": len(records), "correct": sum(d["correct"] for d in details),
              "invalid": invalid, "examples": details,
              "limitation": "Self-authored examples on a familiar paper, not official SciVer labels or a generalization benchmark"}
    (RESULTS / f"{model}.checks.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    lines = ["# Attention Is All You Need: claim-checking demonstration", "",
             "Source: [arXiv 1706.03762v7](https://arxiv.org/pdf/1706.03762v7).",
             f"Model configuration: **{selected['provider']}/{model}, {selected['thinking']} reasoning**.", "",
             f"**{report['correct']}/{len(records)} matched the predefined labels; {invalid} invalid verdicts.**", "",
             "These are self-authored demonstrations, not official SciVer examples. The paper is widely known and may be in model training data.", "",
             "| Check | Type | Expected | Model verdict | Matched |", "|---|---|---|---|---|"]
    for d in details:
        label = "entailed" if d["expected"] else "refuted"
        answer = "invalid" if d["prediction"] is None else ("yes" if d["prediction"] else "no")
        lines.append(f"| {d['sample_id']} | {d['claim_type']} | {label} | {answer} | {'yes' if d['correct'] else 'no'} |")
    lines += ["", "## Checks", ""]
    for d in details:
        lines += [f"**{d['sample_id']}**: {d['claim']}", ""]
    lines += ["## Source consistency check", "",
              "The downloaded PDF's Table 2 shows EN-FR BLEU **41.8** for Transformer (big), whereas its Section 6.1 prose shows **41.0**.",
              "The parallel-2 check asks whether those numbers agree. This detects a discrepancy; it does not determine which experimental number is authoritative.", "",
              "PDF, selected body text and original PDF crops remain in ignored `data/attention_is_all_you_need/`.",
              "Full model responses and selected model/reasoning metadata are in the adjacent inference JSON.", ""]
    (RESULTS / "SUMMARY.md").write_text("\n".join(lines))
    print("\n".join(lines))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()
    summarize(args.input)
