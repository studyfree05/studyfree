"""
StudyFree Question Quality Validator
"""

from difflib import SequenceMatcher


def similarity(a, b):
    return SequenceMatcher(
        None,
        str(a).lower(),
        str(b).lower(),
    ).ratio()


def validate_question(question):

    errors = []

    # Required fields
    required = [
        "question",
        "answer",
        "type",
    ]

    for field in required:

        if field not in question:

            errors.append(
                f"Missing field: {field}"
            )

    if errors:

        return {
            "valid": False,
            "errors": errors,
        }

    # Empty question

    if len(question["question"].strip()) < 15:

        errors.append(
            "Question too short."
        )

    # Empty answer

    if len(str(question["answer"]).strip()) == 0:

        errors.append(
            "Missing answer."
        )

    # MCQ checks

    if question["type"] == "mcq":

        options = question.get(
            "options",
            [],
        )

        if len(options) != 4:

            errors.append(
                "MCQ must have exactly 4 options."
            )

        if len(set(options)) != len(options):

            errors.append(
                "Duplicate options."
            )

        if question["answer"] not in options:

            errors.append(
                "Correct answer missing from options."
            )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
    }