"""
groq_provider.py
----------------

Groq provider for the AI Quiz Engine.
"""

from __future__ import annotations

import json
import os

from groq import Groq

from ..ai_provider import AIResult


DEFAULT_MODEL = "openai/gpt-oss-20b"


def _clean_json_text(text: str) -> str:
    """
    Remove accidental markdown code fences.
    """

    cleaned = str(text).strip()

    if cleaned.startswith("```"):
        lines = cleaned.splitlines()

        if lines:
            lines = lines[1:]

        if (
            lines
            and lines[-1].strip() == "```"
        ):
            lines = lines[:-1]

        cleaned = "\n".join(lines).strip()

    return cleaned


def generate_with_groq(
    prompt: str,
    task: str = "general",
    json_mode: bool = False,
    **kwargs,
) -> AIResult:

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        return AIResult(
            success=False,
            provider="groq",
            model=DEFAULT_MODEL,
            error="GROQ_API_KEY not found.",
        )

    try:

        client = Groq(
            api_key=api_key
        )

        system_content = (
            "You are an educational AI assistant. "
            "Follow the user's instructions exactly. "
            "The lesson may be multilingual or use "
            "mixed-language speech. "
            "Focus only on educational concepts "
            "actually taught."
        )

        if json_mode:
            system_content += (
                " Your response MUST be valid JSON. "
                "Return ONLY one JSON object. "
                "Do not use markdown. "
                "Do not use code fences. "
                "Do not write any text before or after "
                "the JSON object."
            )

        request = {
            "model": DEFAULT_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": system_content,
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "temperature": kwargs.get(
                "temperature",
                0.1,
            ),
            "max_completion_tokens": kwargs.get(
                "max_tokens",
                800,
            ),
            "reasoning_effort": "low",
            "include_reasoning": False,
        }

        # IMPORTANT:
        # Do NOT send Groq's response_format=json_object.
        # We validate JSON locally instead.
        response = client.chat.completions.create(
            **request
        )
        
        
        text = (
            response.choices[0].message.content
            or ""
        ).strip()

        if not text:
            return AIResult(
                success=False,
                provider="groq",
                model=DEFAULT_MODEL,
                error="Groq returned empty output.",
            )

        if json_mode:

            cleaned = _clean_json_text(
                text
            )

            try:
                parsed = json.loads(
                    cleaned
                )

            except json.JSONDecodeError:

                print()
                print("=" * 60)
                print("[GROQ RAW RESPONSE]")
                print(repr(text))
                print("=" * 60)

                return AIResult(
                    success=False,
                    provider="groq",
                    model=DEFAULT_MODEL,
                    error="Groq returned invalid JSON.",
                )

            if not isinstance(
                parsed,
                dict,
            ):
                return AIResult(
                    success=False,
                    provider="groq",
                    model=DEFAULT_MODEL,
                    error="Groq JSON response was not an object.",
                )

            text = cleaned

        return AIResult(
            success=True,
            text=text,
            provider="groq",
            model=DEFAULT_MODEL,
            error=None,
        )

    except Exception as exc:

        return AIResult(
            success=False,
            provider="groq",
            model=DEFAULT_MODEL,
            error=str(exc),
        )