"""
provider_router.py

Provider routing:
- Normal: OpenAI -> Gemini
- Forced testing: PROVIDER_FORCE=openai|gemini
- No OpenRouter / Ollama / Qwen
"""

from __future__ import annotations

import os

from ..ai_provider import AIResult
from .openai_provider import generate_with_openai
from .gemini_provider import generate_with_gemini


def generate_with_provider_router(
    prompt: str,
    task: str = "quiz",
    json_mode: bool = True,
    max_tokens: int = 1500,
    temperature: float = 0.1,
) -> AIResult:
    force = os.getenv("PROVIDER_FORCE", "").strip().lower()

    if force == "gemini":
        print("[AI ROUTER] Forced provider: Gemini")
        return generate_with_gemini(
            prompt=prompt,
            task=task,
            json_mode=json_mode,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    if force == "openai":
        print("[AI ROUTER] Forced provider: OpenAI")
        return generate_with_openai(
            prompt=prompt,
            task=task,
            json_mode=json_mode,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    # Normal production order:
    # Gemini first, OpenAI fallback.
    gemini_result = generate_with_gemini(
        prompt=prompt,
        task=task,
        json_mode=json_mode,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    if gemini_result.success:
        return gemini_result

    print(
        f"[AI ROUTER] Gemini failed: {gemini_result.error}. "
        "Trying OpenAI..."
    )

    result = generate_with_openai(
        prompt=prompt,
        task=task,
        json_mode=json_mode,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    if result.success:
        return result

    print(
        f"[AI ROUTER] OpenAI failed: {result.error}"
    )

    return AIResult(
        success=False,
        provider="router",
        model="gemini->openai",
        text="",
        error=(
            f"Gemini: {gemini_result.error}; "
            f"OpenAI: {result.error}"
        ),
    )