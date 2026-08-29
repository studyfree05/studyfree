"""
validator.py

Validates and cleans generated quiz questions.
"""

from __future__ import annotations

import random


def normalize(text: str) -> str:
    """Normalize text for comparisons."""
    return " ".join(str(text).strip().lower().split())


def remove_duplicates(questions: list[dict]) -> list[dict]:
    """
    Remove duplicate questions.
    """

    seen = set()
    unique = []

    for q in questions:
        key = normalize(q["question"])

        if key in seen:
            continue

        seen.add(key)
        unique.append(q)

    return unique


def validate_options(question: dict) -> bool:
    """
    Validate answer options.
    """

    options = question.get("options", [])

    if len(options) != 4:
        return False

    options = [str(o).strip() for o in options]

    # Remove duplicate options
    if len(set(options)) != 4:
        return False

    if question["answer"] not in options:
        return False

    return True


def shuffle_options(question: dict) -> dict:
    """
    Shuffle options while preserving the correct answer.
    """

    options = question["options"][:]
    answer = question["answer"]

    random.shuffle(options)

    question["options"] = options
    question["answer"] = answer

    return question


def validate_questions(questions: list[dict]) -> list[dict]:
    """
    Validate all questions.
    """

    cleaned = []

    questions = remove_duplicates(questions)

    for q in questions:

        if validate_options(q):
            cleaned.append(shuffle_options(q))

    return cleaned