import json
import os
from typing import Any

import requests

from model_inference.pi_rpc import SYSTEM_PROMPT
from utils.input_processing import prepare_qa_text_input, prepare_single_image_input


def _resolve_model_name(model_name: str) -> str:
    return model_name.split("/", 1)[1] if model_name.startswith("ollama/") else model_name


def _build_images(query: dict[str, Any]) -> list[str]:
    # `prepare_single_image_input` returns raw base64 for model names containing '/'.
    helper_model_name = "ollama/local"
    if query["claim_type"] in {"direct", "analytical"}:
        return [prepare_single_image_input(helper_model_name, query["image_path"])]
    return [
        prepare_single_image_input(helper_model_name, query["item1_path"]),
        prepare_single_image_input(helper_model_name, query["item2_path"]),
    ]


def _generate_one(model: str, query: dict[str, Any], prompt: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    _, qa_text_prompt = prepare_qa_text_input(model, query, prompt)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": qa_text_prompt,
                "images": _build_images(query),
            }
        ],
        "stream": False,
        "options": {
            "temperature": float(os.getenv("OLLAMA_TEMPERATURE", "0")),
            "seed": int(os.getenv("OLLAMA_SEED", "215")),
            "num_ctx": int(os.getenv("OLLAMA_NUM_CTX", "32768")),
            "num_predict": int(os.getenv("OLLAMA_MAX_TOKENS", "2048")),
        },
    }

    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    response = requests.post(f"{base_url.rstrip('/')}/api/chat", json=payload, timeout=1800)
    if not response.ok:
        raise RuntimeError(
            f"Ollama request failed ({response.status_code}) for model {model}: {response.text}"
        )
    data = response.json()
    message = ((data.get("message") or {}).get("content") or "").strip()
    if not message or not data.get("done"):
        raise RuntimeError("Ollama returned an empty/incomplete answer")
    return message, data


def generate_response(
    model_name: str,
    prompt: str,
    queries: list,
    output_path: str,
    n: int = 1,
):
    if n != 1:
        raise ValueError("Ollama backend supports n=1 only")

    actual_model = _resolve_model_name(model_name)
    for query in queries:
        response_text, raw = _generate_one(actual_model, query, prompt)
        query["response"] = response_text
        query["ollama_raw"] = raw

    json.dump(queries, open(output_path, "w", encoding="utf-8"), indent=4, ensure_ascii=False)
