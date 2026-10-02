"""Compare model backends and reasoning levels on the same real SciVer mini-slice."""
import argparse
import base64
import hashlib
import importlib.metadata
import json
import os
import platform
import statistics
import subprocess
import time
from pathlib import Path

import requests

from acc_evaluation import parse_verdict
from benchmarks.prepare_slice import ROOT, MANIFEST, TYPES, prepare
from model_inference.ollama_chat import _generate_one
from model_inference.pi_rpc import PiRpcClient, SYSTEM_PROMPT, _query_images
from utils.constant import COT_PROMPT, DEFAULT_MODEL, DEFAULT_PI_THINKING
from utils.input_processing import prepare_qa_text_input

DEFAULT_MODELS = (DEFAULT_MODEL, "ollama/qwen2.5vl:3b", "ollama/qwen2.5vl:7b")
# Keep future default runs separate from the historical medium/high comparisons.
RESULTS = ROOT / "benchmarks/results/default"


def digest(value):
    return hashlib.sha256(value).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


def file_name(model):
    return model.replace("/", "--").replace(":", "-") + ".json"


def scores(records):
    output = {}
    for typ in (*TYPES, "total"):
        subset = records if typ == "total" else [r for r in records if r["claim_type"] == typ]
        correct = sum(r["prediction"] is not None and r["prediction"] == r["label"]
                      and not r.get("error") and r.get("stop_reason") != "length" for r in subset)
        invalid = sum(r["prediction"] is None and not r.get("error") for r in subset)
        errors = sum(bool(r.get("error")) for r in subset)
        output[typ] = {"correct": correct, "n": len(subset),
                       "accuracy": correct / len(subset) if subset else None,
                       "invalid": invalid, "errors": errors}
    durations = [r["wall_seconds"] for r in records]
    output["latency"] = {"median_wall_seconds": statistics.median(durations),
                         "mean_wall_seconds": statistics.mean(durations),
                         "total_wall_seconds": sum(durations)}
    # Show how the old substring-based evaluator would have scored the same outputs.
    output["legacy_correct"] = sum(bool(r.get("response")) and
                                   ("yes" in r["response"].lower()) == r["label"]
                                   for r in records)
    return output


def versions():
    return {"python": platform.python_version(),
            "packages": {name: importlib.metadata.version(name) for name in ("Pillow", "requests", "tqdm")}}


def run_model(model, queries, manifest, resume=False, thinking=DEFAULT_PI_THINKING, results_dir=RESULTS):
    path = results_dir / file_name(model)
    inputs = []
    for q in queries:
        _, prompt = prepare_qa_text_input(model, q, COT_PROMPT)
        images = _query_images(q)
        inputs.append((prompt, images))
    fingerprints = [{"sample_id": q["sample_id"], "prompt_sha256": digest(p.encode()),
                     "image_sha256": [digest(base64.b64decode(b["data"])) for b in imgs]}
                    for q, (p, imgs) in zip(queries, inputs)]
    config = {"model": model, "dataset_revision": manifest["revision"],
              "manifest_sha256": digest(MANIFEST.read_bytes()), "inputs": fingerprints,
              "system_prompt_sha256": digest(SYSTEM_PROMPT.encode()),
              "thinking": thinking if model.startswith("pi/") else None,
              "ollama_options": {"temperature": 0, "seed": 215, "num_ctx": 32768, "num_predict": 2048}
                               if model.startswith("ollama/") else None}
    records = []
    if path.exists():
        previous = json.loads(path.read_text())
        if previous["config"] != config:
            raise ValueError("Existing run has different inputs/settings; use a different --results-dir")
        if resume:
            records = previous["examples"]
            expected_ids = [q["sample_id"] for q in queries[:len(records)]]
            if [r["sample_id"] for r in records] != expected_ids:
                raise ValueError("Cannot resume: saved examples are not an ordered prefix")
            if previous.get("complete") and len(records) == len(queries):
                print(f"{model}: reusing complete matching run", flush=True)
                return previous

    report = {"config": config, "runtime": versions(), "examples": records}
    client = None
    try:
        if model.startswith("pi/"):
            client = PiRpcClient(model=model.removeprefix("pi/"), thinking=thinking)
            state = client.get_state()
            definition = state.get("model", {})
            if "image" not in definition.get("input", []):
                raise ValueError("Selected Pi model does not accept images")
            if f"{definition.get('provider')}/{definition.get('id')}" != model.removeprefix("pi/"):
                raise ValueError("Pi selected a different model than requested")
            if state.get("thinkingLevel") != thinking:
                raise ValueError("Pi did not select the requested reasoning level")
            report["runtime"]["effective_thinking"] = state["thinkingLevel"]
            report["runtime"]["pi_version"] = subprocess.check_output(["pi", "--version"], text=True).strip()
            report["runtime"]["model"] = {k: definition.get(k) for k in ("id", "provider", "api", "input")}
        elif model.startswith("ollama/"):
            base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
            actual = model.removeprefix("ollama/")
            response = requests.get(f"{base}/api/tags", timeout=30)
            response.raise_for_status()
            tags = response.json()["models"]
            tag = next(x for x in tags if x["name"] == actual)
            response = requests.get(f"{base}/api/version", timeout=30)
            response.raise_for_status()
            report["runtime"]["ollama_version"] = response.json()["version"]
            report["runtime"]["model"] = {"id": actual, "digest": tag["digest"], "details": tag["details"]}
        else:
            raise ValueError("This benchmark supports Pi and Ollama only")

        for i in range(len(records), len(queries)):
            q = queries[i]
            prompt, images = inputs[i]
            row = {k: q[k] for k in ("sample_id", "claim_type", "label")}
            row.update({"response": "", "prediction": None, "image_count": len(images), "error": None})
            start = time.perf_counter()
            try:
                if client:
                    if i:
                        client.new_session()
                    state = client.get_state()
                    selected = state.get("model", {})
                    if (state.get("thinkingLevel") != thinking or
                            f"{selected.get('provider')}/{selected.get('id')}" != model.removeprefix("pi/")):
                        raise ValueError("Model/reasoning changed after session reset")
                    row["response"] = client.prompt_and_wait(prompt, images)
                    message = client.last_assistant
                    row["stop_reason"] = message.get("stopReason")
                    row["effective_thinking"] = state["thinkingLevel"]
                    if message.get("responseModel"):
                        row["response_model"] = message["responseModel"]
                    if message.get("providerThinkingLevel"):
                        row["provider_thinking_level"] = message["providerThinkingLevel"]
                    row["usage"] = {k: message.get("usage", {}).get(k)
                                    for k in ("input", "output", "cacheRead", "totalTokens")}
                else:
                    row["response"], raw = _generate_one(model.removeprefix("ollama/"), q, COT_PROMPT)
                    row["stop_reason"] = raw.get("done_reason")
                    row["usage"] = {k: raw.get(k) for k in ("prompt_eval_count", "eval_count")}
                    row["server_seconds"] = {k: raw.get(k, 0) / 1e9 for k in
                                             ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration")}
                row["prediction"] = parse_verdict(row["response"])
            except Exception as exc:
                # Save only a categorical failure; raw diagnostics can contain paths or secrets.
                row["error"] = type(exc).__name__
                print(f"{model}: {q['sample_id']} failed ({row['error']})", flush=True)
                if client:
                    client.close()
                    client = PiRpcClient(model=model.removeprefix("pi/"), thinking=thinking)
            row["wall_seconds"] = round(time.perf_counter() - start, 3)
            records.append(row)
            report["scores"] = scores(records)
            report["complete"] = len(records) == len(queries)
            write_json(path, report)
            verdict = "INVALID" if row["prediction"] is None else ("yes" if row["prediction"] else "no")
            ok = (row["prediction"] == q["label"] and row["prediction"] is not None
                  and not row["error"] and row.get("stop_reason") != "length")
            print(f"{model} {i+1:02d}/{len(queries)} {q['sample_id']} {q['claim_type']}: "
                  f"{verdict}, {'correct' if ok else 'wrong'}, {row['wall_seconds']:.1f}s", flush=True)
    finally:
        if client:
            client.close()
    report["scores"] = scores(records)
    report["complete"] = len(records) == len(queries)
    write_json(path, report)
    return report


def summarize(models, results_dir=RESULTS):
    reports = [json.loads((results_dir / file_name(model)).read_text()) for model in models]
    if any(not r.get("complete") for r in reports):
        raise ValueError("Cannot compare incomplete runs")
    fingerprint = lambda r: (r["config"]["manifest_sha256"], r["config"]["inputs"], r["config"]["system_prompt_sha256"])
    if any(fingerprint(r) != fingerprint(reports[0]) for r in reports[1:]):
        raise ValueError("Runs do not use identical evidence/prompts")
    rows = [{"model": r["config"]["model"], "thinking": r["config"]["thinking"],
             **r["scores"]} for r in reports]
    write_json(results_dir / "comparison.json", rows)
    header = "| Model | Reasoning | Correct | Accuracy | Direct | Parallel | Sequential | Analytical | Median seconds | Invalid/errors |"
    lines = ["# SciVer mini-benchmark results", "", "16 real test examples; 4 per reasoning type; 8 entailed / 8 refuted.", "",
             "**Exploratory only:** not the full SciVer benchmark or an estimate with useful statistical precision.", "",
             header, "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in rows:
        total = row["total"]
        cells = [row["model"], row["thinking"] or "n/a", f"{total['correct']}/{total['n']}", f"{100*total['accuracy']:.1f}%"]
        cells += [f"{row[t]['correct']}/{row[t]['n']}" for t in TYPES]
        cells += [f"{row['latency']['median_wall_seconds']:.1f}", f"{total['invalid']}/{total['errors']}"]
        lines.append("| " + " | ".join(cells) + " |")
    lines += ["", "Final-answer parsing is strict; malformed/empty/failed/truncated answers count as wrong.",
              "Latencies include image encoding/upload, model loading, and provider latency; no warm-only claim."]
    if any(row["model"].startswith("pi/") for row in rows):
        lines.append("Pi uses Copilot, the reasoning levels shown above, isolated conversations, no tools/personal resources.")
    if any(row["model"].startswith("ollama/") for row in rows):
        lines.append("Qwen models use Ollama Q4_K_M quantization, temperature 0, seed 215, context 32768, output cap 2048.")
    lines += ["Local hardware: Apple M3 Ultra, 96 GiB unified memory. Hosted Pi execution is not hardware-comparable.",
              "Prompt and submitted-image hashes are saved; Pi/providers can still apply their own preprocessing.",
              "Published labels are unchanged, including the apparent annotation inconsistency in test-0160.",
              "Dataset: [chengyewang/SciVer](https://huggingface.co/datasets/chengyewang/SciVer), CC BY 4.0; see slice manifest for revision.", ""]
    (results_dir / "SUMMARY.md").write_text("\n".join(lines))
    print("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    parser.add_argument("--resume", action="store_true", help="Reuse a matching saved prefix of examples")
    parser.add_argument("--thinking", choices=("low", "medium", "high", "xhigh", "max"), default=DEFAULT_PI_THINKING)
    parser.add_argument("--results-dir", type=Path, default=RESULTS,
                        help="Use separate directories for reasoning-level comparisons")
    parser.add_argument("--summarize-only", action="store_true")
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.summarize_only:
        summarize(args.models, results_dir=args.results_dir)
        return
    # Explicit settings also make the saved config true when callers set other env defaults.
    os.environ.update({"OLLAMA_TEMPERATURE": "0", "OLLAMA_SEED": "215", "OLLAMA_NUM_CTX": "32768", "OLLAMA_MAX_TOKENS": "2048"})
    path = prepare()
    queries = json.loads(path.read_text())
    manifest = json.loads(MANIFEST.read_text())
    for model in args.models:
        run_model(model, queries, manifest, resume=args.resume, thinking=args.thinking,
                  results_dir=args.results_dir)


if __name__ == "__main__":
    main()
