"""
question_generator.py (V2)

Generates quiz questions topic-by-topic for better speed and reliability.
"""

from __future__ import annotations

import hashlib
import json
import re

from .cache import exists, load, save
from .config import QUESTION_MODEL
from .ollama_client import generate

TOPIC_CACHE_DIR = "cache/topic_questions"
QUESTION_PROMPT_VERSION = "v6_exact_count"
def build_question_schema(count: int) -> dict:
    """
    Build JSON schema requiring exactly `count` questions.
    """

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
                        "options": {
                            "type": "array",
                            "minItems": 4,
                            "maxItems": 4,
                            "items": {
                                "type": "string"
                            }
                        },
                        "answer": {
                            "type": "string"
                        },
                        "difficulty": {
                            "type": "string",
                            "enum": [
                                "easy",
                                "medium",
                                "hard"
                            ]
                        },
                        "explanation": {
                            "type": "string"
                        }
                    },
                    "required": [
                        "question",
                        "options",
                        "answer",
                        "difficulty",
                        "explanation"
                    ]
                }
            }
        },
        "required": ["questions"]
    }

def build_prompt(
    topic_name: str,
    points: list[str],
    count: int = 2,
) -> str:

    bullets = "\n".join(
        f"FACT {i}: {point}"
        for i, point in enumerate(points, start=1)
    )

    return f"""
You create accurate multiple-choice questions from supplied source facts.

Generate EXACTLY {count} questions.

SOURCE TOPIC:
{topic_name}

SOURCE FACTS:
{bullets}

STRICT RULES:

1. Every question MUST be answerable directly from SOURCE FACTS.
2. Use ONLY SOURCE FACTS.
3. Do NOT add outside knowledge.
4. Do NOT introduce names, formulas, libraries, examples, dates,
   definitions, commands, people, places, or concepts that are not
   present in SOURCE FACTS.
5. The correct answer MUST be directly supported by SOURCE FACTS.
6. Distractors may be simple incorrect alternatives, but must not make
   the question ambiguous.
7. Exactly ONE option must be correct.
8. Generate exactly 4 options.
9. Do not create trick questions.
10. Do not create questions when the supplied facts do not support them.
11. Keep questions clear and suitable for a student studying this topic.
12. The answer field MUST contain the complete correct option text.
13. Never return A, B, C, or D as the answer.
14. Return JSON only.
15. Do not use markdown.

Return exactly:

{{
  "questions": [
    {{
      "question": "",
      "options": ["", "", "", ""],
      "answer": "",
      "difficulty": "easy",
      "explanation": ""
    }}
  ]
}}
"""

def extract_json(text: str) -> str:
    """
    Extract the first JSON object from the model response.
    """

    text = text.strip()

    # Response is already JSON
    if text.startswith("{") and text.endswith("}"):
        return text

    # Find first JSON object
    match = re.search(r"\{.*\}", text, re.DOTALL)

    if match:
        return match.group(0)

    raise ValueError("No JSON found in response")

def parse_json(text: str):
    try:
        json_text = extract_json(text)
        return json.loads(json_text)
    except Exception as e:
        print("JSON Parse Error:", e)
        return None
    


def validate_question(question: dict) -> bool:
    """
    Validate and normalize a single MCQ.
    """

    if not isinstance(question, dict):
        print("Rejected: not a dict")
        return False

    required = [
        "question",
        "options",
        "answer",
        "difficulty",
        "explanation",
    ]

    for key in required:
        if key not in question:
            print(f"Rejected: missing key '{key}'")
            return False

    if not isinstance(question["options"], list):
        print("Rejected: options is not a list")
        return False

    if len(question["options"]) != 4:
        print("Rejected: options length =", len(question["options"]))
        return False

    # Normalize option strings
    question["options"] = [str(opt).strip() for opt in question["options"]]

    # Normalize answer
    answer = str(question["answer"]).strip()

    # Convert A/B/C/D -> actual option text
    if answer.upper() in ["A", "B", "C", "D"]:
        index = ord(answer.upper()) - ord("A")
        question["answer"] = question["options"][index]
    else:
        question["answer"] = answer

    # Final validation
    if question["answer"] not in question["options"]:
        print("Rejected: answer not found in options")
        print("Answer :", repr(question["answer"]))
        print("Options:", [repr(x) for x in question["options"]])
        return False

    return True


def topic_cache_key(topic: dict, questions_per_topic: int) -> str:
    """
    Create a unique cache key for a topic.
    """
    text = QUESTION_PROMPT_VERSION
    text += "\n" + topic["topic"]
    text += "\n" + "\n".join(topic["points"])
    text += f"\n{questions_per_topic}"

    return hashlib.md5(text.encode("utf-8")).hexdigest()


def generate_topic(topic: dict, questions_per_topic: int = 2):
    """
    Generate questions for one topic.
    """
    
    cache_key = topic_cache_key(topic, questions_per_topic)

    if exists(TOPIC_CACHE_DIR, cache_key):
        print(f"✓ Cache hit: {topic['topic']}")
        return load(TOPIC_CACHE_DIR, cache_key)

    prompt = build_prompt(
        topic["topic"],
        topic["points"],
        questions_per_topic,
    )
    
    question_schema = build_question_schema(
        questions_per_topic
    )
        

    response = generate(
        
        model=QUESTION_MODEL,
        prompt=prompt,
        temperature=0.1,
        top_p=0.8,
        num_predict=400,
        num_ctx=768,
        num_thread=4,
        json_schema=question_schema,
    )
    

    data = parse_json(response)
    

    if data is None:
        return []

    questions = data.get("questions", [])
    print(
        f"Model returned {len(questions)} questions "
        f"for {topic['topic']}"
    )
    

    valid = []
    
    for q in questions:
        if validate_question(q):
            valid.append(q)
        

       

        
            
    save(TOPIC_CACHE_DIR, cache_key, valid)
    print(
        f"Valid questions: {len(valid)}/"
        f"{questions_per_topic}"
    )
    return valid
    

def generate_questions(knowledge, questions_per_topic=2):
    """
    Generate quiz questions for all topics.
    """

    all_questions = []

    topics = knowledge.get("topics", [])

    for topic in topics:

        print(f"Generating questions for: {topic['topic']}")
        

        questions = generate_topic(
            topic,
            questions_per_topic
        )

        all_questions.extend(questions)

    return {
        "success": True,
        "questions": all_questions,
        "count": len(all_questions)
    }
    
    