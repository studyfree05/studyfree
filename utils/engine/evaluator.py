"""
answer_evaluator.py

AI-first written-answer evaluator with a deterministic
offline fallback.

Used by:
- Short answers
- Long answers

Return format:
{
    "success": bool,
    "provider": "...",
    "evaluations": [...]
}
"""

from __future__ import annotations

import json
import re
from typing import Any

from utils.engine.ai_provider import generate_ai


# ==========================================================
# TEXT HELPERS
# ==========================================================

def _normalize(text: Any) -> str:
    return " ".join(
        str(text or "")
        .strip()
        .casefold()
        .split()
    )


def _tokens(text: Any) -> set[str]:
    words = re.findall(
        r"[A-Za-z0-9]+",
        _normalize(text),
    )

    stop_words = {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "and",
        "or",
        "to",
        "of",
        "in",
        "on",
        "for",
        "with",
        "by",
        "from",
        "that",
        "this",
        "it",
        "as",
        "be",
        "can",
        "does",
        "do",
        "how",
        "what",
        "why",
        "when",
        "where",
    }

    return {
        word
        for word in words
        if len(word) > 2
        and word not in stop_words
    }


# ==========================================================
# OFFLINE EVALUATION
# ==========================================================

def _offline_one(
    item: dict,
) -> dict:

    expected = str(
        item.get(
            "expected_answer",
            "",
        )
    ).strip()

    student = str(
        item.get(
            "student_answer",
            "",
        )
    ).strip()

    question_type = str(
        item.get(
            "type",
            "short",
        )
    ).lower()

    if not student:

        return {
            "score": 0,
            "status": "skipped",
            "feedback": "Question skipped.",
            "missing": [
                expected
            ]
            if expected
            else [],
            "next_topic": "",
        }

    if not expected:

        return {
            "score": 0,
            "status": "incorrect",
            "feedback": (
                "No reference answer is available."
            ),
            "missing": [],
            "next_topic": "",
        }

    student_normalized = _normalize(
        student
    )

    expected_normalized = _normalize(
        expected
    )

    # Exact semantic text match.
    if (
        student_normalized
        == expected_normalized
    ):

        return {
            "score": 1,
            "status": "correct",
            "feedback": (
                "Correct. Your answer matches "
                "the reference answer."
            ),
            "missing": [],
            "next_topic": "",
        }

    expected_tokens = _tokens(
        expected
    )

    student_tokens = _tokens(
        student
    )

    if not expected_tokens:

        return {
            "score": 0,
            "status": "incorrect",
            "feedback": (
                "The answer does not match "
                "the reference answer."
            ),
            "missing": [],
            "next_topic": "",
        }

    overlap = (
        len(
            expected_tokens
            & student_tokens
        )
        / len(expected_tokens)
    )

    missing_tokens = sorted(
        expected_tokens
        - student_tokens
    )

    # Strong coverage.
    if overlap >= 0.75:

        return {
            "score": 1,
            "status": "correct",
            "feedback": (
                "Correct. Your answer contains "
                "the main concepts required."
            ),
            "missing": [],
            "next_topic": "",
        }

    # Good partial coverage.
    if overlap >= 0.45:

        missing = missing_tokens[:5]

        return {
            "score": 0.5,
            "status": "partial",
            "feedback": (
                "Partially correct. Your answer "
                "contains some of the required "
                "concepts, but it is missing "
                "important details."
            ),
            "missing": missing,
            "next_topic": "",
        }

    # A short student answer containing an important
    # reference phrase can still receive partial credit.
    important_expected_words = sorted(
        expected_tokens,
        key=len,
        reverse=True,
    )[:5]

    phrase_hits = sum(
        1
        for word in important_expected_words
        if word in student_normalized
    )

    if (
        phrase_hits >= 2
        and question_type
        in {
            "short",
            "long",
        }
    ):

        return {
            "score": 0.5,
            "status": "partial",
            "feedback": (
                "Partially correct. Your answer "
                "captures part of the expected idea, "
                "but more explanation is needed."
            ),
            "missing": missing_tokens[:5],
            "next_topic": "",
        }

    return {
        "score": 0,
        "status": "incorrect",
        "feedback": (
            "Your answer does not contain "
            "enough of the key concepts required."
        ),
        "missing": missing_tokens[:5],
        "next_topic": "",
    }


# ==========================================================
# AI EVALUATION
# ==========================================================

def _ai_evaluate(
    items: list[dict],
) -> dict | None:

    prompt = f"""
You are evaluating written answers for an educational quiz.

Evaluate every answer only against its question and
reference answer.

Do not use outside knowledge.

Minor wording differences are acceptable.

For Short Answer:
- judge the key concept
- partial credit is allowed

For Long Answer:
- judge the important factual points
- do not require exact wording
- do not penalize grammar

Return ONLY JSON:

{{
  "evaluations": [
    {{
      "index": 0,
      "score": 1,
      "status": "correct",
      "feedback": "...",
      "missing": [],
      "next_topic": ""
    }}
  ]
}}

score must be one of:
0, 0.5, 1

status must be:
correct, partial, incorrect, skipped

QUESTIONS:

{json.dumps(
    items,
    ensure_ascii=False,
    indent=2,
)}
""".strip()

    result = generate_ai(
        prompt,
        task="answer_evaluation",
        json_mode=True,
        max_tokens=1200,
        temperature=0.0,
    )

    if not result.success:
        return None

    try:

        data = json.loads(
            result.text
        )

    except Exception:

        return None

    evaluations = data.get(
        "evaluations"
    )

    if not isinstance(
        evaluations,
        list,
    ):
        return None

    cleaned = []

    for item in evaluations:

        if not isinstance(
            item,
            dict,
        ):
            continue

        index = item.get(
            "index"
        )

        if not isinstance(
            index,
            int,
        ):
            continue

        score = item.get(
            "score",
            0,
        )

        if score not in {
            0,
            0.5,
            1,
        }:
            score = 0

        status = item.get(
            "status",
            "incorrect",
        )

        if status not in {
            "correct",
            "partial",
            "incorrect",
            "skipped",
        }:
            status = (
                "correct"
                if score == 1
                else "partial"
                if score == 0.5
                else "incorrect"
            )

        cleaned.append(
            {
                "index": index,
                "score": score,
                "status": status,
                "feedback": str(
                    item.get(
                        "feedback",
                        "",
                    )
                ).strip(),
                "missing": (
                    item.get(
                        "missing",
                        [],
                    )
                    if isinstance(
                        item.get(
                            "missing",
                            [],
                        ),
                        list,
                    )
                    else []
                ),
                "next_topic": str(
                    item.get(
                        "next_topic",
                        "",
                    )
                ).strip(),
            }
        )

    if not cleaned:
        return None

    return {
        "evaluations": cleaned
    }


# ==========================================================
# PUBLIC FUNCTION
# ==========================================================

def evaluate_written_answers(
    items: list[dict],
) -> dict:

    if not isinstance(
        items,
        list,
    ):
        return {
            "success": False,
            "provider": "",
            "evaluations": [],
            "error": (
                "Written answer batch "
                "must be a list."
            ),
        }

    if not items:
        return {
            "success": True,
            "provider": "offline",
            "evaluations": [],
            "error": None,
        }

    # ------------------------------------------------------
    # Try online AI first.
    # ------------------------------------------------------

    ai_result = _ai_evaluate(
        items
    )

    if ai_result is not None:

        evaluations = (
            ai_result["evaluations"]
        )

        # Make sure every input item has an evaluation.
        by_index = {
            item["index"]: item
            for item in evaluations
        }

        complete = []

        for index in range(
            len(items)
        ):

            if index in by_index:

                complete.append(
                    by_index[index]
                )

            else:

                offline = _offline_one(
                    items[index]
                )

                offline["index"] = index

                complete.append(
                    offline
                )

        return {
            "success": True,
            "provider": "ai",
            "evaluations": complete,
            "error": None,
        }

    # ------------------------------------------------------
    # ALL AI PROVIDERS FAILED
    # ------------------------------------------------------

    evaluations = []

    for index, item in enumerate(
        items
    ):

        evaluation = _offline_one(
            item
        )

        evaluation["index"] = index

        evaluations.append(
            evaluation
        )

    return {
        "success": True,
        "provider": "offline",
        "evaluations": evaluations,
        "error": None,
    }