"""
OpenRouter provider for the educational AI engine.

Goals:
- Safe HTTP handling
- Correct JSON-mode prompting
- Multiple model fallback
- Proper 429 handling
- No indentation/flow problems
- No response_format requirement for free models
- Clear errors for callers
"""

from __future__ import annotations
import os
import json
import time
from typing import Optional

from ..ai_provider import AIResult

import requests




OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

CONNECT_TIMEOUT = 10
READ_TIMEOUT = 120

MAX_RETRIES_PER_MODEL = 1
RETRY_DELAY = 2


# ------------------------------------------------------------
# MODEL CONFIGURATION
# ------------------------------------------------------------

DEFAULT_MODELS = [
    "google/gemma-4-26b-a4b-it:free",
    "openai/gpt-oss-20b:free",
    "openrouter/free",
]


# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------

def _safe_http_error(status: int) -> str:
    if status == 400:
        return "Provider rejected the request."
    if status == 401:
        return "OpenRouter API key is invalid or missing."
    if status == 403:
        return "OpenRouter access was denied."
    if status == 404:
        return "Requested AI model was not found."
    if status == 408:
        return "Provider request timed out."
    if status == 429:
        return "Provider rate limited."
    if status == 500:
        return "OpenRouter server error."
    if status == 502:
        return "OpenRouter gateway error."
    if status == 503:
        return "AI service is temporarily unavailable."
    if status == 504:
        return "OpenRouter gateway timed out."

    return f"OpenRouter HTTP error: {status}"


def _parse_response(
    response: requests.Response,
    model: str,
) -> AIResult:

    try:
        data = response.json()
    except ValueError:
        return AIResult(
            success=False,
            provider="openrouter",
            model=model,
            error="Provider returned invalid JSON.",
        )

    try:
        choices = data.get("choices")

        if not choices:
            return AIResult(
                success=False,
                provider="openrouter",
                model=model,
                error="Provider returned no choices.",
            )

        message = choices[0].get("message", {})

        text = message.get("content", "")

        if text is None:
            text = ""

        if not isinstance(text, str):
            text = str(text)

        text = text.strip()

        if not text:
            return AIResult(
                success=False,
                provider="openrouter",
                model=model,
                error="Provider returned empty response.",
            )

        return AIResult(
            success=True,
            provider="openrouter",
            model=model,
            error=None,
            text=text,
        )

    except Exception:
        return AIResult(
            success=False,
            provider="openrouter",
            model=model,
            error="Unable to parse provider response.",
        )


def _parse_json_safely(
    text: str,
) -> Optional[dict]:

    if not text:
        return None

    cleaned = text.strip()

    # Remove accidental markdown fences.
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        cleaned = "\n".join(lines).strip()

    try:
        value = json.loads(cleaned)

        if isinstance(value, dict):
            return value

        return None

    except Exception:
        return None


# ------------------------------------------------------------
# SINGLE MODEL REQUEST
# ------------------------------------------------------------

def _request_model(
    *,
    api_key: str,
    model: str,
    prompt: str,
    json_mode: bool,
    max_tokens: int,
    temperature: float,
) -> AIResult:

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    system_prompt = (
        "You are an educational AI assistant. "
        "The supplied lesson may be in English, Telugu, Hindi, "
        "Tamil, Kannada, Malayalam, or mixed language. "
        "Understand the meaning of the lesson. "

        "ALL GENERATED QUIZ CONTENT MUST BE IN ENGLISH. "

        "Questions, answers, MCQ options, explanations, "
        "and all generated educational text MUST use English. "

        "NEVER generate Hindi, Telugu, Tamil, Kannada, "
        "Malayalam, Bengali, Gujarati, Arabic, or any other "
        "non-English script in generated quiz content. "

        "ONLY source evidence or quoted source excerpts may "
        "remain in the original language. "

        "If the source lesson is Hindi, translate its educational "
        "meaning into clear English instead of copying Hindi text. "

        "Follow the user's requested output format exactly."
    )

    if json_mode:
        system_prompt += (
            " Return ONLY one valid JSON object. "
            "Do not use markdown. "
            "Do not use code fences. "
            "Do not add explanations outside JSON."
        )

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    last_error = "Provider request failed."

    for attempt in range(MAX_RETRIES_PER_MODEL + 1):

        try:

            response = requests.post(
                OPENROUTER_URL,
                headers=headers,
                json=payload,
                timeout=(
                    CONNECT_TIMEOUT,
                    READ_TIMEOUT,
                ),
            )

            status = response.status_code

            print(
                f"[OPENROUTER DEBUG] "
                f"model={model} "
                f"status={status}"
            )

            # ------------------------------------------------
            # SUCCESS
            # ------------------------------------------------

            if status == 200:

                result = _parse_response(
                    response,
                    model,
                )

                if result.success:
                    return result

                return result

            # ------------------------------------------------
            # RATE LIMIT
            # ------------------------------------------------

            if status == 429:

                print(
                    f"[OPENROUTER] 429 rate limit | "
                    f"model={model} | "
                    f"skipping model"
                )

                return AIResult(
                    success=False,
                    provider="openrouter",
                    model=model,
                    error="Provider rate limited.",
                )
            # ------------------------------------------------
            # OTHER HTTP ERRORS
            # ------------------------------------------------

            last_error = _safe_http_error(
                status
            )

            retryable = status in {
                408,
                409,
                425,
                500,
                502,
                503,
                504,
            }

            if (
                retryable
                and attempt < MAX_RETRIES_PER_MODEL
            ):

                time.sleep(
                    RETRY_DELAY
                )

                continue

            return AIResult(
                success=False,
                provider="openrouter",
                model=model,
                error=last_error,
            )

        except requests.Timeout:

            last_error = "Provider timed out."

            if attempt < MAX_RETRIES_PER_MODEL:

                time.sleep(
                    RETRY_DELAY
                )

                continue

            return AIResult(
                success=False,
                provider="openrouter",
                model=model,
                error=last_error,
            )

        except requests.ConnectionError:

            last_error = (
                "Provider connection failed."
            )

            if attempt < MAX_RETRIES_PER_MODEL:

                time.sleep(
                    RETRY_DELAY
                )

                continue

            return AIResult(
                success=False,
                provider="openrouter",
                model=model,
                error=last_error,
            )

        except requests.RequestException:

            return AIResult(
                success=False,
                provider="openrouter",
                model=model,
                error=(
                    "Provider request failed."
                ),
            )

        except Exception:

            return AIResult(
                success=False,
                provider="openrouter",
                model=model,
                error="AI provider failure.",
            )

    return AIResult(
        success=False,
        provider="openrouter",
        model=model,
        error=last_error,
    )


# ------------------------------------------------------------
# PUBLIC OPENROUTER FUNCTION
# ------------------------------------------------------------

def generate_with_openrouter(
    *,
    prompt: str,
    task: str,
    json_mode: bool = False,
    max_tokens: int = 500,
    temperature: float = 0.2,
) -> AIResult:

    # -----------------------------------------------
    # API KEY
    # -----------------------------------------------

    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        return AIResult(
            success=False,
            provider="openrouter",
            model="",
            error="OPENROUTER_API_KEY environment variable is missing.",
            text="",
        )

    
    if not api_key:

        return AIResult(
            success=False,
            provider="openrouter",
            model="",
            error=(
                "OpenRouter API key is missing."
            ),
        )

    # -----------------------------------------------
    # MODEL SELECTION
    # -----------------------------------------------

    if task in {
        "mcq_batch",
        "mcq_region_repair",
    }:

        models = [
            "google/gemma-4-26b-a4b-it:free",
            "openai/gpt-oss-20b:free",
            "nvidia/nemotron-3-nano-30b-a3b:free",
            "nvidia/nemotron-3-ultra-550b-a55b:free",
            "openrouter/free",
        ]

    else:

        models = DEFAULT_MODELS.copy()

    # -----------------------------------------------
    # TRY MODELS
    # -----------------------------------------------

    failures = []

    for model in models:

        result = _request_model(
            api_key=api_key,
            model=model,
            prompt=prompt,
            json_mode=json_mode,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        if result.success:

            if json_mode:

                parsed = _parse_json_safely(
                    result.text
                )

                if parsed is None:

                    print(
                        "[MODEL INVALID JSON] "
                        f"{model}"
                    )

                    return AIResult(
                        success=False,
                        provider="openrouter",
                        model=model,
                        error=(
                            "OpenRouter returned "
                            "invalid JSON."
                        ),
                        text="",
                    )

            return result

        print(
            f"[MODEL FAILED] "
            f"{model}: "
            f"{result.error}"
        )

        failures.append(
            (
                model,
                result.error,
            )
        )

        # ------------------------------------------------
        # IMPORTANT:
        # Stop immediately on provider-level failure.
        #
        # We do NOT continue through every configured
        # OpenRouter model during an outage.
        # ai_provider.py will then activate the global
        # outage fallback and the quiz can go offline.
        # ------------------------------------------------

        break

    # -----------------------------------------------
    # ALL MODELS FAILED
    # -----------------------------------------------

    return AIResult(
        success=False,
        provider="openrouter",
        model="",
        error=(
            failures[-1][1]
            if failures
            else
            "OpenRouter provider failed."
        ),
        text="",
    )