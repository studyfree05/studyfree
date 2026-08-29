"""
short_question_generator.py

Generates grounded short-answer questions from video knowledge.
"""

from __future__ import annotations

import hashlib
import json

from .cache import exists, load, save
from .config import QUESTION_MODEL
from .ollama_client import generate


SHORT_CACHE_DIR = "cache/short_questions"
SHORT_PROMPT_VERSION = "v1_grounded"


# ==========================================================
# JSON SCHEMA
# ==========================================================

def build_short_schema(count: int) -> dict:

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

def build_short_prompt(
    topic_name: str,
    points: list[str],
    count: int,
) -> str:

    facts = "\n".join(
        f"FACT {i}: {point}"
        for i, point in enumerate(points, start=1)
    )

    return f"""
Create exactly {count} SHORT-ANSWER questions.

TOPIC:
{topic_name}

SOURCE FACTS:
{facts}

STRICT RULES:

1. Questions must be based ONLY on SOURCE FACTS.
2. Do not introduce outside facts.
3. The student should normally answer in 1-3 sentences.
4. Questions must test understanding, not just copying.
5. Provide a concise model answer.
6. Explain the concept clearly.
7. Give a simple real-life example when possible.
8. Give a short useful memory trick.
9. Do not invent technical information.
10. Return JSON only.

Each question must contain:

question
answer
explanation
real_life_example
memory_trick
difficulty
"""


# ==========================================================
# CACHE KEY
# ==========================================================

def short_cache_key(
    topic: dict,
    count: int,
) -> str:

    text = SHORT_PROMPT_VERSION
    text += "\n" + topic["topic"]
    text += "\n" + "\n".join(topic["points"])
    text += f"\n{count}"

    return hashlib.md5(
        text.encode("utf-8")
    ).hexdigest()


# ==========================================================
# VALIDATOR
# ==========================================================

def validate_short_question(question: dict) -> bool:

    if not isinstance(question, dict):
        return False

    required = [
        "question",
        "answer",
        "explanation",
        "real_life_example",
        "memory_trick",
        "difficulty",
    ]

    for key in required:

        if key not in question:
            return False

        question[key] = str(
            question[key]
        ).strip()

        if not question[key]:
            return False

    question["type"] = "short"

    return True


# ==========================================================
# GENERATE FOR ONE TOPIC
# ==========================================================

def generate_short_topic(
    topic: dict,
    count: int,
):

    cache_key = short_cache_key(
        topic,
        count,
    )

    if exists(
        SHORT_CACHE_DIR,
        cache_key,
    ):
        print(
            f"✓ Short cache hit: "
            f"{topic['topic']}"
        )

        return load(
            SHORT_CACHE_DIR,
            cache_key,
        )

    prompt = build_short_prompt(
        topic["topic"],
        topic["points"],
        count,
    )

    schema = build_short_schema(count)

    response = generate(
        model=QUESTION_MODEL,
        prompt=prompt,
        temperature=0.1,
        top_p=0.8,
        num_predict=700,
        num_ctx=1024,
        num_thread=4,
        json_schema=schema,
    )

    try:
        data = json.loads(response)
    except Exception as e:
        print(
            "Short question JSON error:",
            e,
        )
        return []

    questions = data.get(
        "questions",
        [],
    )

    valid = []

    for question in questions:

        if validate_short_question(question):
            valid.append(question)

    print(
        f"Short questions: "
        f"{len(valid)}/{count}"
    )

    save(
        SHORT_CACHE_DIR,
        cache_key,
        valid,
    )

    return valid