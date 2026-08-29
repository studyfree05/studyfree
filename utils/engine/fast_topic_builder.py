"""
fast_topic_builder.py

Builds major educational topic candidates from the
whole-video scanner WITHOUT calling Ollama.

Goals:
- very fast
- whole-video coverage
- remove filler/noisy phrases
- merge related phrases
- keep section evidence
"""

from __future__ import annotations

import re
from collections import defaultdict


# ==========================================================
# SETTINGS
# ==========================================================

MAX_TOPICS = 12

GENERIC_WORDS = {
    "today",
    "learn",
    "learning",
    "concept",
    "important",
    "example",
    "examples",
    "basic",
    "basics",
    "python",
    "programming",
}


# ==========================================================
# CLEAN PHRASE
# ==========================================================

def clean_phrase(phrase: str) -> str:

    phrase = str(phrase).lower().strip()

    words = re.findall(
        r"[a-z0-9_]+|[\u0C00-\u0C7F]+",
        phrase,
    )

    words = [
        word
        for word in words
        if word not in GENERIC_WORDS
        and len(word) >= 3
    ]

    return " ".join(words).strip()

def contains_pattern(
    phrase: str,
    pattern: str,
) -> bool:

    phrase_words = phrase.split()
    pattern_words = pattern.split()

    if len(pattern_words) == 1:
        return pattern in phrase_words

    return pattern in phrase

# ==========================================================
# NORMALIZE RELATED TOPICS
# ==========================================================

def normalize_topic(phrase: str) -> str:
    """
    Convert scanner phrases into clean topic names.
    """

    phrase = clean_phrase(phrase)

    if not phrase:
        return ""

    rules = [
        (
            (
                "data type",
                "data types",
                "data storage",
            ),
            "Data Types",
        ),
        (
            (
                "input output",
                "input/output",
                "output function",
                "output functions",
            ),
            "Input and Output",
        ),
        (
            (
                "variable",
                "variables",
            ),
            "Variables",
        ),
        (
            (
                "arithmetic operator",
                "arithmetic operators",
                "comparison operator",
                "comparison operators",
                "operator",
                "operators",
            ),
            "Operators",
        ),
        (
            (
                "conditional statement",
                "conditional statements",
                "conditional",
            ),
            "Conditional Statements",
        ),
        (
            (
                "for loop",
                "for loops",
                "while loop",
                "while loops",
                "loop",
                "loops",
            ),
            "Loops",
        ),
        (
            (
                "function",
                "functions",
            ),
            "Functions",
        ),
        (
            (
                "dictionary",
                "dictionaries",
            ),
            "Dictionaries",
        ),
        (
            (
                "list",
                "lists",
            ),
            "Lists",
        ),
        (
            (
                "tuple",
                "tuples",
            ),
            "Tuples",
        ),
        (
            (
                "file handling",
            ),
            "File Handling",
        ),
        (
            (
                "exception",
                "exceptions",
                "exception handling",
            ),
            "Exception Handling",
        ),
        (
            (
                "class",
                "classes",
            ),
            "Classes",
        ),
        (
            (
                "object",
                "objects",
            ),
            "Objects",
        ),
        (
            (
                "set",
                "sets",
            ),
            "Sets",
        ),
    ]

    # Match known concepts.
    for patterns, topic in rules:

        for pattern in patterns:

            if contains_pattern(
                phrase,
                pattern,
            ):
                return topic

    # Generic fallback.
    # Keeps this engine usable for Physics, Chemistry,
    # Maths, Biology and other educational subjects.
    words = phrase.split()

    if not words:
        return ""

    return " ".join(
        word.capitalize()
        for word in words[:4]
    )

# ==========================================================
# BUILD TOPICS
# ==========================================================

def build_fast_topics(
    scan: dict,
    max_topics: int = MAX_TOPICS,
) -> dict:

    if not scan.get("success"):

        return {
            "success": False,
            "topics": [],
            "count": 0,
            "error": "Topic scan failed.",
        }

    sections = scan.get(
        "sections",
        [],
    )

    if not sections:

        return {
            "success": False,
            "topics": [],
            "count": 0,
            "error": "No scanned sections.",
        }

    # topic -> section numbers
    topic_sections = defaultdict(set)

    # topic -> score
    topic_scores = defaultdict(float)

    # ------------------------------------------------------
    # Read every sampled video section
    # ------------------------------------------------------

    for section in sections:

        section_number = section.get(
            "section"
        )

        phrases = section.get(
            "phrases",
            [],
        )

        # Earlier phrases from the scanner are stronger.
        for rank, phrase in enumerate(
            phrases,
            start=1,
        ):

            topic = normalize_topic(
                phrase
            )

            if not topic:
                continue

            # Reject obvious weak fallback topics.
            if len(topic) < 3:
                continue
            
            # Reject weak generic one-word topics.
            WEAK_TOPICS = {
                "Data",
                "Statements",
                "Concept",
                "Concepts",
                "Information",
                "Example",
                "Examples",
            }

            if topic in WEAK_TOPICS:
                continue
            topic_sections[topic].add(
                    section_number
                     )
            # Rank 1 gets highest score.
            topic_scores[topic] += (
                7 - min(rank, 6)
                )
                                
               
                           

                            


                            
                        
    # ------------------------------------------------------
    # Reward concepts appearing in multiple sections
    # ------------------------------------------------------

    candidates = []

    for topic, sections_found in topic_sections.items():

        coverage_bonus = (
            len(sections_found) * 3
        )

        score = (
            topic_scores[topic]
            + coverage_bonus
        )

        candidates.append({
            "topic": topic,
            "sections": sorted(
                sections_found
            ),
            "score": score,
        })

    # ------------------------------------------------------
    # Sort by importance
    # ------------------------------------------------------

    candidates.sort(
        key=lambda item: (
            item["score"],
            len(item["sections"]),
        ),
        reverse=True,
    )

    # ------------------------------------------------------
    # Preserve whole-video coverage
    # ------------------------------------------------------

    selected = []
    selected_names = set()

    # First pass:
    # try to represent different video sections.
    covered_sections = set()

    for candidate in candidates:

        new_sections = (
            set(candidate["sections"])
            - covered_sections
        )

        if not new_sections:
            continue

        selected.append(candidate)

        selected_names.add(
            candidate["topic"]
        )

        covered_sections.update(
            candidate["sections"]
        )

        if len(selected) >= max_topics:
            break

    # Second pass:
    # fill remaining slots by importance.
    if len(selected) < max_topics:

        for candidate in candidates:

            if (
                candidate["topic"]
                in selected_names
            ):
                continue

            selected.append(candidate)

            selected_names.add(
                candidate["topic"]
            )

            if len(selected) >= max_topics:
                break

    # Remove internal scoring before returning.
    topics = [
        {
            "topic": item["topic"],
            "sections": item["sections"],
        }
        for item in selected
    ]

    return {
        "success": bool(topics),
        "topics": topics,
        "count": len(topics),
        "error": (
            None
            if topics
            else "No topic candidates found."
        ),
    }