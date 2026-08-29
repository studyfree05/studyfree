"""
long_question_generator.py

Generates grounded descriptive/long-answer questions
from video knowledge.
"""

from __future__ import annotations

import hashlib
import json

from .cache import exists, load, save
from .config import QUESTION_MODEL
from .ollama_client import generate


LONG_CACHE_DIR = "cache/long_questions"
LONG_PROMPT_VERSION = "v1_grounded"


# ==========================================================
# JSON SCHEMA
# ==========================================================

def build_long_schema(count: int) -> dict:

    return {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string"
                        },
                        "answer": {
                            "type": "string"
                        },
                        "explanation": {
                            "type": "string"
                        },
                        "real_life_example": {
                            "type": "string"
                        },
                        "memory_trick": {
                            "type": "string"
                        },
                        "key_points": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        },
                        "difficulty": {
                            "type": "string",
                            "enum": [
                                "easy",
                                "medium",
                                "hard"
                            ]
                        }
                    },
                    "required": [
                        "question",
                        "answer",
                        "explanation",
                        "real_life_example",
                        "memory_trick",
                        "key_points",
                        "difficulty"
                    ]
                }
            }
        },
        "required": ["questions"]
    }


# ==========================================================
# PROMPT
# ==========================================================

def build_long_prompt(
    topic_name: str,
    points: list[str],
    count: int,
) -> str:

    facts = "\n".join(
        f"- {point}"
        for point in points
    )

    return f"""
Create exactly {count} descriptive LONG-ANSWER questions.

TOPIC:
{topic_name}

SOURCE INFORMATION:
{facts}

STRICT RULES:

1. Use ONLY the supplied source information.
2. Do not introduce outside technical facts.
3. Do not mention "FACT", "SOURCE", or numbered facts
   in the student-facing question or answer.
4. Questions should test explanation and understanding.
5. A student should normally answer in a paragraph.
6. Provide a clear model answer.
7. Provide a detailed but easy-to-understand explanation.
8. Give a practical real-life example when possible.
9. Give a short and useful memory trick.
10. Provide key_points containing the important ideas
    expected in a good student answer.
11. Avoid duplicate questions.
12. Return JSON only.

Each question must contain:

question
answer
explanation
real_life_example
memory_trick
key_points
difficulty
"""


# ==========================================================
# CACHE
# ==========================================================

def long_cache_key(
    topic: dict,
    count: int,
) -> str:

    text = LONG_PROMPT_VERSION
    text += "\n" + topic["topic"]
    text += "\n" + "\n".join(topic["points"])
    text += f"\n{count}"

    return hashlib.md5(
        text.encode("utf-8")
    ).hexdigest()


# ==========================================================
# VALIDATION
# ==========================================================

def validate_long_question(question: dict) -> bool:

    if not isinstance(question, dict):
        return False

    required_text = [
        "question",
        "answer",
        "explanation",
        "real_life_example",
        "memory_trick",
        "difficulty",
    ]

    for key in required_text:

        if key not in question:
            return False

        question[key] = str(
            question[key]
        ).strip()

        if not question[key]:
            return False

    key_points = question.get("key_points")

    if not isinstance(key_points, list):
        return False

    key_points = [
        str(point).strip()
        for point in key_points
        if str(point).strip()
    ]

    if not key_points:
        return False

    question["key_points"] = key_points
    question["type"] = "long"

    return True


# ==========================================================
# GENERATE
# ==========================================================

def generate_long_topic(
    topic: dict,
    count: int,
):

    cache_key = long_cache_key(
        topic,
        count,
    )

    if exists(
        LONG_CACHE_DIR,
        cache_key,
    ):
        print(
            f"✓ Long cache hit: "
            f"{topic['topic']}"
        )

        return load(
            LONG_CACHE_DIR,
            cache_key,
        )

    prompt = build_long_prompt(
        topic["topic"],
        topic["points"],
        count,
    )

    schema = build_long_schema(count)

    response = generate(
        model=QUESTION_MODEL,
        prompt=prompt,
        temperature=0.1,
        top_p=0.8,
        num_predict=1000,
        num_ctx=1280,
        num_thread=4,
        json_schema=schema,
    )

    try:
        data = json.loads(response)

    except Exception as e:

        print(
            "Long question JSON error:",
            e,
        )

        return []

    questions = data.get(
        "questions",
        [],
    )

    valid = []

    for question in questions:

        if validate_long_question(question):
            valid.append(question)

    print(
        f"Long questions: "
        f"{len(valid)}/{count}"
    )

    save(
        LONG_CACHE_DIR,
        cache_key,
        valid,
    )

    return valid