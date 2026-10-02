import json
import os
import subprocess
import sys
import tempfile
from typing import Any

from utils.input_processing import prepare_caption, prepare_context


DEFAULT_QUESTION = {
    "type": "choice",
    "instructions": (
        "Decide whether the claim is supported by the provided text evidence only. "
        "Answer no when the evidence is contradicted, insufficient, or ambiguous."
    ),
    "criteria": {
        "yes": "The claim is supported by the provided text evidence.",
        "no": "The claim is contradicted, unsupported, insufficiently supported, or ambiguous.",
    },
}


def _resolve_python() -> str:
    candidates = [os.getenv("LAYA_PYTHON"), sys.executable]
    for candidate in candidates:
        if not candidate:
            continue
        if os.path.sep in candidate:
            if os.path.exists(candidate):
                return candidate
        else:
            return candidate
    raise RuntimeError(
        "Could not resolve a Python executable for Laya. Set LAYA_PYTHON to a Python with `laya` installed."
    )


def _resolve_model_name(model_name: str) -> str:
    if model_name == "laya":
        return os.getenv("LAYA_MODEL", "typed-decisions")
    if model_name.startswith("laya/"):
        return model_name.split("/", 1)[1]
    return model_name


def _build_state(query: dict[str, Any]) -> str:
    context = prepare_context(query["paper_path"], query["section"])
    if query["claim_type"] in {"direct", "analytical"}:
        caption = prepare_caption(query["paper_path"], query["type"], query["item"])
        evidence = f"Caption: {caption}"
    else:
        caption1 = prepare_caption(query["paper_path"], query["item1_type"], query["item1"])
        caption2 = prepare_caption(query["paper_path"], query["item2_type"], query["item2"])
        evidence = f"Item 1 caption: {caption1}\nItem 2 caption: {caption2}"

    return (
        "Scientific claim verification from text-only evidence.\n\n"
        f"Claim type: {query['claim_type']}\n"
        f"Claim: {query['claim']}\n\n"
        f"Context:\n{context}\n\n"
        f"Evidence:\n{evidence}\n"
    )


def _run_laya(states: list[str], model: str) -> list[dict[str, Any]]:
    python_exe = _resolve_python()
    device = os.getenv("LAYA_DEVICE")
    max_len = os.getenv("LAYA_MAX_LEN")

    payload = {
        "states": states,
        "question": DEFAULT_QUESTION,
        "model": model,
        "device": device,
        "max_len": int(max_len) if max_len else None,
    }

    helper = r'''
import json
import sys
from laya import Router

with open(sys.argv[1], 'r', encoding='utf-8') as f:
    payload = json.load(f)

router_kwargs = {}
if payload.get('device'):
    router_kwargs['device'] = payload['device']
router = Router(**router_kwargs)

results = []
for state in payload['states']:
    result = router.predict(
        state,
        {'answer': payload['question']},
        model=payload.get('model'),
        max_len=payload.get('max_len'),
    )
    results.append(result)

json.dump(results, sys.stdout, ensure_ascii=False)
'''

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
        tmp_path = f.name

    try:
        completed = subprocess.run(
            [python_exe, "-c", helper, tmp_path],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"Laya invocation failed with {python_exe}:\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}"
        ) from e
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return json.loads(completed.stdout)


def _format_response(result: dict[str, Any]) -> str:
    answer = ((result.get("answers") or {}).get("answer") or {})
    choice = answer.get("choice", "no")
    confidence = answer.get("confidence")
    if isinstance(confidence, (int, float)):
        prefix = f"Laya text-only baseline confidence: {confidence:.4f}."
    else:
        prefix = "Laya text-only baseline."
    final = "yes" if choice == "yes" else "no"
    return f"{prefix}\nTherefore, the final answer is: Answer: {final}"


def generate_response(
    model_name: str,
    prompt: str,
    queries: list,
    output_path: str,
    n: int = 1,
):
    if n != 1:
        raise ValueError("Laya text baseline supports n=1 only")

    resolved_model = _resolve_model_name(model_name)
    states = [_build_state(query) for query in queries]
    results = _run_laya(states, resolved_model)

    for query, result in zip(queries, results):
        query["response"] = _format_response(result)
        query["laya_raw"] = result

    json.dump(queries, open(output_path, "w", encoding="utf-8"), indent=4, ensure_ascii=False)
