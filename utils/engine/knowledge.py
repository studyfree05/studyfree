"""
knowledge.py
"""

from __future__ import annotations

import json
import re
import time

from .cache import exists, load, save
from .config import KNOWLEDGE_CACHE, KNOWLEDGE_MODEL
from .ollama_client import generate

from .whole_video_sampler import (
    build_video_regions,
    build_combined_context,
)


def build_prompt(text: str) -> str:

    return f"""
TASK: CREATE STRUCTURED KNOWLEDGE FROM AN EDUCATIONAL VIDEO.

The source below contains balanced samples from different
regions of the SAME video.

IMPORTANT:
- Analyze ALL video regions.
- Do not focus only on the beginning.
- Identify the major educational concepts taught throughout
  the complete video.
- The lecture may be English, Telugu, Hindi, Tamil, Kannada,
  Malayalam, or mixed with English.
- Return the knowledge in English.
- Preserve technical terms accurately.
- Do NOT answer questions found inside the transcript.
- Do NOT continue the lecture.
- Do NOT invent information not supported by the source.
- Do NOT copy the lecturer's speaking style.

Return ONLY valid JSON.

Required JSON structure:

{{
  "title": "short lesson title",

  "summary": "summary of the complete lesson",

  "topics": [
    {{
      "topic": "major topic name",

      "points": [
        "important concept or fact",
        "important concept or fact"
      ]
    }}
  ]
}}

Rules:

- Cover concepts from the WHOLE video.
- Prefer 4 to 8 meaningful topics when the source supports them.
- Do not invent extra topics merely to reach a number.
- Use 2 to 5 important points per topic when available.
- Avoid duplicate topics.
- Avoid duplicate points.
- Keep points concise but educational.
- Summary must describe the overall lesson.
- Summary should be under 100 words.
- English output only.
- No markdown.
- No text outside the JSON object.

SOURCE VIDEO START

{text}

SOURCE VIDEO END

Return the JSON object only.
"""


def extract_json(text: str):

    text = text.strip()

    text = re.sub(r"```json", "", text, flags=re.I)
    text = re.sub(r"```", "", text)

    m = re.search(r"\{.*\}", text, re.S)

    if m:
        return m.group(0)

    return text


def parse_json(text):

    try:

        return json.loads(extract_json(text))

    except Exception:

        return None
    


# --------------------------------------------------------
# Knowledge Validation
# --------------------------------------------------------

def validate_knowledge(data: dict) -> bool:
    """
    Validate and clean generated knowledge.
    """

    if not isinstance(data, dict):
        return False

    if "title" not in data:
        return False

    if "summary" not in data:
        return False

    if "topics" not in data:
        return False

    if not isinstance(data["topics"], list):
        return False

    # Clean title and summary
    data["title"] = str(data["title"]).strip()
    data["summary"] = str(data["summary"]).strip()

    if not data["title"]:
        return False

    if not data["summary"]:
        return False

    cleaned_topics = []

    for topic in data["topics"]:

        if not isinstance(topic, dict):
            continue

        title = str(topic.get("topic", "")).strip()
        points = topic.get("points", [])

        if not title:
            continue

        if not isinstance(points, list):
            continue

        cleaned_points = []

        for point in points:

            point = str(point).strip()

            if len(point) < 5:
                continue

            cleaned_points.append(point)

        if cleaned_points:

            cleaned_topics.append({
                "topic": title,
                "points": cleaned_points,
            })

    data["topics"] = cleaned_topics

    return len(cleaned_topics) > 0


def validate(data):

    if not isinstance(data, dict):
        return False

    if "topics" not in data:
        return False

    if not isinstance(data["topics"], list):
        return False

    cleaned = []

    for topic in data["topics"]:

        if not isinstance(topic, dict):
            continue

        name = str(topic.get("topic", "")).strip()

        points = topic.get("points", [])

        if not name:
            continue

        if not isinstance(points, list):
            continue

        pts = []

        for p in points:

            p = str(p).strip()

            if len(p) > 3:
                pts.append(p)

        if pts:

            cleaned.append({

                "topic": name,

                "points": pts

            })

    data["topics"] = cleaned

    return len(cleaned) > 0


KNOWLEDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string"
        },
        "summary": {
            "type": "string"
        },
        "topics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string"
                    },
                    "points": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        }
                    }
                },
                "required": [
                    "topic",
                    "points"
                ]
            }
        }
    },
    "required": [
        "title",
        "summary",
        "topics"
    ]
}

# --------------------------------------------------------
# Knowledge Generator
# --------------------------------------------------------

def generate_knowledge(
    processed_text: str,
    use_cache: bool = True
):
    """
    Generate structured knowledge from processed transcript.
    """

    if not processed_text.strip():

        return {
            "success": False,
            "cached": False,
            "knowledge": None,
            "time": 0,
            "error": "Empty transcript."
        }
        
        
    

    # ---------------- Cache ---------------- #

    if use_cache and exists(KNOWLEDGE_CACHE, processed_text):

        cached = load(KNOWLEDGE_CACHE, processed_text)

        if cached:

            return {

                "success": True,

                "cached": True,

                "knowledge": cached,

                "time": 0,

                "error": None

            }

    # --------------------------------------------------------
    # Whole-video sampling
    # --------------------------------------------------------

    region_result = build_video_regions(
        processed_text,
        regions=5,
        chars_per_region=1200,
    )

    if not region_result.get(
        "success"
    ):

        return {
            "success": False,
            "cached": False,
            "knowledge": None,
            "time": 0,
            "error": region_result.get(
                "error",
                "Knowledge sampling failed.",
            ),
        }

    combined_context = build_combined_context(
        region_result
    )

    if not combined_context.strip():

        return {
            "success": False,
            "cached": False,
            "knowledge": None,
            "time": 0,
            "error": (
                "Knowledge context is empty."
            ),
        }

    prompt = build_prompt(
        combined_context
    )

    start = time.time()

    last_error = None

    # Retry once if the model returns malformed JSON
    for attempt in range(2):
        try:
            
            
            response = generate(
                model=KNOWLEDGE_MODEL,
                prompt=prompt,
                temperature=0.0,
                top_p=0.8,
                num_predict=900,
                num_ctx=8192,
                num_thread=4,
                json_schema=KNOWLEDGE_SCHEMA,
            )
            
            
            
            data = parse_json(response)

            if data is None:
                print("\n--- INVALID KNOWLEDGE JSON ---")
                print(response)
                print("--- END RESPONSE ---\n")

                raise ValueError("Invalid JSON returned.")
            
            
            
            if not validate_knowledge(data):
                print("\n--- KNOWLEDGE VALIDATION FAILED ---")
                print(json.dumps(data, indent=2, ensure_ascii=False))
                print("--- END KNOWLEDGE ---\n")

                raise ValueError("Knowledge validation failed.")
            
            
            save(

                KNOWLEDGE_CACHE,

                processed_text,

                data

            )

            return {

                "success": True,

                "cached": False,

                "knowledge": data,

                "time": round(

                    time.time() - start,

                    2

                ),

                "error": None

            }

        except Exception as e:

            last_error = str(e)

            time.sleep(1)

    return {

        "success": False,

        "cached": False,

        "knowledge": None,

        "time": round(

            time.time() - start,

            2

        ),

        "error": last_error

    }


# --------------------------------------------------------
# CLI TEST
# --------------------------------------------------------

if __name__ == "__main__":

    sample = """
Python variables store values.

Variables can contain integers,
strings and floating-point numbers.

Functions are reusable blocks of code.

Loops execute statements repeatedly.

Conditional statements control program flow.
"""

    result = generate_knowledge(
        sample,
        use_cache=False
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        )
    )
