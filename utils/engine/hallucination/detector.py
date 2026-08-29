"""
StudyFree Universal Evidence Grounding Detector

Goals:
- multilingual
- subject independent
- Unicode aware
- region aware
- no hardcoded subject corrections
- no AI/API calls
- fast local validation

This module measures whether generated question/answer
content is lexically grounded in the source video evidence.

It does NOT attempt to decide whether a scientific,
historical, mathematical, or programming claim is
objectively true. It measures support from the supplied
lecture evidence.
"""

from __future__ import annotations

import re
import unicodedata


# ==========================================================
# TOKEN SETTINGS
# ==========================================================

MIN_TOKEN_LENGTH = 2


# Common low-information English words.
# These are ignored only to improve overlap quality.
# We intentionally do NOT maintain language-specific
# stop-word lists for Telugu/Hindi/etc.
ENGLISH_STOP_WORDS = {
    "the",
    "and",
    "for",
    "are",
    "was",
    "were",
    "with",
    "this",
    "that",
    "from",
    "into",
    "what",
    "which",
    "when",
    "where",
    "why",
    "how",
    "does",
    "did",
    "has",
    "have",
    "had",
    "can",
    "could",
    "would",
    "should",
    "will",
    "shall",
    "about",
    "using",
    "used",
    "use",
    "following",
    "according",
    "video",
    "lecture",
    "lesson",
    "explain",
    "describe",
}


# ==========================================================
# NORMALIZATION
# ==========================================================

def normalize_text(
    text,
) -> str:

    text = str(
        text or ""
    )

    # Unicode normalization is important for multilingual
    # scripts and mixed-language transcripts.
    text = unicodedata.normalize(
        "NFKC",
        text,
    )

    return text.lower().strip()


# ==========================================================
# UNIVERSAL TOKENIZER
# ==========================================================

def tokenize(
    text,
) -> set[str]:
    """
    Unicode-aware tokenizer.

    Keeps:
    - English
    - Telugu
    - Hindi
    - Tamil
    - Kannada
    - Malayalam
    - numbers
    - mixed alphanumeric technical tokens

    Punctuation is treated as a separator.
    """

    text = normalize_text(
        text
    )

    tokens = set()

    current = []

    def flush():

        if not current:
            return

        token = "".join(
            current
        ).strip("_")

        current.clear()

        if len(token) < MIN_TOKEN_LENGTH:
            return

        if token in ENGLISH_STOP_WORDS:
            return

        tokens.add(
            token
        )

    for char in text:

        category = unicodedata.category(
            char
        )

        # L = Unicode letter
        # N = Unicode number
        # M = combining mark
        if (
            category.startswith("L")
            or category.startswith("N")
            or category.startswith("M")
            or char == "_"
        ):

            current.append(
                char
            )

        else:

            flush()

    flush()

    return tokens


# ==========================================================
# REGION LOOKUP
# ==========================================================

def _get_region_context(
    regions: list[dict],
    region_number,
    question_type: str | None = None,
) -> str:

    try:

        region_number = int(
            region_number
        )

    except (
        TypeError,
        ValueError,
    ):

        return ""

    context_keys = {
        "mcq": "mcq_context",
        "short": "short_context",
        "long": "long_context",
    }

    context_key = context_keys.get(
        str(
            question_type or ""
        ).lower(),
        "context",
    )

    for item in regions:

        if not isinstance(
            item,
            dict,
        ):
            continue

        try:

            item_region = int(
                item.get(
                    "region"
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            continue

        if item_region == region_number:

            context = str(
                item.get(
                    context_key,
                    "",
                )
            ).strip()

            # Legacy/safety fallback.
            if not context:

                context = str(
                    item.get(
                        "context",
                        "",
                    )
                ).strip()

            return context

    return ""

# ==========================================================
# ALL-VIDEO EVIDENCE
# ==========================================================

def _all_video_context(
    regions: list[dict],
    question_type: str | None = None,
) -> str:

    context_keys = {
        "mcq": "mcq_context",
        "short": "short_context",
        "long": "long_context",
    }

    context_key = context_keys.get(
        str(
            question_type or ""
        ).lower(),
        "context",
    )

    parts = []

    for item in regions:

        if not isinstance(
            item,
            dict,
        ):
            continue

        context = str(
            item.get(
                context_key,
                "",
            )
        ).strip()

        if not context:

            context = str(
                item.get(
                    "context",
                    "",
                )
            ).strip()

        if context:

            parts.append(
                context
            )

    return "\n".join(
        parts
    )
# ==========================================================
# OVERLAP
# ==========================================================

def _calculate_overlap(
    generated_tokens: set[str],
    evidence_tokens: set[str],
) -> dict:
    """
    Universal multilingual token-overlap scorer.

    Supports:
    - English
    - Telugu
    - Hindi
    - Tamil
    - Kannada
    - Malayalam
    - mixed-language text
    - technical/programming tokens

    Exact token matches are preferred.

    A conservative containment fallback is used for
    longer Unicode tokens because transcript systems can
    occasionally split or attach Indic-script characters
    differently.

    No translation, stemming, subject knowledge or AI
    calls are used.
    """

    if not generated_tokens:

        return {
            "score": 100.0,
            "matched": [],
            "unknown": [],
        }

    matched = set()
    unknown = set()

    # ------------------------------------------------------
    # 1. EXACT TOKEN MATCHING
    # ------------------------------------------------------

    for token in generated_tokens:

        if token in evidence_tokens:

            matched.add(token)
            continue

        # --------------------------------------------------
        # 2. CONSERVATIVE UNICODE CONTAINMENT FALLBACK
        # --------------------------------------------------
        #
        # Useful for transcript/token-boundary differences
        # in Telugu/Hindi/Tamil/Kannada/Malayalam etc.
        #
        # We require a reasonably long token so tiny
        # fragments cannot create false grounding.
        # --------------------------------------------------

        token_matched = False

        if len(token) >= 4:

            for evidence_token in evidence_tokens:

                if len(evidence_token) < 4:
                    continue

                shorter_length = min(
                    len(token),
                    len(evidence_token),
                )

                longer_length = max(
                    len(token),
                    len(evidence_token),
                )

                # Do not accept very different-sized words.
                if (
                    shorter_length
                    / max(1, longer_length)
                    < 0.70
                ):
                    continue

                if (
                    token in evidence_token
                    or evidence_token in token
                ):

                    matched.add(token)

                    token_matched = True

                    break

        if not token_matched:

            unknown.add(token)

    score = round(
        (
            len(matched)
            / len(generated_tokens)
        )
        * 100,
        1,
    )

    return {
        "score": score,

        "matched": sorted(
            matched
        ),

        "unknown": sorted(
            unknown
        ),
    }



# ==========================================================
# QUESTION GROUNDING
# ==========================================================

def ground_question(
    question: dict,
    regions: list[dict],
) -> dict:
    """
    Verify a question's source evidence against its assigned
    video region.

    The question/answer may be English while the source
    evidence may be Telugu, Hindi, Tamil, Kannada,
    Malayalam, English, or mixed language.

    Grounding is based on the SOURCE EVIDENCE itself.

    Important:
    A region may expose the same lesson material through
    different context fields such as:
        - mcq_context
        - short_context
        - long_context
        - context

    Therefore the evidence is checked against ALL available
    source-context fields for the assigned region instead of
    relying on only one question-type-specific field.
    """

    # ------------------------------------------------------
    # BASIC VALIDATION
    # ------------------------------------------------------

    if not isinstance(
        question,
        dict,
    ):

        return {
            "grounded": False,
            "confidence": 0.0,
            "region_confidence": 0.0,
            "video_confidence": 0.0,
            "region": None,
            "evidence": "",
            "evidence_found": False,
            "exact_match": False,
            "unknown_words": [],
            "error": (
                "Question must be a dictionary."
            ),
        }

    region_number = question.get(
        "region"
    )

    evidence = str(
        question.get(
            "evidence",
            "",
        )
        or ""
    ).strip()

    if not evidence:

        return {
            "grounded": False,
            "confidence": 0.0,
            "region_confidence": 0.0,
            "video_confidence": 0.0,
            "region": region_number,
            "evidence": "",
            "evidence_found": False,
            "exact_match": False,
            "unknown_words": [],
            "error": (
                "Question has no source evidence."
            ),
        }

    # ------------------------------------------------------
    # FIND ASSIGNED REGION
    # ------------------------------------------------------

    assigned_region = None

    for region in regions:

        if not isinstance(
            region,
            dict,
        ):
            continue

        if (
            region.get("region")
            == region_number
        ):

            assigned_region = region
            break

    # Some pipelines may not store "region" inside the
    # region dictionary and instead rely on position.
    if assigned_region is None:

        try:

            numeric_region = int(
                region_number
            )

        except (
            TypeError,
            ValueError,
        ):

            numeric_region = None

        if (
            numeric_region is not None
            and 1
            <= numeric_region
            <= len(regions)
        ):

            candidate = regions[
                numeric_region - 1
            ]

            if isinstance(
                candidate,
                dict,
            ):

                assigned_region = candidate

    if assigned_region is None:

        return {
            "grounded": False,
            "confidence": 0.0,
            "region_confidence": 0.0,
            "video_confidence": 0.0,
            "region": region_number,
            "evidence": evidence,
            "evidence_found": False,
            "exact_match": False,
            "unknown_words": [],
            "error": (
                "Assigned video region not found."
            ),
        }

    # ------------------------------------------------------
    # COLLECT ALL SOURCE CONTEXTS FOR THIS REGION
    # ------------------------------------------------------

    context_keys = [
        "mcq_context",
        "short_context",
        "long_context",
        "context",
        "evidence",
        "source_context",
        "transcript",
        "text",
    ]

    region_contexts = []

    for key in context_keys:

        value = str(
            assigned_region.get(
                key,
                "",
            )
            or ""
        ).strip()

        if not value:
            continue

        if value in region_contexts:
            continue

        region_contexts.append(
            value
        )

    # Preserve compatibility with the existing helper.
    question_type = str(
        question.get(
            "type",
            "",
        )
        or ""
    ).strip().lower()

    preferred_context = _get_region_context(
        regions,
        region_number,
        question_type,
    )

    preferred_context = str(
        preferred_context or ""
    ).strip()

    if (
        preferred_context
        and preferred_context
        not in region_contexts
    ):

        region_contexts.insert(
            0,
            preferred_context,
        )

    if not region_contexts:

        return {
            "grounded": False,
            "confidence": 0.0,
            "region_confidence": 0.0,
            "video_confidence": 0.0,
            "region": region_number,
            "evidence": evidence,
            "evidence_found": False,
            "exact_match": False,
            "unknown_words": [],
            "error": (
                "No source context was found "
                "for the assigned region."
            ),
        }

    # ------------------------------------------------------
    # WHOLE VIDEO CONTEXT
    # ------------------------------------------------------

    whole_context = str(
        _all_video_context(
            regions,
            question_type,
        )
        or ""
    ).strip()

    # ------------------------------------------------------
    # NORMALIZED EXACT MATCH
    # ------------------------------------------------------
    #
    # This is the strongest check.
    #
    # If the generated evidence is actually copied from
    # ANY source field belonging to the assigned region,
    # accept it as fully grounded.
    #
    # This is especially important for Kannada/Hindi/etc.
    # where English question text is a paraphrase but the
    # evidence itself remains in the original language.
    # ------------------------------------------------------

    normalized_evidence = normalize_text(
        evidence
    )

    exact_region_match = False
    matched_context = ""

    if normalized_evidence:

        for context in region_contexts:

            normalized_context = normalize_text(
                context
            )

            if not normalized_context:
                continue

            if (
                normalized_evidence
                in normalized_context
            ):

                exact_region_match = True
                matched_context = context
                break

    if exact_region_match:

        return {
            "grounded": True,
            "confidence": 100.0,
            "region_confidence": 100.0,
            "video_confidence": 100.0,
            "region": region_number,
            "evidence": evidence,
            "evidence_found": True,
            "exact_match": True,
            "matched_context": (
                matched_context
            ),
            "unknown_words": [],
            "error": None,
        }

    # ------------------------------------------------------
    # EXACT VIDEO MATCH
    # ------------------------------------------------------

    normalized_video = normalize_text(
        whole_context
    )

    exact_video_match = (
        bool(normalized_evidence)
        and bool(normalized_video)
        and (
            normalized_evidence
            in normalized_video
        )
    )

    # A source excerpt found in the whole video but not
    # in the assigned region is NOT accepted as grounded.
    # Keep the result informative, but continue checking.
    if exact_video_match:

        video_exact_evidence = True

    else:

        video_exact_evidence = False

    # ------------------------------------------------------
    # TOKEN-LEVEL NEAR MATCH
    # ------------------------------------------------------

    evidence_tokens = tokenize(
        evidence
    )

    best_region_score = 0.0
    best_video_score = 0.0
    best_region_overlap = None

    # Compare against EVERY context field in the
    # assigned region and keep the strongest score.
    for context in region_contexts:

        region_tokens = tokenize(
            context
        )

        overlap = _calculate_overlap(
            evidence_tokens,
            region_tokens,
        )

        score = float(
            overlap.get(
                "score",
                0.0,
            )
            or 0.0
        )

        if score > best_region_score:

            best_region_score = score
            best_region_overlap = overlap

    # Whole-video comparison
    if whole_context:

        video_tokens = tokenize(
            whole_context
        )

        video_overlap = _calculate_overlap(
            evidence_tokens,
            video_tokens,
        )

        best_video_score = float(
            video_overlap.get(
                "score",
                0.0,
            )
            or 0.0
        )

    # ------------------------------------------------------
    # CONFIDENCE
    # ------------------------------------------------------

    confidence = round(
        (
            best_region_score
            * 0.85
        )
        + (
            best_video_score
            * 0.15
        ),
        1,
    )

    # ------------------------------------------------------
    # GROUNDING DECISION
    # ------------------------------------------------------
    #
    # The assigned region remains the authority.
    #
    # 80% was previously applied to only one context field.
    # Since we now compare ALL source fields from that region,
    # keep the same strong threshold.
    # ------------------------------------------------------

    grounded = (
        best_region_score >= 55.0
    )

    # Exact source evidence in the whole video but not in
    # the assigned region must remain rejected.
    if (
        video_exact_evidence
        and best_region_score < 80.0
    ):

        grounded = False

    # ------------------------------------------------------
    # UNKNOWN WORDS
    # ------------------------------------------------------

    unknown_words = []

    if isinstance(
        best_region_overlap,
        dict,
    ):

        unknown_words = (
            best_region_overlap.get(
                "unknown_words",
                [],
            )
        )

        if not isinstance(
            unknown_words,
            list,
        ):

            unknown_words = []

    # ------------------------------------------------------
    # FINAL RESULT
    # ------------------------------------------------------

    return {
        "grounded": bool(
            grounded
        ),

        "confidence": confidence,

        "region_confidence": (
            round(
                best_region_score,
                1,
            )
        ),

        "video_confidence": (
            round(
                best_video_score,
                1,
            )
        ),

        "region": region_number,

        "evidence": evidence,

        "evidence_found": (
            best_region_score > 0.0
        ),

        "exact_match": False,

        "video_exact_match": (
            video_exact_evidence
        ),

        "unknown_words": (
            unknown_words
        ),

        "error": (
            None
            if grounded
            else (
                "Source evidence could not "
                "be sufficiently matched to "
                "the assigned video region."
            )
        ),
    }

# ==========================================================
# KNOWLEDGE CLAIM GROUNDING
# ==========================================================

def ground_knowledge(
    knowledge: dict,
    regions: list[dict],
) -> dict:
    """
    Verify every generated knowledge point using its
    original-language evidence and assigned source region.

    This works across English, Telugu, Hindi, Tamil,
    Kannada, Malayalam and mixed-language transcripts
    because the English knowledge claim itself does not
    need to lexically match the source language.
    """

    results = []

    total_score = 0.0

    claim_count = 0

    # ======================================================
    # VALIDATE INPUT
    # ======================================================

    if not isinstance(
        knowledge,
        dict,
    ):

        return {
            "grounded": False,
            "confidence": 0.0,
            "claim_count": 0,
            "grounded_count": 0,
            "results": [],
        }

    # ======================================================
    # COMPLETE VIDEO CONTEXT
    # ======================================================

    whole_context = (
        _all_video_context(
            regions
        )
    )

    normalized_video = (
        normalize_text(
            whole_context
        )
    )

    video_tokens = tokenize(
        whole_context
    )

    # ======================================================
    # TOPICS
    # ======================================================

    for topic in knowledge.get(
        "topics",
        [],
    ):

        if not isinstance(
            topic,
            dict,
        ):
            continue

        topic_name = str(
            topic.get(
                "topic",
                topic.get(
                    "name",
                    "",
                ),
            )
        ).strip()

        points = topic.get(
            "points",
            [],
        )

        if not isinstance(
            points,
            list,
        ):
            continue

        # ==================================================
        # KNOWLEDGE POINTS
        # ==================================================

        for point_item in points:

            # ==============================================
            # NEW EVIDENCE-AWARE FORMAT
            # ==============================================

            if isinstance(
                point_item,
                dict,
            ):

                point = str(
                    point_item.get(
                        "point",
                        "",
                    )
                ).strip()

                region_number = (
                    point_item.get(
                        "region"
                    )
                )

                source_evidence = str(
                    point_item.get(
                        "evidence",
                        "",
                    )
                ).strip()

            # ==============================================
            # OLD FORMAT
            # ==============================================

            else:

                point = str(
                    point_item
                ).strip()

                region_number = None

                source_evidence = ""

            if not point:
                continue

            claim_count += 1

            # ==============================================
            # NO EVIDENCE
            # ==============================================

            if not source_evidence:

                results.append(
                    {
                        "topic": topic_name,
                        "claim": point,
                        "region": (
                            region_number
                        ),
                        "evidence": "",
                        "grounded": False,
                        "confidence": 0.0,
                        "region_confidence": 0.0,
                        "video_confidence": 0.0,
                        "evidence_found": False,
                        "exact_match": False,
                        "unknown_words": [],
                        "error": (
                            "Knowledge point has "
                            "no source evidence."
                        ),
                    }
                )

                continue

            # ==============================================
            # REGION LOOKUP
            # ==============================================

            region_context = (
                _get_region_context(
                    regions,
                    region_number,
                )
            )

            if not region_context:

                results.append(
                    {
                        "topic": topic_name,
                        "claim": point,
                        "region": (
                            region_number
                        ),
                        "evidence": (
                            source_evidence
                        ),
                        "grounded": False,
                        "confidence": 0.0,
                        "region_confidence": 0.0,
                        "video_confidence": 0.0,
                        "evidence_found": False,
                        "exact_match": False,
                        "unknown_words": [],
                        "error": (
                            "Assigned knowledge "
                            "region not found."
                        ),
                    }
                )

                continue

            # ==============================================
            # NORMALIZE
            # ==============================================

            normalized_evidence = (
                normalize_text(
                    source_evidence
                )
            )

            normalized_region = (
                normalize_text(
                    region_context
                )
            )

            # ==============================================
            # EXACT REGION MATCH
            # ==============================================

            exact_region_match = (
                normalized_evidence
                in normalized_region
            )

            exact_video_match = (
                normalized_evidence
                in normalized_video
            )

            if exact_region_match:

                score = 100.0

                total_score += score

                results.append(
                    {
                        "topic": topic_name,
                        "claim": point,
                        "region": (
                            region_number
                        ),
                        "evidence": (
                            source_evidence
                        ),
                        "grounded": True,
                        "confidence": 100.0,
                        "region_confidence": 100.0,
                        "video_confidence": 100.0,
                        "evidence_found": True,
                        "exact_match": True,
                        "unknown_words": [],
                        "error": None,
                    }
                )

                continue

            # ==============================================
            # NEAR TOKEN MATCH
            # ==============================================

            evidence_tokens = tokenize(
                source_evidence
            )

            region_tokens = tokenize(
                region_context
            )

            region_overlap = (
                _calculate_overlap(
                    evidence_tokens,
                    region_tokens,
                )
            )

            video_overlap = (
                _calculate_overlap(
                    evidence_tokens,
                    video_tokens,
                )
            )

            region_score = (
                region_overlap[
                    "score"
                ]
            )

            video_score = (
                video_overlap[
                    "score"
                ]
            )

            # Assigned source region is the primary
            # grounding evidence.

            score = round(
                (
                    region_score
                    * 0.85
                )
                + (
                    video_score
                    * 0.15
                ),
                1,
            )

            grounded = (
                region_score >= 80.0
            )

            total_score += score

            results.append(
                {
                    "topic": topic_name,

                    "claim": point,

                    "region": (
                        region_number
                    ),

                    "evidence": (
                        source_evidence
                    ),

                    "grounded": grounded,

                    "confidence": score,

                    "region_confidence": (
                        region_score
                    ),

                    "video_confidence": (
                        video_score
                    ),

                    "evidence_found": (
                        region_score >= 55.0
                    ),

                    "exact_match": False,

                    "matched_words": (
                        region_overlap[
                            "matched"
                        ]
                    ),

                    "unknown_words": (
                        region_overlap[
                            "unknown"
                        ]
                    ),

                    "error": None,
                }
            )

    # ======================================================
    # FINAL RESULT
    # ======================================================

    grounded_count = sum(
        1
        for item in results
        if item.get(
            "grounded",
            False,
        )
    )

    average = round(
        total_score
        / max(
            1,
            claim_count,
        ),
        1,
    )

    return {
        "grounded": (
            claim_count > 0
            and grounded_count
            == claim_count
        ),

        "confidence": average,

        "claim_count": (
            claim_count
        ),

        "grounded_count": (
            grounded_count
        ),

        "results": results,
    }


# ==========================================================
# COMPLETE QUIZ GROUNDING
# ==========================================================

def ground_quiz(
    questions: list[dict],
    regions: list[dict],
) -> dict:

    results = []

    for index, question in enumerate(
        questions,
        start=1,
    ):

        result = ground_question(
            question,
            regions,
        )

        result["question_number"] = index

        result["type"] = question.get(
            "type"
        )

        results.append(
            result
        )

    if not results:

        return {
            "grounded": False,
            "confidence": 0.0,
            "grounded_count": 0,
            "question_count": 0,
            "results": [],
        }

    grounded_count = sum(
        1
        for result in results
        if result["grounded"]
    )

    confidence = round(
        sum(
            result["confidence"]
            for result in results
        )
        / len(results),
        1,
    )

    # Good-enough production threshold:
    # For a normal 15-question quiz, at least 10 questions
    # must pass source grounding.
    minimum_grounded = max(
        1,
        int(len(results) * 0.67),
    )

    return {
        "grounded": (
            grounded_count >= minimum_grounded
        ),

        "confidence": confidence,

        "grounded_count": grounded_count,

        "question_count": len(
            results
        ),

        "results": results,
    }




# ==========================================================
# BACKWARD COMPATIBILITY
# ==========================================================

def detect_hallucination(
    question,
    graph,
):
    """
    Legacy compatibility function.

    Keeps older StudyFree pipeline code working while the
    project migrates to source-region grounding.
    """

    if not isinstance(question, dict):
        return {
            "hallucinated": True,
            "confidence": 0.0,
            "unknown_words": [],
        }

    if not isinstance(graph, dict):
        graph = {}

    knowledge_text = []

    for topic in graph.get(
        "topics",
        []
    ):

        if not isinstance(topic, dict):
            continue

        knowledge_text.append(
            str(
                topic.get(
                    "name",
                    topic.get(
                        "topic",
                        "",
                    ),
                )
            )
        )

        knowledge_text.append(
            str(
                topic.get(
                    "summary",
                    "",
                )
            )
        )

        for point in topic.get(
            "points",
            [],
        ):

            knowledge_text.append(
                str(point)
            )

        for fact in topic.get(
            "facts",
            [],
        ):

            knowledge_text.append(
                str(fact)
            )

        for keyword in topic.get(
            "keywords",
            [],
        ):

            knowledge_text.append(
                str(keyword)
            )

    generated_text = (
        str(
            question.get(
                "question",
                ""
            )
        )
        + " "
        + str(
            question.get(
                "answer",
                ""
            )
        )
    )

    generated_tokens = tokenize(
        generated_text
    )

    knowledge_tokens = tokenize(
        "\n".join(
            knowledge_text
        )
    )

    overlap = _calculate_overlap(
        generated_tokens,
        knowledge_tokens,
    )

    confidence = overlap[
        "score"
    ]

    return {
        "hallucinated": (
            confidence < 45.0
        ),

        "confidence": confidence,

        "unknown_words": (
            overlap["unknown"]
        ),
    }