"""
fast_quiz_generator.py
-----------------------

Generates the 15-question quiz skeleton from balanced
whole-video regions using ONE Ollama call.

Output:
- 5 MCQs
- 5 short questions
- 5 long questions

No enrichment yet.
"""

from __future__ import annotations

import json
import re
import time

from .ollama_client import generate
from .config import QUESTION_MODEL
from .whole_video_sampler import build_combined_context


# ==========================================================
# JSON EXTRACTION
# ==========================================================

def _extract_json(raw: str):

    if not raw:
        return None

    raw = raw.strip()

    raw = re.sub(
        r"^```(?:json)?",
        "",
        raw,
        flags=re.IGNORECASE,
    )

    raw = re.sub(
        r"```$",
        "",
        raw,
    )

    raw = raw.strip()

    try:
        return json.loads(raw)

    except json.JSONDecodeError:
        pass

    start = raw.find("{")
    end = raw.rfind("}")

    if start == -1 or end == -1:
        return None

    try:
        return json.loads(
            raw[start:end + 1]
        )

    except json.JSONDecodeError:
        return None


# ==========================================================
# VALIDATION
# ==========================================================

def _valid_question(item: dict) -> bool:

    if not isinstance(item, dict):
        return False

    question = item.get("question")

    if not isinstance(question, str):
        return False

    if len(question.strip()) < 8:
        return False

    return True


def _validate_mcq(item: dict) -> bool:

    if not _valid_question(item):
        return False

    options = item.get("options")
    answer = item.get("answer")

    if not isinstance(options, list):
        return False

    if len(options) != 4:
        return False

    if not all(
        isinstance(option, str)
        and option.strip()
        for option in options
    ):
        return False

    if not isinstance(answer, str):
        return False

    if answer not in options:
        return False

    return True


def _validate_result(data: dict):

    if not isinstance(data, dict):
        return None

    mcq = data.get("mcq")
    short = data.get("short")
    long_questions = data.get("long")

    if not isinstance(mcq, list):
        return None

    if not isinstance(short, list):
        return None

    if not isinstance(long_questions, list):
        return None

    mcq = [
        item
        for item in mcq
        if _validate_mcq(item)
    ]

    short = [
        item
        for item in short
        if _valid_question(item)
    ]

    long_questions = [
        item
        for item in long_questions
        if _valid_question(item)
    ]

    return {
        "mcq": mcq[:5],
        "short": short[:5],
        "long": long_questions[:5],
    }


# ==========================================================
# GENERATE
# ==========================================================

def generate_fast_quiz(
    region_result: dict,
) -> dict:

    start = time.perf_counter()

    context = build_combined_context(
        region_result
    )

    if not context:

        return {
            "success": False,
            "mcq": [],
            "short": [],
            "long": [],
            "counts": {},
            "time": 0,
            "error": "No video context.",
        }

    prompt = f"""
You are creating an educational quiz strictly from a
video lesson transcript.

The transcript may contain Telugu, Hindi, English, or
mixed-language speech.

IMPORTANT:
The five VIDEO REGIONS represent different parts of the
same complete lesson.

Create EXACTLY:
- 5 MCQs
- 5 short-answer questions
- 5 long-answer questions

WHOLE-VIDEO COVERAGE:
- Use all five regions.
- Do not create all questions from the beginning.
- Questions must test concepts actually taught.
- Ignore greetings, filler speech and unrelated chatter.
- Write questions in clear English.
- Do not invent facts not supported by the transcript.
- Avoid duplicate questions.

MCQ:
Each MCQ must have exactly 4 options.
The answer must exactly equal one option.

SHORT:
Include question and concise answer.

LONG:
Include question and a useful detailed answer.

Return JSON only.

Required format:

{{
  "mcq": [
    {{
      "question": "...",
      "options": ["...", "...", "...", "..."],
      "answer": "..."
    }}
  ],
  "short": [
    {{
      "question": "...",
      "answer": "..."
    }}
  ],
  "long": [
    {{
      "question": "...",
      "answer": "..."
    }}
  ]
}}

VIDEO LESSON:

{context}
""".strip()

    try:

        raw = generate(
            model=QUESTION_MODEL,
            prompt=prompt,
            temperature=0.1,
            top_p=0.8,

            # 15 questions require more output than topics,
            # but keep it controlled for speed.
            num_predict=1800,

            # 11k transcript chars + prompt need a larger context.
            num_ctx=8192,

            num_thread=4,
            json_mode=True,
        )

        data = _extract_json(raw)

        if data is None:

            return {
                "success": False,
                "mcq": [],
                "short": [],
                "long": [],
                "counts": {},
                "time": round(
                    time.perf_counter() - start,
                    2,
                ),
                "error": "Invalid JSON.",
            }

        result = _validate_result(data)

        if result is None:

            return {
                "success": False,
                "mcq": [],
                "short": [],
                "long": [],
                "counts": {},
                "time": round(
                    time.perf_counter() - start,
                    2,
                ),
                "error": "Invalid quiz structure.",
            }

        counts = {
            "mcq": len(result["mcq"]),
            "short": len(result["short"]),
            "long": len(result["long"]),
        }

        counts["total"] = sum(
            counts.values()
        )

        return {
            "success": (
                counts["mcq"] == 5
                and counts["short"] == 5
                and counts["long"] == 5
            ),
            **result,
            "counts": counts,
            "time": round(
                time.perf_counter() - start,
                2,
            ),
            "error": (
                None
                if counts["total"] == 15
                else "Model did not return all 15 valid questions."
            ),
        }

    except Exception as exc:

        return {
            "success": False,
            "mcq": [],
            "short": [],
            "long": [],
            "counts": {},
            "time": round(
                time.perf_counter() - start,
                2,
            ),
            "error": str(exc),
        }