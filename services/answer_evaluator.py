"""
StudyFree Written Answer Evaluator
----------------------------------

AI-first written-answer evaluator with a deterministic
offline fallback.

Flow:

Groq
  ↓
Gemini
  ↓
OpenRouter
  ↓ all unavailable
Offline evaluator

Used for:
- Short answers
- Long answers

MCQs are evaluated separately.
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
        "through",
        "their",
        "they",
        "them",
        "into",
        "than",
        "then",
        "also",
        "only",
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

    if not student:

        return {
            "score": 0,
            "status": "skipped",
            "feedback": "Question skipped.",
        }

    if not expected:

        return {
            "score": 0,
            "status": "incorrect",
            "feedback": (
                "No reference answer is available."
            ),
        }

    student_normalized = _normalize(
        student
    )

    expected_normalized = _normalize(
        expected
    )

    # Exact answer.
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
                "Your answer does not match "
                "the reference answer."
            ),
        }

    overlap = (
        len(
            expected_tokens
            & student_tokens
        )
        / len(expected_tokens)
    )

    # Strong concept coverage.
    if overlap >= 0.70:

        return {
            "score": 1,
            "status": "correct",
            "feedback": (
                "Correct. Your answer contains "
                "the main concepts required."
            ),
        }

    # Partial concept coverage.
    if overlap >= 0.35:

        missing = sorted(
            expected_tokens
            - student_tokens
        )

        missing_text = ", ".join(
            missing[:4]
        )

        if missing_text:

            feedback = (
                "Partially correct. Your answer "
                "contains some of the key concepts, "
                "but it is missing: "
                + missing_text
                + "."
            )

        else:

            feedback = (
                "Partially correct. Your answer "
                "contains part of the expected idea."
            )

        return {
            "score": 0.5,
            "status": "partial",
            "feedback": feedback,
        }

    return {
        "score": 0,
        "status": "incorrect",
        "feedback": (
            "Your answer does not contain "
            "enough of the key concepts required."
        ),
    }


# ==========================================================
# AI PROMPT
# ==========================================================

def _build_prompt(
    items: list[dict],
) -> str:

    payload = []

    for index, item in enumerate(
        items,
        start=1,
    ):

        payload.append(
            {
                "id": index,
                "type": str(
                    item.get(
                        "type",
                        "short",
                    )
                ),
                "question": str(
                    item.get(
                        "question",
                        "",
                    )
                ),
                "expected_answer": str(
                    item.get(
                        "expected_answer",
                        "",
                    )
                ),
                "student_answer": str(
                    item.get(
                        "student_answer",
                        "",
                    )
                ),
            }
        )

    return f"""
You are grading student answers for an educational quiz.

Evaluate the MEANING of each student answer, not exact wording.

A student answer is CORRECT when it expresses the essential
meaning needed to answer the question.

A student answer is PARTIAL when it contains some correct
understanding but misses an important part.

A student answer is INCORRECT when:
- the meaning is wrong
- it contradicts the expected answer
- it answers a different question
- it gives only unrelated keywords
- it contains insufficient relevant information

Do not give credit merely because some words overlap.

For SHORT answers:
Judge the essential concept.

For LONG answers:
Judge the important factual points and explanation.

Allowed status values:
"correct"
"partial"
"incorrect"
"skipped"

Allowed scores:
correct = 1
partial = 0.5
incorrect = 0
skipped = 0

Return exactly one evaluation for every item.

Return JSON only:

{{
  "evaluations": [
    {{
      "id": 1,
      "status": "correct",
      "score": 1,
      "feedback": "..."
    }}
  ]
}}

ITEMS:

{json.dumps(
    payload,
    ensure_ascii=False,
    indent=2,
)}
""".strip()


# ==========================================================
# VALIDATE AI RESULT
# ==========================================================

def _validate_evaluation(
    item: Any,
) -> dict | None:

    if not isinstance(
        item,
        dict,
    ):
        return None

    try:

        item_id = int(
            item.get(
                "id"
            )
        )

    except Exception:

        return None

    status = str(
        item.get(
            "status",
            "",
        )
    ).strip().lower()

    if status not in {
        "correct",
        "partial",
        "incorrect",
        "skipped",
    }:
        return None

    score_map = {
        "correct": 1,
        "partial": 0.5,
        "incorrect": 0,
        "skipped": 0,
    }

    return {
        "id": item_id,
        "status": status,
        "score": score_map[status],
        "feedback": str(
            item.get(
                "feedback",
                "",
            )
        ).strip(),
    }


# ==========================================================
# PUBLIC EVALUATOR
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
            "evaluations": [],
            "error": (
                "Items must be a list."
            ),
        }

    if not items:

        return {
            "success": True,
            "evaluations": [],
            "provider": "none",
            "model": "",
            "error": None,
        }

    # ======================================================
    # ONLINE AI
    # ======================================================

    prompt = _build_prompt(
        items
    )

    result = generate_ai(
        prompt=prompt,
        task="answer_evaluation",
        json_mode=True,
        max_tokens=1200,
        temperature=0.0,
    )

    if result.success:

        try:

            data = json.loads(
                result.text
            )

        except Exception:

            data = None

        if isinstance(
            data,
            dict,
        ):

            raw = data.get(
                "evaluations",
                [],
            )

            if isinstance(
                raw,
                list,
            ):

                valid = []

                seen_ids = set()

                for item in raw:

                    checked = (
                        _validate_evaluation(
                            item
                        )
                    )

                    if checked is None:
                        continue

                    item_id = checked[
                        "id"
                    ]

                    if item_id in seen_ids:
                        continue

                    if not (
                        1
                        <= item_id
                        <= len(items)
                    ):
                        continue

                    seen_ids.add(
                        item_id
                    )

                    valid.append(
                        checked
                    )

                valid.sort(
                    key=lambda x: x["id"]
                )

                # Complete AI batch.
                if len(valid) == len(items):

                    return {
                        "success": True,
                        "evaluations": valid,
                        "provider": result.provider,
                        "model": result.model,
                        "error": None,
                    }

    # ======================================================
    # ALL ONLINE AI FAILED
    # ======================================================

    offline_evaluations = []

    for index, item in enumerate(
        items,
        start=1,
    ):

        evaluation = _offline_one(
            item
        )

        evaluation["id"] = index

        offline_evaluations.append(
            evaluation
        )

    return {
        "success": True,
        "evaluations": offline_evaluations,
        "provider": "offline",
        "model": "rule-based-answer-evaluator",
        "error": None,
    }