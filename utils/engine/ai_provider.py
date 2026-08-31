"""
ai_provider.py
--------------

Central AI provider layer for the quiz engine.

The rest of the project should NOT directly call
Gemini, Groq, Ollama, or any other AI provider.

All AI requests should eventually pass through this file.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any

import time



# ==========================================================
# RESULT
# ==========================================================

@dataclass
class AIResult:
    success: bool
    text: str = ""
    provider: str = ""
    model: str = ""
    error: str | None = None


# ==========================================================
# PROVIDER ERRORS
# ==========================================================

class AIProviderError(Exception):
    """Raised when an AI provider fails."""


# ==========================================================
# PROVIDER REGISTRY
# ==========================================================

_PROVIDERS: dict[str, Callable[..., AIResult]] = {}

_PROVIDER_COOLDOWN_UNTIL: dict[str, float] = {}

PROVIDER_COOLDOWN_SECONDS = 300





def register_provider(
    name: str,
    handler: Callable[..., AIResult],
) -> None:
    """
    Register an AI provider.

    Example:
        register_provider("gemini", generate_with_gemini)
    """

    _PROVIDERS[name] = handler
    



# ==========================================================
# PROVIDER ORDER
# ==========================================================

# We will connect these later.
#
# Changing providers in the future should require changing
# configuration, NOT rewriting the quiz engine.

PROVIDER_ORDER = [
    "openai",
]


def _load_providers() -> None:
    """Load provider handlers lazily to avoid circular imports."""

    from .providers.gemini_provider import generate_with_gemini
    from .providers.openrouter_provider import (
        generate_with_openrouter,
    )
    
    from .providers.openai_provider import (
        generate_with_openai,
    )
    register_provider(
        "gemini",
        generate_with_gemini,
    )

    register_provider(
        "openrouter",
        generate_with_openrouter,
    )
    
    register_provider(
        "openai",
        generate_with_openai,
    )
    
    

def _is_provider_on_cooldown(
    provider_name: str,
) -> bool:

    cooldown_until = (
        _PROVIDER_COOLDOWN_UNTIL.get(
            provider_name,
            0.0,
        )
    )

    return time.time() < cooldown_until


def _set_provider_cooldown(
    provider_name: str,
    seconds: float = PROVIDER_COOLDOWN_SECONDS,
) -> None:

    _PROVIDER_COOLDOWN_UNTIL[
        provider_name
    ] = time.time() + seconds

    

# ==========================================================
# GENERATE
# ==========================================================

def generate_ai(
    prompt: str,
    *,
    task: str = "general",
    json_mode: bool = False,
    **kwargs: Any,
) -> AIResult:
    """
    Generate AI output using available providers.

    Providers are attempted in PROVIDER_ORDER.

    If one provider fails, the next provider is tried
    automatically.
    """


    _load_providers()
    
    
    
    if not prompt or not prompt.strip():

        return AIResult(
            success=False,
            error="Empty prompt.",
        )

    errors = []

    for provider_name in PROVIDER_ORDER:

        if _is_provider_on_cooldown(
            provider_name
        ):
            print(
                f"[AI] Skipping {provider_name} "
                f"(cooldown)"
            )
            continue

        handler = _PROVIDERS.get(
            provider_name
        )

        if handler is None:
            continue

        try:

            result = handler(
                prompt=prompt,
                task=task,
                json_mode=json_mode,
                **kwargs,
            )

            if result.success:
                return result

            error_text = (
                result.error
                or "unknown error"
            )

            errors.append(
                f"{provider_name}: "
                f"{error_text}"
            )

            if (
                "rate limit" in error_text.lower()
                or "429" in error_text
            ):
                _set_provider_cooldown(
                    provider_name
                )

                print(
                    f"[AI] {provider_name} "
                    f"placed on cooldown for "
                    f"{PROVIDER_COOLDOWN_SECONDS}s"
                )

        except Exception as exc:

            errors.append(
                f"{provider_name}: {exc}"
            )

    # No provider succeeded.
    if not errors:

        error_message = (
            "No AI providers are configured."
        )

    else:

        error_message = " | ".join(
            errors
        )

    return AIResult(
        success=False,
        error=error_message,
    )


# ==========================================================
# STATUS
# ==========================================================

def get_provider_status() -> dict:
    """
    Return configured provider information.
    """
    
    _load_providers()

    configured = [
        name
        for name in PROVIDER_ORDER
        if name in _PROVIDERS
    ]

    return {
        "provider_order": PROVIDER_ORDER.copy(),
        "configured": configured,
        "count": len(configured),
    }