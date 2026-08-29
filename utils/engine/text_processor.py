"""
text_processor.py
-----------------

Optimizes transcript text before sending it to the AI.

Features
--------
✓ Normalize whitespace
✓ Remove duplicate sentences
✓ Remove duplicate paragraphs
✓ Remove tiny paragraphs
✓ Rank paragraphs
✓ Compress transcript
✓ Return statistics

Author: Yashwanth AI Quiz Engine
"""

from __future__ import annotations

import re
from collections import Counter

# ---------------- CONFIG ---------------- #

MAX_CHARS = 6000
MIN_SENTENCE_LENGTH = 20
MIN_PARAGRAPH_LENGTH = 40


# ---------------- NORMALIZE ---------------- #

def normalize(text: str) -> str:
    """Normalize whitespace."""
    text = text.replace("\r", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ---------------- SPLIT ---------------- #

def split_paragraphs(text: str) -> list[str]:
    """Split transcript into paragraphs."""

    paragraphs = re.split(r"\n\s*\n", text)

    if len(paragraphs) <= 1:
        paragraphs = re.split(r'(?<=[.!?])\s+', text)

    return [p.strip() for p in paragraphs if p.strip()]


# ---------------- DUPLICATES ---------------- #

def remove_duplicate_paragraphs(paragraphs: list[str]) -> list[str]:

    seen = set()

    cleaned = []

    for p in paragraphs:

        key = p.lower()

        if key in seen:
            continue

        seen.add(key)

        cleaned.append(p)

    return cleaned


def remove_duplicate_sentences(paragraphs: list[str]) -> list[str]:

    result = []

    for para in paragraphs:

        sentences = re.split(r'(?<=[.!?])\s+', para)

        seen = set()

        unique = []

        for s in sentences:

            key = s.lower().strip()

            if key in seen:
                continue

            seen.add(key)

            unique.append(s)

        result.append(" ".join(unique))

    return result


# ---------------- FILTER ---------------- #

def filter_small(paragraphs: list[str]) -> list[str]:

    return [

        p

        for p in paragraphs

        if len(p) >= MIN_PARAGRAPH_LENGTH

    ]


# ---------------- SCORE ---------------- #

STOP_WORDS = {

    "the","is","a","an","and","or","to","of",

    "in","on","at","for","with","that",

    "this","it","as","are","be","by","from"

}


def score(paragraph: str):

    words = re.findall(r"\w+", paragraph.lower())

    words = [

        w

        for w in words

        if w not in STOP_WORDS

    ]

    if not words:

        return 0

    freq = Counter(words)

    return sum(freq.values())


# ---------------- RANK ---------------- #

def rank(paragraphs: list[str]):

    ranked = sorted(

        paragraphs,

        key=score,

        reverse=True

    )

    return ranked


# ---------------- BUILD ---------------- #

def compress(paragraphs: list[str]):
    """
    Compress paragraphs to MAX_CHARS.

    Handles very large transcript paragraphs safely.
    """

    output = []
    size = 0

    for p in paragraphs:

        remaining = MAX_CHARS - size

        if remaining <= 0:
            break

        # Paragraph fits completely
        if len(p) <= remaining:
            output.append(p)
            size += len(p)

        # Paragraph is too large: take only what fits
        else:
            chunk = p[:remaining].strip()

            if chunk:
                output.append(chunk)

            break

    return "\n\n".join(output)

# ---------------- MAIN ---------------- #

def process(text: str):

    try:

        original = len(text)

        text = normalize(text)

        paragraphs = split_paragraphs(text)

        paragraphs = remove_duplicate_paragraphs(paragraphs)

        paragraphs = remove_duplicate_sentences(paragraphs)

        paragraphs = filter_small(paragraphs)

        paragraphs = rank(paragraphs)

        optimized = compress(paragraphs)

        return {

            "success": True,

            "text": optimized,

            "original_length": original,

            "optimized_length": len(optimized),

            "paragraphs": len(paragraphs),

            "compression": round(

                len(optimized) / max(original, 1),

                2

            ),

            "error": None

        }

    except Exception as e:

        return {

            "success": False,

            "text": "",

            "original_length": 0,

            "optimized_length": 0,

            "paragraphs": 0,

            "compression": 0,

            "error": str(e)

        }