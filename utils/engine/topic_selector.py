"""
topic_selector.py

Uses ONE Ollama call to convert fast whole-video scanner
results into clean educational topics.
"""

from __future__ import annotations

import json
import re
import time

from .ollama_client import generate
from .config import (
    KNOWLEDGE_MODEL,
    MAX_TOPICS,
)




# ==========================================================
# BUILD COMPACT SCANNER CONTEXT
# ==========================================================

def build_topic_evidence(scan: dict) -> str:

    sections = scan.get("sections", [])

    lines = []

    for section in sections:

        number = section.get("section")

        words = section.get("words", [])[:6]
        phrases = section.get("phrases", [])[:6]

        lines.append(
            f"SECTION {number}\n"
            f"WORDS: {', '.join(words)}\n"
            f"PHRASES: {', '.join(phrases)}"
        )

    return "\n\n".join(lines)


# ==========================================================
# EXTRACT JSON
# ==========================================================

def extract_json(text: str):

    if not text:
        return None

    text = text.strip()

    # Remove markdown fences if model adds them.
    text = re.sub(
        r"^```(?:json)?",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"```$",
        "",
        text,
    )

    text = text.strip()

    try:
        return json.loads(text)

    except json.JSONDecodeError:
        pass

    # Try to recover JSON object from surrounding text.
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        return None

    try:
        return json.loads(
            text[start:end + 1]
        )

    except json.JSONDecodeError:
        return None


# ==========================================================
# VALIDATE TOPICS
# ==========================================================

def validate_topics(data) -> list[dict]:

    if not isinstance(data, dict):
        return []

    topics = data.get("topics")

    if not isinstance(topics, list):
        return []

    valid = []

    seen = set()

    for item in topics:

        if not isinstance(item, dict):
            continue

        topic = str(
            item.get("topic", "")
        ).strip()

        if not topic:
            continue

        if len(topic) > 80:
            continue

        key = topic.lower()

        if key in seen:
            continue

        seen.add(key)

        sections = item.get(
            "sections",
            []
        )

        if not isinstance(sections, list):
            sections = []

        clean_sections = []

        for section in sections:

            try:
                section = int(section)

                if section > 0:
                    clean_sections.append(section)

            except (TypeError, ValueError):
                continue

        valid.append({
            "topic": topic,
            "sections": clean_sections,
        })

    return valid[:MAX_TOPICS]


# ==========================================================
# SELECT MAJOR TOPICS
# ==========================================================

def select_major_topics(
    scan: dict,
) -> dict:

    start = time.perf_counter()

    if not scan.get("success"):

        return {
            "success": False,
            "topics": [],
            "time": 0,
            "error": "Topic scan failed.",
        }

    evidence = build_topic_evidence(
        scan
    )

    prompt = f"""
You are analyzing an educational video.

Below is compact evidence collected from different
sections across the ENTIRE video.

Your task is to identify the major educational topics
actually taught in the video.

IMPORTANT RULES:

1. Use ONLY the supplied section evidence.
2. Do NOT invent topics.
3. Merge duplicate or closely related concepts.
4. Prefer meaningful educational topic names.
5. Ignore greetings, filler words and broken words.
6. Cover the beginning, middle and end of the video.
7. Return at most {MAX_TOPICS} major topics.
8. Do not create vague topics such as:
   "Introduction", "General Information",
   "Task Assignment", or "Miscellaneous"
   unless they are genuinely educational concepts.
9. Topic names must be short and clear.
10. Return ONLY valid JSON.
11. No markdown.
12. No explanation outside JSON.

Required JSON format:

{{
  "topics": [
    {{
      "topic": "Variables",
      "sections": [1]
    }},
    {{
      "topic": "Data Types",
      "sections": [2]
    }}
  ]
}}

SECTION EVIDENCE:

{evidence}
"""

    try:
        
        
        raw = generate(
            model=KNOWLEDGE_MODEL,
            prompt=prompt,
            temperature=0.05,
            top_p=0.8,
            num_predict=350,
            num_ctx=2048,
            num_thread=4,
            json_mode=True,
        )

        

        data = extract_json(raw)

        if data is None:

            print("\n--- INVALID TOPIC JSON ---")
            print(raw)
            print("--- END RESPONSE ---\n")

            return {
                "success": False,
                "topics": [],
                "time": round(
                    time.perf_counter() - start,
                    2,
                ),
                "error": "Invalid topic JSON.",
            }

        topics = validate_topics(data)

        if not topics:

            return {
                "success": False,
                "topics": [],
                "time": round(
                    time.perf_counter() - start,
                    2,
                ),
                "error": "No valid topics returned.",
            }

        return {
            "success": True,
            "topics": topics,
            "count": len(topics),
            "time": round(
                time.perf_counter() - start,
                2,
            ),
            "error": None,
        }

    except Exception as e:

        return {
            "success": False,
            "topics": [],
            "time": round(
                time.perf_counter() - start,
                2,
            ),
            "error": str(e),
        }