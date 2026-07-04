"""Hugging Face Inference API client — OpenAI SDK + HF router."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from openai import APIConnectionError, APIStatusError, OpenAI

# Legacy api-inference.huggingface.co no longer resolves (deprecated Jul 2025).
# https://huggingface.co/docs/inference-providers
DEFAULT_MODEL = "meta-llama/Meta-Llama-3-8B-Instruct"
DEFAULT_BASE_URL = "https://router.huggingface.co/v1"


class HuggingFaceError(Exception):
    pass


def get_hf_token() -> str:
    token = (
        os.getenv("HF_TOKEN", "").strip()
        or os.getenv("HUGGINGFACE_API_KEY", "").strip()
        or os.getenv("HUGGING_FACE_HUB_TOKEN", "").strip()
    )
    if not token:
        raise HuggingFaceError(
            "Missing HF token. Set HF_TOKEN (or HUGGINGFACE_API_KEY) in backend/.env"
        )
    return token


def get_base_url() -> str:
    raw = (
        os.getenv("HF_BASE_URL", "").strip()
        or os.getenv("HF_CHAT_URL", "").strip()
        or DEFAULT_BASE_URL
    )
    # Allow legacy full chat URL in env — normalize to base_url
    if raw.rstrip("/").endswith("/chat/completions"):
        raw = raw.rstrip("/")[: -len("/chat/completions")]
    return raw.rstrip("/") or DEFAULT_BASE_URL


def _make_client(*, timeout_s: float) -> OpenAI:
    return OpenAI(
        base_url=get_base_url(),
        api_key=get_hf_token(),
        timeout=timeout_s,
    )


def _strip_fences(text: str) -> str:
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    return fence.group(1).strip() if fence else text.strip()


def extract_json_array(text: str) -> list[dict[str, Any]]:
    """Parse JSON array from model output."""
    text = _strip_fences(text)
    if not text:
        raise HuggingFaceError("Empty model response")

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [x for x in parsed if isinstance(x, dict)]
    except json.JSONDecodeError:
        pass

    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, list):
                return [x for x in parsed if isinstance(x, dict)]
        except json.JSONDecodeError as exc:
            raise HuggingFaceError(f"Could not parse JSON array: {exc}") from exc

    raise HuggingFaceError(f"Could not parse JSON array from: {text[:300]}...")


def call_hf_normalizer(
    *,
    system: str,
    user: str,
    model_id: str = DEFAULT_MODEL,
    max_new_tokens: int = 2048,
    temperature: float = 0.1,
    timeout_s: float = 180.0,
) -> dict[str, Any]:
    """
    Call HF router via OpenAI-compatible chat completions.

    Docs: https://huggingface.co/docs/inference-providers
    """
    base_url = get_base_url()
    client = _make_client(timeout_s=timeout_s)

    try:
        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_new_tokens,
            temperature=temperature,
        )
    except APIConnectionError as exc:
        raise HuggingFaceError(
            f"Cannot reach Hugging Face API at {base_url}. "
            f"Check network/DNS. (Underlying: {exc})"
        ) from exc
    except APIStatusError as exc:
        if exc.status_code == 503:
            raise HuggingFaceError(
                f"Model {model_id} unavailable (503). Retry or try --model with :fastest suffix."
            ) from exc
        raise HuggingFaceError(f"HF API {exc.status_code}: {exc.message}") from exc

    generated = response.choices[0].message.content or ""
    raw_response = response.model_dump()

    result: dict[str, Any] = {
        "model_id": model_id,
        "base_url": base_url,
        "generated_text": generated,
        "raw_response": raw_response,
    }

    try:
        result["parsed_array"] = extract_json_array(generated)
    except HuggingFaceError as exc:
        result["parse_error"] = str(exc)
        result["parsed_array"] = None

    return result
