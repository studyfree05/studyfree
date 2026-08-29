"""
topic_scanner.py

Fast whole-video topic candidate extraction.

IMPORTANT:
This does NOT call Ollama.

Purpose:
- scan the entire transcript
- find repeated meaningful terms
- preserve beginning/middle/end coverage
- produce compact evidence for the AI
"""

from __future__ import annotations

import re
from collections import Counter

from .chunker import chunk_text


# ==========================================================
# STOP WORDS
# ==========================================================

STOP_WORDS = {
    # English
    "the", "and", "that", "this", "with", "from",
    "have", "has", "had", "will", "would", "can",
    "could", "should", "into", "about", "your",
    "you", "our", "their", "they", "them", "then",
    "than", "when", "where", "what", "which", "who",
    "why", "how", "for", "are", "was", "were", "is",
    "am", "be", "been", "being", "to", "of", "in",
    "on", "at", "by", "as", "or", "if", "so",
    "we", "it", "a", "an",

    # Common lecture filler / transliterated English
    "okay", "ok", "basically", "actually",
    "example", "examples", "let", "lets",
    "say", "now", "next", "again", "fine",
    "right", "got", "understand",

    # Telugu lecture fillers
    "సో", "ఓకే", "అంటే", "మనకి", "మనం",
    "ఇప్పుడు", "కాబట్టి", "అదే", "విధంగా",
    "బేసిక్", "గా", "ఒక", "ఇది", "అది",
}


# ==========================================================
# TOKENIZE
# ==========================================================

def tokenize(text: str) -> list[str]:

    words = re.findall(
        r"[A-Za-z0-9_]+|[\u0C00-\u0C7F]+",
        text.lower(),
    )

    cleaned = []

    for word in words:

        word = word.strip("_")

        if len(word) < 3:
            continue

        if word in STOP_WORDS:
            continue

        if word.isdigit():
            continue

        cleaned.append(word)

    return cleaned


# ==========================================================
# PHRASES
# ==========================================================

def make_phrases(
    words: list[str],
    size: int,
) -> list[str]:

    if len(words) < size:
        return []

    return [
        " ".join(words[i:i + size])
        for i in range(
            len(words) - size + 1
        )
    ]


# ==========================================================
# SCAN ONE SECTION
# ==========================================================

def scan_section(
    text: str,
    top_words: int = 8,
    top_phrases: int = 6,
) -> dict:

    words = tokenize(text)

    word_counts = Counter(words)

    bigrams = Counter(
        make_phrases(words, 2)
    )

    return {
        "words": [
            word
            for word, _ in word_counts.most_common(
                top_words
            )
        ],

        "phrases": [
            phrase
            for phrase, _ in bigrams.most_common(
                top_phrases
            )
        ],
    }


# ==========================================================
# WHOLE VIDEO SCANNER
# ==========================================================

def scan_video_topics(
    text: str,
    max_sections: int = 12,
) -> dict:

    if not text or not text.strip():

        return {
            "success": False,
            "sections": [],
            "global_words": [],
            "global_phrases": [],
            "error": "Empty transcript.",
        }

    chunks = chunk_text(text)

    if not chunks:

        return {
            "success": False,
            "sections": [],
            "global_words": [],
            "global_phrases": [],
            "error": "Unable to split transcript.",
        }

    # ------------------------------------------------------
    # Select sections evenly across entire video
    # ------------------------------------------------------

    if len(chunks) <= max_sections:

        indexes = list(
            range(len(chunks))
        )

    else:

        indexes = []

        for i in range(max_sections):

            index = round(
                i
                * (len(chunks) - 1)
                / (max_sections - 1)
            )

            if index not in indexes:
                indexes.append(index)

    sections = []

    all_words = []
    all_phrases = []

    # ------------------------------------------------------
    # Scan selected sections
    # ------------------------------------------------------

    for section_number, index in enumerate(
        indexes,
        start=1,
    ):

        chunk = chunks[index]

        scan = scan_section(chunk)

        sections.append({
            "section": section_number,
            "chunk_index": index,
            "words": scan["words"],
            "phrases": scan["phrases"],
        })

        words = tokenize(chunk)

        all_words.extend(words)

        all_phrases.extend(
            make_phrases(words, 2)
        )

    # ------------------------------------------------------
    # Global ranking
    # ------------------------------------------------------

    global_words = Counter(
        all_words
    ).most_common(25)

    global_phrases = Counter(
        all_phrases
    ).most_common(25)

    return {
        "success": True,

        "total_chunks": len(chunks),

        "scanned_sections": len(sections),

        "sections": sections,

        "global_words": [
            word
            for word, _ in global_words
        ],

        "global_phrases": [
            phrase
            for phrase, _ in global_phrases
        ],

        "error": None,
    }