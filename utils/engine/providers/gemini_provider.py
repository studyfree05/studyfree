"""
gemini_provider.py
Stable Gemini provider for StudyFree.

Uses Google GenAI structured JSON output without tools/function calling.
"""

from __future__ import annotations

import os
import time
from typing import Any
import logging

logging.getLogger("google_genai.models").setLevel(logging.ERROR)

try:
    from google import genai
    from google.genai import types
except ImportError as exc:  # pragma: no cover
    genai = None
    types = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

from ..ai_provider import AIResult


# Stable models first. Do not use experimental model names from the
# environment when the quiz pipeline needs predictable JSON output.
GEMINI_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
]

MAX_ATTEMPTS_PER_MODEL = 2
RETRY_DELAY_SECONDS = 0.8


def _schema(task: str) -> dict[str, Any]:
    if task in {"mcq_batch", "short_batch", "long_batch"}:
        min_items = 5
        max_items = 5
    else:
        min_items = 1
        max_items = 5

    return {
        "type": "OBJECT",
        "properties": {
            "questions": {
                "type": "ARRAY",
                "minItems": min_items,
                "maxItems": max_items,
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "region": {"type": "INTEGER"},
                        "type": {"type": "STRING"},
                        "question": {"type": "STRING"},
                        "options": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"},
                        },
                        "answer": {"type": "STRING"},
                        "evidence": {"type": "STRING"},
                    },
                    "required": [
                        "region",
                        "question",
                        "answer",
                        "evidence",
                    ],
                },
            }
        },
        "required": ["questions"],
    }


def generate_with_gemini(
    prompt: str,
    task: str = "quiz",
    json_mode: bool = True,
    max_tokens: int = 1500,
    temperature: float = 0.1,
) -> AIResult:
    """Generate structured quiz JSON with stable Gemini models."""

    if genai is None:
        return AIResult(
            success=False,
            provider="gemini",
            model="unavailable",
            error=f"google-genai is not installed: {_IMPORT_ERROR}",
        )

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return AIResult(
            success=False,
            provider="gemini",
            model="gemini",
            error="GEMINI_API_KEY is not configured.",
        )

    try:
        client = genai.Client(api_key=api_key)
    except Exception as exc:
        print(
            f"[GEMINI] client initialization failed: "
            f"{type(exc).__name__}: {exc}"
        )
        return AIResult(
            success=False,
            provider="gemini",
            model="gemini",
            error="Gemini client initialization failed.",
        )

    last_error = "Gemini request failed for all configured models."

    for model_name in GEMINI_MODELS:

        for attempt in range(1, MAX_ATTEMPTS_PER_MODEL + 1):

            try:
                # Gemini 3.x:
                # Do not send temperature/top_p/top_k.
                config_kwargs: dict[str, Any] = {
                    "max_output_tokens": max_tokens,
                }

                if json_mode:
                    config_kwargs["response_mime_type"] = "application/json"
                    config_kwargs["response_schema"] = _schema(task)

                # IMPORTANT:
                # No tools.
                # No function declarations.
                # No automatic function calling.
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        **config_kwargs
                    ),
                )

                text = str(
                    getattr(response, "text", "") or ""
                ).strip()
                print("[GEMINI RAW RESPONSE]", text)

                if text:
                    print(
                        f"[GEMINI] task={task} "
                        f"model={model_name} "
                        f"attempt={attempt} "
                        f"chars={len(text)}"
                    )

                    return AIResult(
                        success=True,
                        provider="gemini",
                        model=model_name,
                        text=text,
                        error=None,
                    )

                last_error = "Gemini returned an empty response."

                print(
                    f"[GEMINI] empty response | "
                    f"task={task} "
                    f"model={model_name} "
                    f"attempt={attempt}"
                )

            except Exception as exc:

                error_text = str(exc)

                last_error = (
                    f"Gemini request failed: "
                    f"{type(exc).__name__}"
                )

                print(
                    f"[GEMINI] request error | "
                    f"task={task} "
                    f"model={model_name} "
                    f"attempt={attempt} "
                    f"error={type(exc).__name__}: {exc}"
                )

                # -------------------------------------------------
                # 429 QUOTA / RATE LIMIT
                #
                # NEVER retry the same model when Gemini says
                # RESOURCE_EXHAUSTED / 429.
                #
                # Immediately move to the next model.
                # -------------------------------------------------
                if (
                    "429" in error_text
                    or "RESOURCE_EXHAUSTED" in error_text
                    or "quota" in error_text.lower()
                ):
                    print(
                        f"[GEMINI] quota/rate limit detected | "
                        f"model={model_name} | "
                        f"switching immediately"
                    )

                    break

                # -------------------------------------------------
                # Other temporary errors:
                # retry once using the existing small delay.
                # -------------------------------------------------
                if attempt < MAX_ATTEMPTS_PER_MODEL:
                    time.sleep(RETRY_DELAY_SECONDS)

        print(
            f"[GEMINI] switching model after failure: "
            f"{model_name}"
        )

    return AIResult(
        success=False,
        provider="gemini",
        model="gemini-fallback-chain",
        error=last_error,
    )