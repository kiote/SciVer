import base64
import json
import mimetypes
import os
import subprocess
import urllib.request
from typing import List, Optional

from utils.input_processing import prepare_qa_text_input


class PiRpcError(RuntimeError):
    pass


class PiRpcClient:
    def __init__(self, model: Optional[str] = None, thinking: Optional[str] = None):
        cmd = ["pi", "--mode", "rpc", "--no-session", "--no-tools"]
        if model:
            cmd.extend(["--model", model])
        if thinking:
            cmd.extend(["--thinking", thinking])
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        if self.proc.stdin is None or self.proc.stdout is None:
            raise PiRpcError("Failed to start pi RPC process")
        self._next_id = 1

    def close(self):
        if self.proc.stdin and not self.proc.stdin.closed:
            self.proc.stdin.close()
        try:
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()

    def _id(self, prefix: str) -> str:
        value = f"{prefix}-{self._next_id}"
        self._next_id += 1
        return value

    def _send(self, payload: dict):
        if self.proc.stdin is None or self.proc.stdin.closed:
            raise PiRpcError("pi RPC stdin is closed")
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()

    def _read_record(self) -> dict:
        if self.proc.stdout is None:
            raise PiRpcError("pi RPC stdout is unavailable")
        line = self.proc.stdout.readline()
        if not line:
            stderr = ""
            if self.proc.stderr is not None:
                try:
                    stderr = self.proc.stderr.read()
                except Exception:
                    stderr = ""
            raise PiRpcError(f"pi RPC exited unexpectedly. stderr:\n{stderr}")
        return json.loads(line)

    def _wait_for_response(self, request_id: str) -> dict:
        while True:
            record = self._read_record()
            if record.get("type") == "response" and record.get("id") == request_id:
                if not record.get("success"):
                    raise PiRpcError(record.get("error", "Unknown pi RPC error"))
                return record

    def new_session(self):
        request_id = self._id("new-session")
        self._send({"id": request_id, "type": "new_session"})
        self._wait_for_response(request_id)

    def prompt_and_wait(self, message: str, images: Optional[List[dict]] = None) -> str:
        request_id = self._id("prompt")
        payload = {"id": request_id, "type": "prompt", "message": message}
        if images:
            payload["images"] = images
        self._send(payload)

        response = self._wait_for_response(request_id)
        disposition = response.get("data", {}).get("disposition")
        if disposition == "handled":
            return self.get_last_assistant_text()

        while True:
            record = self._read_record()
            if record.get("type") == "agent_settled":
                break

        return self.get_last_assistant_text()

    def get_last_assistant_text(self) -> str:
        request_id = self._id("last-text")
        self._send({"id": request_id, "type": "get_last_assistant_text"})
        response = self._wait_for_response(request_id)
        data = response.get("data")
        return data if isinstance(data, str) else data.get("text", "")


def _resolve_pi_model(model_name: str) -> tuple[Optional[str], Optional[str]]:
    if model_name == "pi/current":
        provider = os.getenv("PI_PROVIDER")
        model = os.getenv("PI_MODEL")
        if not provider or not model:
            raise PiRpcError("PI_PROVIDER/PI_MODEL are not set; cannot resolve pi/current")
        thinking = os.getenv("PI_REASONING_LEVEL")
        return f"{provider}/{model}", thinking

    if model_name.startswith("pi/"):
        return model_name[len("pi/"):], None

    return None, None


def _image_block_from_source(image_source: str) -> dict:
    if image_source.startswith("http://") or image_source.startswith("https://"):
        with urllib.request.urlopen(image_source) as response:
            data = response.read()
            mime_type = response.headers.get_content_type() or "image/jpeg"
    else:
        with open(image_source, "rb") as f:
            data = f.read()
        mime_type = mimetypes.guess_type(image_source)[0] or "image/jpeg"

    return {
        "type": "image",
        "data": base64.b64encode(data).decode("utf-8"),
        "mimeType": mime_type,
    }


def _query_images(query: dict) -> List[dict]:
    if query["claim_type"] in {"direct", "analytical"}:
        return [_image_block_from_source(query["image_path"])]
    return [
        _image_block_from_source(query["item1_path"]),
        _image_block_from_source(query["item2_path"]),
    ]


def generate_response(
    model_name: str,
    prompt: str,
    queries: list,
    output_path: str,
    n: int = 1,
):
    if n != 1:
        raise ValueError("pi RPC backend currently supports n=1 only")

    resolved_model, thinking = _resolve_pi_model(model_name)
    client = PiRpcClient(model=resolved_model, thinking=thinking)
    try:
        for idx, query in enumerate(queries):
            if idx:
                client.new_session()
            _, qa_text_prompt = prepare_qa_text_input(resolved_model or model_name, query, prompt)
            images = _query_images(query)
            query["response"] = client.prompt_and_wait(qa_text_prompt, images=images)
    finally:
        client.close()

    json.dump(queries, open(output_path, "w", encoding="utf-8"), indent=4, ensure_ascii=False)
