"""
cleaner.py
----------

Cleans raw YouTube transcripts before concept extraction.

Responsibilities
----------------
1. Normalize text
2. Remove greetings & promotional phrases
3. Skip intro section
4. Return standardized result
"""

from __future__ import annotations

import re

from utils.engine.noise_patterns import NOISE_PATTERNS


# Number of initial chunks to skip
INTRO_SKIP_CHUNKS = 0

# Words per chunk
CHUNK_SIZE = 180


def _normalize(text: str) -> str:
    """
    Normalize whitespace.
    """

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def _remove_noise(text: str) -> str:
    """
    Remove greetings and promotional phrases.
    """

    for pattern in NOISE_PATTERNS:
        text = re.sub(
            pattern,
            "",
            text,
            flags=re.IGNORECASE,
        )

    return text


def _skip_intro(text: str) -> str:
    """
    Skip the first few chunks where creators usually
    introduce the video or ask viewers to like/share/subscribe.
    """

    words = text.split()

    skip_words = INTRO_SKIP_CHUNKS * CHUNK_SIZE

    if len(words) <= skip_words:
        return text

    return " ".join(words[skip_words:])


def clean_transcript(text: str) -> dict:
    """
    Clean transcript.

    Returns
    -------
    {
        "success": bool,
        "text": str,
        "original_length": int,
        "cleaned_length": int
    }
    """

    if not text.strip():
        return {
            "success": False,
            "text": "",
            "original_length": 0,
            "cleaned_length": 0,
        }

    original_length = len(text)

    cleaned = _normalize(text)

    cleaned = _remove_noise(cleaned)

    cleaned = _skip_intro(cleaned)

    cleaned = _normalize(cleaned)

    return {
        "success": True,
        "text": cleaned,
        "original_length": original_length,
        "cleaned_length": len(cleaned),
    }