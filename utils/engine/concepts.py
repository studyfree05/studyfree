"""
concepts.py
-----------

Extract educational concepts from cleaned transcripts using Gemini.

Responsibilities
----------------
1. Split large transcripts into manageable chunks.
2. Extract educational concepts from each chunk.
3. Merge duplicate concepts.
4. Return a standardized result.
"""

from __future__ import annotations

import json
import os

import google.generativeai as genai


# ======================================================
# CONFIG
# ======================================================

MODEL_NAME = "gemini-2.5-flash"

CHUNK_SIZE = 2500
OVERLAP = 300


# ======================================================
# GEMINI
# ======================================================

def configure(api_key: str) -> None:
    """
    Configure Gemini API.
    """

    genai.configure(api_key=api_key)


# ======================================================
# CHUNKING
# ======================================================

def chunk_text(text: str) -> list[str]:
    """
    Split transcript into overlapping chunks.
    """

    words = text.split()

    chunks = []

    step = CHUNK_SIZE - OVERLAP

    for i in range(0, len(words), step):

        chunk = words[i:i + CHUNK_SIZE]

        if chunk:
            chunks.append(" ".join(chunk))

    return chunks


# ======================================================
# MERGE
# ======================================================

def merge_concepts(concepts: list[dict]) -> list[dict]:
    """
    Merge duplicate concepts.
    """

    merged = {}

    for item in concepts:

        name = item.get("concept", "").strip()

        if not name:
            continue

        key = name.lower()

        keywords = item.get("keywords", [])

        if key not in merged:

            merged[key] = {
                "concept": name,
                "keywords": set(keywords),
            }

        else:

            merged[key]["keywords"].update(keywords)

    result = []

    for value in merged.values():

        result.append({
            "concept": value["concept"],
            "keywords": sorted(value["keywords"])
        })

    result.sort(key=lambda x: x["concept"])

    return result


# ======================================================
# EXTRACTION
# ======================================================

def extract_concepts(text: str) -> dict:
    """
    Extract concepts from transcript.

    Returns
    -------
    {
        "success": bool,
        "concepts": list,
        "error": str | None
    }
    """

    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:

        return {
            "success": False,
            "concepts": [],
            "error": "GOOGLE_API_KEY not found."
        }

    configure(api_key)

    model = genai.GenerativeModel(MODEL_NAME)

    chunks = chunk_text(text)

    all_concepts = []

    try:

        for chunk in chunks:

            prompt = f"""
You are an expert educator.

Read the transcript carefully.

Extract ONLY educational concepts.

Ignore:
- Greetings
- Promotions
- Like/Share/Subscribe
- Personal stories
- Advertisements

Return ONLY valid JSON.

Example:

[
    {{
        "concept": "Variables",
        "keywords": [
            "variable",
            "memory",
            "container"
        ]
    }},
    {{
        "concept": "Data Types",
        "keywords": [
            "int",
            "float",
            "string",
            "boolean"
        ]
    }}
]

Transcript:

{chunk}
"""

            response = model.generate_content(prompt)

            text_response = response.text.strip()

            if text_response.startswith("```"):

                text_response = text_response.replace("```json", "")
                text_response = text_response.replace("```", "")
                text_response = text_response.strip()

            concepts = json.loads(text_response)

            all_concepts.extend(concepts)

        merged = merge_concepts(all_concepts)

        return {
            "success": True,
            "concepts": merged,
            "error": None,
        }

    except Exception as e:

        return {
            "success": False,
            "concepts": [],
            "error": str(e),
        }