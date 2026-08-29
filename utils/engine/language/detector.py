"""
StudyFree Language Detector
---------------------------

Fast Unicode-based language/script detector.

Supports:
- English
- Telugu
- Hindi / Devanagari
- Tamil
- Kannada
- Malayalam
- mixed-language transcripts

No AI calls.
"""

from __future__ import annotations

import re


# ==========================================================
# UNICODE SCRIPT RANGES
# ==========================================================

SCRIPT_PATTERNS = {

    # Telugu Unicode block
    "telugu": re.compile(
        r"[\u0C00-\u0C7F]"
    ),

    # Devanagari Unicode block
    # Used for Hindi detection in StudyFree.
    "hindi": re.compile(
        r"[\u0900-\u097F]"
    ),

    # Tamil Unicode block
    "tamil": re.compile(
        r"[\u0B80-\u0BFF]"
    ),

    # Kannada Unicode block
    "kannada": re.compile(
        r"[\u0C80-\u0CFF]"
    ),

    # Malayalam Unicode block
    "malayalam": re.compile(
        r"[\u0D00-\u0D7F]"
    ),

}


# ==========================================================
# DETECTOR
# ==========================================================

def detect_language(
    text: str,
) -> dict:
    """
    Detect the dominant script/language in transcript text.

    Returns:

    {
        "language": str,
        "counts": {
            "telugu": int,
            "hindi": int,
            "tamil": int,
            "kannada": int,
            "malayalam": int,
            "english": int,
        }
    }

    English count represents Latin alphabet characters.

    For mixed-language educational transcripts, the
    dominant script is returned while all script counts
    remain available.
    """

    text = str(
        text or ""
    )

    counts = {}

    # ------------------------------------------------------
    # INDIAN LANGUAGE SCRIPTS
    # ------------------------------------------------------

    for (
        language,
        pattern,
    ) in SCRIPT_PATTERNS.items():

        counts[language] = len(
            pattern.findall(
                text
            )
        )

    # ------------------------------------------------------
    # ENGLISH / LATIN
    # ------------------------------------------------------

    counts["english"] = len(
        re.findall(
            r"[A-Za-z]",
            text,
        )
    )

    # ------------------------------------------------------
    # EMPTY / UNRECOGNIZED TEXT
    # ------------------------------------------------------

    if not any(
        counts.values()
    ):

        return {
            "language": "unknown",
            "counts": counts,
        }

    # ------------------------------------------------------
    # DOMINANT SCRIPT
    # ------------------------------------------------------

    language = max(
        counts,
        key=counts.get,
    )

    return {
        "language": language,
        "counts": counts,
    }