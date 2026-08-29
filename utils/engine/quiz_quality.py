"""
quiz_quality.py
---------------

Universal quiz quality validation.

Designed for:
- any educational subject
- any language
- multilingual lessons
- mixed-language transcripts

IMPORTANT:
This module does NOT try to "correct" subject terminology.
It validates structure and obvious quality problems only.

No AI calls are made here.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher


EXPECTED_REGIONS = {1, 2, 3, 4, 5}
VALID_TYPES = {"mcq", "short", "long"}


# ==========================================================
# NORMALIZATION
# ==========================================================

def normalize_text(
    text: str,
) -> str:
    """
    Normalize text ONLY for comparison.

    The original question/answer is never modified.
    """

    if not isinstance(text, str):
        return ""

    text = text.casefold()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# ==========================================================
# TEXT QUALITY
# ==========================================================

def valid_text(
    value,
    min_chars: int = 2,
) -> bool:

    return (
        isinstance(value, str)
        and len(value.strip()) >= min_chars
    )


# ==========================================================
# QUESTION SIMILARITY
# ==========================================================

def similarity(
    first: str,
    second: str,
) -> float:

    first = normalize_text(first)
    second = normalize_text(second)

    if not first or not second:
        return 0.0

    return SequenceMatcher(
        None,
        first,
        second,
    ).ratio()


# ==========================================================
# VALIDATE ONE QUESTION
# ==========================================================

def validate_question(
    question: dict,
) -> list[str]:

    problems = []

    if not isinstance(question, dict):

        return [
            "Question is not an object."
        ]

    question_type = question.get(
        "type"
    )

    if question_type not in VALID_TYPES:

        problems.append(
            "Invalid question type."
        )

    region = question.get(
        "region"
    )

    if region not in EXPECTED_REGIONS:

        problems.append(
            "Invalid video region."
        )

    question_text = question.get(
        "question"
    )

    if not valid_text(
        question_text,
        min_chars=5,
    ):

        problems.append(
            "Question text is empty or too short."
        )

    answer = question.get(
        "answer"
    )

    if not valid_text(
        answer,
        min_chars=1,
    ):

        problems.append(
            "Answer is empty."
        )

    # ------------------------------------------------------
    # MCQ-specific checks
    # ------------------------------------------------------

    if question_type == "mcq":

        options = question.get(
            "options"
        )

        if not isinstance(
            options,
            list,
        ):

            problems.append(
                "MCQ options are missing."
            )

        else:

            if len(options) != 4:

                problems.append(
                    "MCQ must have exactly four options."
                )

            cleaned_options = []

            for option in options:

                if not valid_text(
                    option,
                    min_chars=1,
                ):

                    problems.append(
                        "MCQ contains an empty option."
                    )

                else:

                    cleaned_options.append(
                        normalize_text(option)
                    )

            # No duplicate options.
            if (
                len(cleaned_options)
                != len(set(cleaned_options))
            ):

                problems.append(
                    "MCQ contains duplicate options."
                )

            if (
                valid_text(answer)
                and answer not in options
            ):

                problems.append(
                    "MCQ answer does not exactly "
                    "match an option."
                )

    return problems


# ==========================================================
# DUPLICATE DETECTION
# ==========================================================

QUESTION_STOP_WORDS = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "was",
    "were",
    "what",
    "why",
    "how",
    "when",
    "where",
    "which",
    "who",
    "do",
    "does",
    "did",
    "can",
    "could",
    "would",
    "should",
    "in",
    "on",
    "of",
    "to",
    "for",
    "from",
    "with",
    "and",
    "or",
    "by",
    "using",
    "used",
    "use",
    "explain",
    "describe",
    "compare",
    "discuss",
}


def meaningful_words(
    text: str,
) -> set[str]:

    text = normalize_text(
        text
    )

    words = re.findall(
        r"[a-z0-9_+#]+",
        text,
    )

    return {
        word
        for word in words
        if (
            len(word) > 1
            and word
            not in QUESTION_STOP_WORDS
        )
    }


def concept_similarity(
    first: str,
    second: str,
) -> dict:

    first_words = meaningful_words(
        first
    )

    second_words = meaningful_words(
        second
    )

    if (
        not first_words
        or not second_words
    ):

        return {
            "jaccard": 0.0,
            "containment": 0.0,
        }

    intersection = (
        first_words
        &
        second_words
    )

    union = (
        first_words
        |
        second_words
    )

    smaller_size = min(
        len(first_words),
        len(second_words),
    )

    jaccard = (
        len(intersection)
        /
        len(union)
        if union
        else 0.0
    )

    containment = (
        len(intersection)
        /
        smaller_size
        if smaller_size
        else 0.0
    )

    return {
        "jaccard": round(
            jaccard,
            3,
        ),
        "containment": round(
            containment,
            3,
        ),
    }


def find_duplicates(
    questions: list[dict],
    sequence_threshold: float = 0.92,
    jaccard_threshold: float = 0.72,
    containment_threshold: float = 0.85,
) -> list[dict]:

    duplicates = []

    for first_index in range(
        len(questions)
    ):

        first_question = questions[
            first_index
        ]

        first = str(
            first_question.get(
                "question",
                "",
            )
        )

        for second_index in range(
            first_index + 1,
            len(questions),
        ):

            second_question = questions[
                second_index
            ]

            second = str(
                second_question.get(
                    "question",
                    "",
                )
            )

            sequence_score = similarity(
                first,
                second,
            )

            concept_score = (
                concept_similarity(
                    first,
                    second,
                )
            )

            jaccard = concept_score[
                "jaccard"
            ]

            containment = concept_score[
                "containment"
            ]

            # --------------------------------------------------
            # SAME-TYPE vs CROSS-TYPE
            # --------------------------------------------------
            #
            # Same-type questions should be strongly distinct.
            #
            # Cross-type questions may legitimately discuss the
            # same broad topic at different learning depths.
            # Therefore we only flag cross-type questions when
            # their meaningful vocabulary overlaps very heavily.
            # --------------------------------------------------

            same_type = (
                first_question.get(
                    "type"
                )
                ==
                second_question.get(
                    "type"
                )
            )

            duplicate = False
            reason = ""

            if (
                sequence_score
                >= sequence_threshold
            ):

                duplicate = True
                reason = "wording"

            elif same_type and (
                jaccard
                >= jaccard_threshold
                or containment
                >= containment_threshold
            ):

                duplicate = True
                reason = "concept"

            elif (
                not same_type
                and (
                    jaccard >= 0.80
                    or containment >= 0.95
                )
            ):

                duplicate = True
                reason = "cross-type concept"

            if duplicate:

                duplicates.append({
                    "first": first_index,
                    "second": second_index,
                    "similarity": round(
                        sequence_score,
                        3,
                    ),
                    "jaccard": jaccard,
                    "containment": containment,
                    "reason": reason,
                })

    return duplicates


# ==========================================================
# TYPE + REGION COVERAGE
# ==========================================================

def check_coverage(
    questions: list[dict],
) -> dict:

    coverage = {
        "mcq": set(),
        "short": set(),
        "long": set(),
    }

    for question in questions:

        question_type = question.get(
            "type"
        )

        region = question.get(
            "region"
        )

        if (
            question_type in coverage
            and region in EXPECTED_REGIONS
        ):

            coverage[
                question_type
            ].add(region)

    return {
        question_type: (
            regions
            == EXPECTED_REGIONS
        )
        for question_type, regions
        in coverage.items()
    }


# ==========================================================
# COMPLETE QUIZ VALIDATION
# ==========================================================

def validate_quiz_quality(
    questions: list[dict],
) -> dict:
    """
    Validate a complete 15-question quiz.

    Does NOT modify generated educational content.
    """

    if not isinstance(
        questions,
        list,
    ):

        return {
            "valid": False,
            "count": 0,
            "errors": [
                "Questions must be a list."
            ],
            "duplicates": [],
            "coverage": {},
        }

    errors = []
    warnings = []

    if len(questions) != 15:

        errors.append(
            "Quiz must contain exactly 15 questions."
        )

    # ------------------------------------------------------
    # Individual validation
    # ------------------------------------------------------

    for index, question in enumerate(
        questions,
        start=1,
    ):

        problems = validate_question(
            question
        )

        for problem in problems:

            errors.append(
                f"Question {index}: {problem}"
            )

    # ------------------------------------------------------
    # Exact type counts
    # ------------------------------------------------------

    counts = {
        "mcq": 0,
        "short": 0,
        "long": 0,
    }

    for question in questions:

        question_type = question.get(
            "type"
        )

        if question_type in counts:

            counts[
                question_type
            ] += 1

    for question_type in counts:

        if counts[
            question_type
        ] != 5:

            errors.append(
                f"Expected 5 {question_type} "
                f"questions, found "
                f"{counts[question_type]}."
            )

    # ------------------------------------------------------
    # Region coverage
    # ------------------------------------------------------

    coverage = check_coverage(
        questions
    )

    for question_type, complete in (
        coverage.items()
    ):

        if not complete:

            errors.append(
                f"{question_type} does not "
                "cover all five video regions."
            )

    # ------------------------------------------------------
    # Duplicate questions
    # ------------------------------------------------------

    duplicates = find_duplicates(
        questions
    )

    # We flag duplicates instead of silently rewriting them.
    for duplicate in duplicates:

        warnings.append(
            "Possible duplicate questions: "
            f"{duplicate['first'] + 1} and "
            f"{duplicate['second'] + 1} "
            f"(reason: {duplicate['reason']}, "
            f"wording: {duplicate['similarity']}, "
            f"concept: {duplicate['jaccard']}, "
            f"containment: {duplicate['containment']})."
        )

    return {
        "valid": not errors,
        "count": len(questions),
        "counts": counts,
        "coverage": coverage,
        "duplicates": duplicates,
        "warnings": warnings,
        "errors": errors,
    }