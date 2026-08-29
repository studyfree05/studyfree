"""
ollama_client.py
----------------

Shared Ollama client.
"""

from __future__ import annotations

import requests

from .config import (
    OLLAMA_URL,
    TIMEOUT,
)


def generate(
    model: str,
    prompt: str,
    temperature: float = 0.1,
    top_p: float = 0.8,
    num_predict: int = 300,
    num_ctx: int = 2048,
    num_thread: int = 4,
    json_mode: bool = False,
    json_schema: dict | None = None,
    keep_alive: str = "10m",
):
    """
    Generate a response using Ollama.

    json_mode=True forces Ollama to return JSON.
    """

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "top_p": top_p,
            "num_predict": num_predict,
            "num_ctx": num_ctx,
            "num_thread": num_thread,
        },
    }

    # Force JSON output when requested
    if json_schema is not None:
        payload["format"] = json_schema
    elif json_mode:
        payload["format"] = "json"

    r = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json=payload,
        timeout=TIMEOUT,
    )

    r.raise_for_status()

    data = r.json()

    return data.get("response", "").strip()