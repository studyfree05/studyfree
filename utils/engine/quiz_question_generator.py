"""
quiz_question_generator.py

Builds the final 15-question educational quiz.

Final structure:
- 5 MCQs
- 5 short-answer questions
- 5 long-answer questions
"""

from __future__ import annotations

from .question_generator import generate_topic
from .short_question_generator import generate_short_topic
from .long_question_generator import generate_long_topic


MCQ_COUNT = 5
SHORT_COUNT = 5
LONG_COUNT = 5


# ==========================================================
# DISTRIBUTE QUESTION COUNT ACROSS TOPICS
# ==========================================================

def distribute_counts(
    total: int,
    topic_count: int,
) -> list[int]:

    if topic_count <= 0:
        return []

    # Don't use more topics than questions.
    active_topics = min(
        total,
        topic_count,
    )

    counts = [
        total // active_topics
        for _ in range(active_topics)
    ]

    remainder = total % active_topics

    for i in range(remainder):
        counts[i] += 1

    return counts


# ==========================================================
# NORMALIZE QUESTION
# ==========================================================

def normalize_question(
    question: dict,
    question_type: str,
    topic_name: str,
) -> dict:

    result = dict(question)

    result["type"] = question_type
    result["topic"] = topic_name

    return result


# ==========================================================
# GENERATE ONE QUESTION TYPE
# ==========================================================

def generate_type(
    topics: list[dict],
    total: int,
    generator,
    question_type: str,
) -> list[dict]:

    counts = distribute_counts(
        total,
        len(topics),
    )

    questions = []

    for topic, count in zip(
        topics,
        counts,
    ):

        if count <= 0:
            continue

        print(
            f"Generating {count} {question_type} "
            f"for: {topic['topic']}"
        )

        generated = generator(
            topic,
            count,
        )

        for question in generated:

            questions.append(
                normalize_question(
                    question,
                    question_type,
                    topic["topic"],
                )
            )

    return questions[:total]


# ==========================================================
# FINAL QUIZ GENERATOR
# ==========================================================

def generate_full_quiz_questions(
    knowledge: dict,
) -> dict:

    topics = knowledge.get(
        "topics",
        [],
    )

    topics = [
        topic
        for topic in topics
        if isinstance(topic, dict)
        and topic.get("topic")
        and isinstance(
            topic.get("points"),
            list,
        )
        and topic["points"]
    ]

    if not topics:

        return {
            "success": False,
            "mcq": [],
            "short": [],
            "long": [],
            "questions": [],
            "count": 0,
            "error": "No valid topics found.",
        }

    # ------------------------------------------------------
    # 5 MCQs
    # ------------------------------------------------------

    print("\n" + "=" * 60)
    print("GENERATING 5 MCQs")
    print("=" * 60)

    mcq_questions = generate_type(
        topics,
        MCQ_COUNT,
        generate_topic,
        "mcq",
    )

    # ------------------------------------------------------
    # 5 SHORT
    # ------------------------------------------------------

    print("\n" + "=" * 60)
    print("GENERATING 5 SHORT QUESTIONS")
    print("=" * 60)

    short_questions = generate_type(
        topics,
        SHORT_COUNT,
        generate_short_topic,
        "short",
    )

    # ------------------------------------------------------
    # 5 LONG
    # ------------------------------------------------------

    print("\n" + "=" * 60)
    print("GENERATING 5 LONG QUESTIONS")
    print("=" * 60)

    long_questions = generate_type(
        topics,
        LONG_COUNT,
        generate_long_topic,
        "long",
    )

    # ------------------------------------------------------
    # COMBINE
    # ------------------------------------------------------

    all_questions = (
        mcq_questions
        + short_questions
        + long_questions
    )

    complete = (
        len(mcq_questions) == MCQ_COUNT
        and len(short_questions) == SHORT_COUNT
        and len(long_questions) == LONG_COUNT
    )

    return {
        "success": complete,

        "mcq": mcq_questions,
        "short": short_questions,
        "long": long_questions,

        "questions": all_questions,

        "counts": {
            "mcq": len(mcq_questions),
            "short": len(short_questions),
            "long": len(long_questions),
            "total": len(all_questions),
        },

        "count": len(all_questions),

        "error": (
            None
            if complete
            else "Unable to generate all 15 questions."
        ),
    }