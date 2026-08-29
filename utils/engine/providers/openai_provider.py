"""
openai_provider.py

Primary OpenAI provider for the quiz engine.
"""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from ..ai_provider import AIResult


load_dotenv()

DEFAULT_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-5.6-luna",
)


def generate_with_openai(
    *,
    prompt: str,
    task: str = "general",
    json_mode: bool = False,
    max_tokens: int = 1400,
    temperature: float = 0.1,
    **kwargs,
) -> AIResult:

    api_key = os.getenv(
        "OPENAI_API_KEY"
    )

    if not api_key:

        return AIResult(
            success=False,
            provider="openai",
            model=DEFAULT_MODEL,
            error="OPENAI_API_KEY not found.",
        )

    if not prompt or not prompt.strip():

        return AIResult(
            success=False,
            provider="openai",
            model=DEFAULT_MODEL,
            error="Empty prompt.",
        )

    try:

        client = OpenAI(
            api_key=api_key
        )

        instructions = (
            "You are the primary educational AI "
            "engine for a quiz application. "
            "The lesson source may be Kannada, "
            "Telugu, Hindi, Tamil, Malayalam, "
            "Bengali, Gujarati, English, or mixed. "
            "Understand the source meaning before "
            "writing the answer. "
            "All student-facing question, answer, "
            "option, explanation, and feedback content "
            "must be in clear English. "
            "Use ONLY information supported by the "
            "supplied lesson evidence. "
            "Do not invent facts. "
            "Do not mention the transcript, teacher, "
            "speaker, dataset, or source in questions. "
            "Make every question independently "
            "understandable."
        )

        if json_mode:

            instructions += (
                " Return ONLY valid JSON. "
                "Do not use markdown fences. "
                "Do not add commentary outside JSON."
            )

        response = client.responses.create(
            model=DEFAULT_MODEL,
            instructions=instructions,
            input=prompt,
            max_output_tokens=max_tokens,
        )

        text = str(
            getattr(
                response,
                "output_text",
                "",
            )
            or ""
        ).strip()

        if not text:

            return AIResult(
                success=False,
                provider="openai",
                model=DEFAULT_MODEL,
                error="OpenAI returned an empty response.",
            )

        if json_mode:

            try:
                json.loads(
                    text
                )

            except json.JSONDecodeError:

                cleaned = text.strip()

                if cleaned.startswith(
                    "```"
                ):

                    lines = (
                        cleaned.splitlines()
                    )

                    if lines:
                        lines = lines[1:]

                    if (
                        lines
                        and lines[-1].strip()
                        == "```"
                    ):

                        lines = lines[:-1]

                    cleaned = "\n".join(
                        lines
                    ).strip()

                try:

                    json.loads(
                        cleaned
                    )

                    text = cleaned

                except json.JSONDecodeError:

                    return AIResult(
                        success=False,
                        provider="openai",
                        model=DEFAULT_MODEL,
                        error=(
                            "OpenAI returned invalid JSON."
                        ),
                    )

        return AIResult(
            success=True,
            text=text,
            provider="openai",
            model=DEFAULT_MODEL,
            error=None,
        )

    except Exception as exc:

        return AIResult(
            success=False,
            provider="openai",
            model=DEFAULT_MODEL,
            error=str(exc),
        )