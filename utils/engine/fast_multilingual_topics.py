"""
fast_multilingual_topics.py

Fast multilingual educational topic extraction.

Designed for:
- English
- Hindi
- Telugu
- mixed-language transcripts

Uses:
- fast whole-video sampling
- ONE small Ollama call
"""

from __future__ import annotations

import json
import re
import time

from .chunker import chunk_text, select_chunks
from .ollama_client import generate
from .config import KNOWLEDGE_MODEL


MAX_TOPICS = 10


# ==========================================================
# BUILD SMALL WHOLE-VIDEO EVIDENCE
# ==========================================================

def build_multilingual_evidence(
    text: str,
    max_sections: int = 10,
    chars_per_section: int = 280,
) -> str:

    chunks = chunk_text(text)

    selected = select_chunks(
        chunks,
        max_chunks=max_sections,
    )

    evidence = []

    for index, chunk in enumerate(
        selected,
        start=1,
    ):

        if not chunk:
            continue

        # Take text from the middle of each selected chunk.
        # This avoids repeatedly capturing greetings/intros.
        if len(chunk) <= chars_per_section:

            sample = chunk.strip()

        else:

            start = max(
                0,
                (len(chunk) // 2)
                - (chars_per_section // 2),
            )

            sample = chunk[
                start:
                start + chars_per_section
            ].strip()

        if sample:

            evidence.append(
                f"S{index}: {sample}"
            )

    return "\n".join(evidence)


# ==========================================================
# JSON RECOVERY
# ==========================================================

def extract_json(raw: str):

    if not raw:
        return None

    raw = raw.strip()

    raw = re.sub(
        r"^```(?:json)?",
        "",
        raw,
        flags=re.IGNORECASE,
    )

    raw = re.sub(
        r"```$",
        "",
        raw,
    )

    raw = raw.strip()

    try:
        return json.loads(raw)

    except json.JSONDecodeError:
        pass

    start = raw.find("{")
    end = raw.rfind("}")

    if (
        start == -1
        or end == -1
        or end <= start
    ):
        return None

    try:
        return json.loads(
            raw[start:end + 1]
        )

    except json.JSONDecodeError:
        return None


# ==========================================================
# VALIDATE
# ==========================================================

def validate_topics(data) -> list[str]:

    if not isinstance(data, dict):
        return []

    topics = data.get("topics")

    if not isinstance(topics, list):
        return []

    valid = []
    seen = set()

    for item in topics:

        if not isinstance(item, str):
            continue

        item = item.strip()

        if not item:
            continue

        if len(item) > 60:
            continue

        key = item.casefold()

        if key in seen:
            continue

        seen.add(key)
        valid.append(item)

        if len(valid) >= MAX_TOPICS:
            break

    return valid


# ==========================================================
# EXTRACT TOPICS
# ==========================================================

def extract_multilingual_topics(
    text: str,
) -> dict:

    start_time = time.perf_counter()

    if not text or not text.strip():

        return {
            "success": False,
            "topics": [],
            "count": 0,
            "evidence_chars": 0,
            "time": 0,
            "error": "Empty transcript.",
        }

    evidence = build_multilingual_evidence(
        text,
        max_sections=10,
        chars_per_section=280,
    )

    prompt = f"""
Identify the main EDUCATIONAL TOPICS taught in these
samples from one lesson.

The transcript may mix Telugu, Hindi and English.

Return topic names in clear ENGLISH.

Rules:
- Use only concepts actually present.
- Ignore speech filler and conversational phrases.
- Merge related concepts.
- Cover the whole lesson.
- Maximum {MAX_TOPICS} topics.
- Topic names must be short.
- Return JSON only.

Format:
{{"topics":["Variables","Data Types","Operators"]}}

Samples:
{evidence}
""".strip()

    try:

        raw = generate(
            model=KNOWLEDGE_MODEL,
            prompt=prompt,

            # Speed-focused settings
            temperature=0.0,
            top_p=0.7,

            # Topic names need very little output.
            num_predict=140,

            # Prompt is intentionally compact.
            num_ctx=1536,

            num_thread=4,
            json_mode=True,
        )

        data = extract_json(raw)

        if data is None:

            return {
                "success": False,
                "topics": [],
                "count": 0,
                "evidence_chars": len(evidence),
                "time": round(
                    time.perf_counter()
                    - start_time,
                    2,
                ),
                "error": "Invalid topic JSON.",
            }

        topics = validate_topics(data)

        if not topics:

            return {
                "success": False,
                "topics": [],
                "count": 0,
                "evidence_chars": len(evidence),
                "time": round(
                    time.perf_counter()
                    - start_time,
                    2,
                ),
                "error": "No valid topics.",
            }

        return {
            "success": True,
            "topics": topics,
            "count": len(topics),
            "evidence_chars": len(evidence),
            "time": round(
                time.perf_counter()
                - start_time,
                2,
            ),
            "error": None,
        }

    except Exception as e:

        return {
            "success": False,
            "topics": [],
            "count": 0,
            "evidence_chars": len(evidence),
            "time": round(
                time.perf_counter()
                - start_time,
                2,
            ),
            "error": str(e),
        }