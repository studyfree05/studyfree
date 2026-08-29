"""
StudyFree Scoring Engine
------------------------

Fast local scoring for:
- MCQ
- short answers
- long answers

Uses:
- normalized text similarity
- important concept-word overlap
- contradiction protection

No AI/API call is required.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher


# ==========================================================
# COMMON WORDS
# ==========================================================

STOP_WORDS = {
    "a", "an", "the",
    "is", "are", "was", "were",
    "be", "been", "being",
    "to", "of", "in", "on", "at",
    "for", "from", "with", "by",
    "and", "or", "but",
    "that", "this", "these", "those",
    "it", "its",
    "as",
    "we", "you", "they",
    "can", "could", "would", "should",
    "will",
    "do", "does", "did",
    "have", "has", "had",
    "using", "used", "use",
}


# ==========================================================
# NORMALIZE
# ==========================================================

def normalize(text):

    text = str(
        text or ""
    ).lower().strip()

    text = re.sub(
        r"[^a-z0-9+#*/%<>=.!?-]+",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# ==========================================================
# SIMILARITY
# ==========================================================

def similarity(a, b):

    a = normalize(a)
    b = normalize(b)

    if not a or not b:
        return 0.0

    return SequenceMatcher(
        None,
        a,
        b,
    ).ratio()


# ==========================================================
# IMPORTANT WORDS
# ==========================================================

def important_words(text):

    words = re.findall(
        r"[a-z0-9+#]+",
        normalize(text),
    )

    return {
        word
        for word in words
        if (
            len(word) >= 3
            and word not in STOP_WORDS
        )
    }


# ==========================================================
# SIMPLE WORD NORMALIZATION
# ==========================================================

def concept_form(word):
    """
    Small normalization layer.

    This is intentionally conservative.
    It handles common wording differences without
    attempting full NLP.
    """

    replacements = {
        "changed": "change",
        "changing": "change",
        "changes": "change",

        "modified": "change",
        "modify": "change",
        "modifying": "change",

        "reusable": "reuse",
        "reused": "reuse",
        "using": "use",

        "performs": "perform",
        "performed": "perform",
        "performing": "perform",

        "functions": "function",
        "lists": "list",
        "tuples": "tuple",
        "variables": "variable",
        "values": "value",

        "immutable": "cannot_change",
        "mutable": "can_change",
    }

    return replacements.get(
        word,
        word,
    )


def concept_words(text):

    return {
        concept_form(word)
        for word in important_words(
            text
        )
    }


# ==========================================================
# CONCEPT OVERLAP
# ==========================================================

def concept_overlap(user, answer):

    expected = concept_words(
        answer
    )

    supplied = concept_words(
        user
    )

    if not expected:
        return 0.0

    matches = (
        expected
        & supplied
    )

    return (
        len(matches)
        / len(expected)
    )


# ==========================================================
# SPECIAL MEANING NORMALIZATION
# ==========================================================

def semantic_normalize(text):
    """
    Normalize a few common equivalent educational phrases.

    Examples:
    mutable       -> can_change
    immutable     -> cannot_change
    can be changed -> can_change

    This remains local and deterministic.
    """

    text = normalize(text)

    replacements = [
        (
            r"\bcannot be changed\b",
            " cannot_change ",
        ),
        (
            r"\bcan not be changed\b",
            " cannot_change ",
        ),
        (
            r"\bcannot change\b",
            " cannot_change ",
        ),
        (
            r"\bcan't be changed\b",
            " cannot_change ",
        ),
        (
            r"\bcan't change\b",
            " cannot_change ",
        ),
        (
            r"\bcannot be modified\b",
            " cannot_change ",
        ),
        (
            r"\bcan be changed\b",
            " can_change ",
        ),
        (
            r"\bcan change\b",
            " can_change ",
        ),
        (
            r"\bcan be modified\b",
            " can_change ",
        ),
        (
            r"\bimmutable\b",
            " cannot_change ",
        ),
        (
            r"\bmutable\b",
            " can_change ",
        ),
        (
            r"\breusable\b",
            " reuse ",
        ),
        (
            r"\buse it again\b",
            " reuse ",
        ),
        (
            r"\bused again\b",
            " reuse ",
        ),
    ]

    for pattern, replacement in replacements:

        text = re.sub(
            pattern,
            replacement,
            text,
        )

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


# ==========================================================
# SEMANTIC CONCEPT OVERLAP
# ==========================================================

def semantic_overlap(user, answer):

    return concept_overlap(
        semantic_normalize(user),
        semantic_normalize(answer),
    )


# ==========================================================
# CONTRADICTION CHECK
# ==========================================================

def has_basic_contradiction(
    user,
    answer,
):
    """
    Prevent obvious opposite answers from receiving
    concept-overlap credit.

    This is intentionally conservative.
    """

    u = semantic_normalize(
        user
    )

    a = semantic_normalize(
        answer
    )

    pairs = [
        (
            "can_change",
            "cannot_change",
        ),
        (
            " true ",
            " false ",
        ),
        (
            " increase ",
            " decrease ",
        ),
        (
            " greater ",
            " smaller ",
        ),
    ]

    padded_u = f" {u} "
    padded_a = f" {a} "

    for positive, negative in pairs:

        answer_positive = (
            positive in padded_a
        )

        answer_negative = (
            negative in padded_a
        )

        user_positive = (
            positive in padded_u
        )

        user_negative = (
            negative in padded_u
        )

        if (
            answer_positive
            and not answer_negative
            and user_negative
            and not user_positive
        ):
            return True

        if (
            answer_negative
            and not answer_positive
            and user_positive
            and not user_negative
        ):
            return True

    return False


# ==========================================================
# WRITTEN ANSWER METRICS
# ==========================================================

def written_metrics(
    user,
    answer,
):

    user = str(
        user or ""
    ).strip()

    answer = str(
        answer or ""
    ).strip()

    if not user:

        return {
            "similarity": 0.0,
            "concept_overlap": 0.0,
            "contradiction": False,
        }

    return {
        "similarity":
            similarity(
                user,
                answer,
            ),

        "concept_overlap":
            semantic_overlap(
                user,
                answer,
            ),

        "contradiction":
            has_basic_contradiction(
                user,
                answer,
            ),
    }


# ==========================================================
# MCQ
# ==========================================================

def score_mcq(
    user,
    answer,
):

    user = normalize(
        user
    )

    answer = normalize(
        answer
    )

    if (
        user
        and user == answer
    ):

        return {
            "score": 1,
            "status": "correct",
        }

    return {
        "score": 0,
        "status": "incorrect",
    }


# ==========================================================
# SHORT ANSWER
# ==========================================================

def score_short(
    user,
    answer,
):

    metrics = written_metrics(
        user,
        answer,
    )

    sim = metrics[
        "similarity"
    ]

    overlap = metrics[
        "concept_overlap"
    ]

    contradiction = metrics[
        "contradiction"
    ]

    if contradiction:

        return {
            "score": 0,
            "status": "incorrect",
        }

    # Very close wording.
    if sim >= 0.85:

        return {
            "score": 1,
            "status": "correct",
        }

    # Strong concept coverage even with different wording.
    if overlap >= 0.70:

        return {
            "score": 1,
            "status": "correct",
        }

    # Reasonable partial understanding.
    if (
        sim >= 0.50
        or overlap >= 0.40
    ):

        return {
            "score": 0.5,
            "status": "partial",
        }

    return {
        "score": 0,
        "status": "incorrect",
    }


# ==========================================================
# LONG ANSWER
# ==========================================================

def score_long(
    user,
    answer,
):

    metrics = written_metrics(
        user,
        answer,
    )

    sim = metrics[
        "similarity"
    ]

    overlap = metrics[
        "concept_overlap"
    ]

    contradiction = metrics[
        "contradiction"
    ]

    if contradiction:

        return {
            "score": 0,
            "status": "incorrect",
        }

    # Close wording.
    if sim >= 0.75:

        return {
            "score": 1,
            "status": "correct",
        }

    # Strong semantic/concept coverage.
    if overlap >= 0.65:

        return {
            "score": 1,
            "status": "correct",
        }

    # Some correct understanding.
    if (
        sim >= 0.40
        or overlap >= 0.35
    ):

        return {
            "score": 0.5,
            "status": "partial",
        }

    return {
        "score": 0,
        "status": "incorrect",
    }