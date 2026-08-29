"""
free_knowledge_generator.py

Whole-video structured knowledge generation
using the existing free OpenRouter provider.

Features:
- whole-video knowledge
- multilingual source support
- original-language evidence
- region-aware grounding
- strict validation
"""

from __future__ import annotations

import json
import re

from .providers.openrouter_provider import (
    generate_with_openrouter,
)

from .whole_video_sampler import (
    build_combined_context,
)


# ==========================================================
# SETTINGS
# ==========================================================

VALID_REGIONS = {
    1,
    2,
    3,
    4,
    5,
}


# ==========================================================
# PROMPT
# ==========================================================

def build_knowledge_prompt(
    regions: list[dict],
) -> str:

    region_result = {
        "success": bool(regions),
        "regions": regions,
    }

    evidence = build_combined_context(
        region_result
    )

    return f"""
You are the StudyFree educational knowledge engine.

Analyze the supplied evidence from multiple regions of ONE
educational video.

The evidence may be:
- English
- Telugu
- Hindi
- Tamil
- Kannada
- Malayalam
- another language
- mixed with English

Your task is to reconstruct the IMPORTANT EDUCATIONAL
KNOWLEDGE taught throughout the video.

IMPORTANT RULES:

- Use ALL video regions.
- Cover the whole lesson, not only the beginning.
- Output title, summary, topic names and educational points
  in English.
- Preserve programming terms, formulas, symbols and
  technical terminology accurately.
- Do not invent facts unsupported by the evidence.
- Do not treat casual examples as major topics.
- Do not mistake example values for the main concept.
- Merge duplicate concepts taught in different regions.
- Prefer meaningful concepts over superficial transcript
  wording.
- Do not answer questions spoken by the lecturer.
- Do not continue the lecture.
- Do not include markdown.
- Return ONLY valid JSON.


SOURCE GROUNDING RULE:

EVERY educational point MUST include:

1. "region"
   The VIDEO REGION number where the point is supported.

2. "evidence"
   A short source excerpt copied DIRECTLY from that region.

The evidence MUST:

- come from the specified region
- remain in the ORIGINAL source language
- NOT be translated
- NOT be paraphrased
- NOT be rewritten into cleaner language
- support the educational point
- preferably contain about 8 to 40 words

For mixed-language lectures, preserve the exact mixed
language appearing in the source.

For example, if the source is Telugu mixed with English,
the evidence must remain Telugu-English.

Never invent evidence.

If a point cannot be supported by a source excerpt,
DO NOT include that point.


Required JSON structure:

{{
  "title": "accurate short lesson title",

  "summary": "concise summary covering the overall lesson",

  "topics": [
    {{
      "topic": "major educational concept",

      "points": [
        {{
          "point": "important fact or explanation in English",
          "region": 1,
          "evidence": "exact original-language source excerpt"
        }},
        {{
          "point": "another important fact or explanation",
          "region": 2,
          "evidence": "exact original-language source excerpt"
        }}
      ]
    }}
  ]
}}


QUALITY REQUIREMENTS:

- Prefer 4 to 8 major topics when supported by the video.
- Fewer topics are acceptable only when the source genuinely
  contains fewer concepts.
- Prefer 2 to 5 useful points for each topic.
- Avoid duplicate topics.
- Avoid duplicate points.
- Do not create vague topics such as "Video Transcription".
- Do not create a topic merely from an isolated example.
- Topic names should represent concepts being taught.
- Summary must describe the lesson rather than the transcript.
- Summary should be under 120 words.
- Knowledge should cover concepts from across the supplied
  video regions.
- Every retained point must contain valid source evidence.


VIDEO EVIDENCE:

{evidence}

Return the JSON object only.
"""


# ==========================================================
# JSON PARSING
# ==========================================================

def _extract_json(
    text: str,
) -> str:

    text = str(
        text or ""
    ).strip()

    text = re.sub(
        r"```json",
        "",
        text,
        flags=re.I,
    )

    text = re.sub(
        r"```",
        "",
        text,
    )

    match = re.search(
        r"\{.*\}",
        text,
        re.S,
    )

    if match:
        return match.group(0)

    return text


def _parse_json(
    text: str,
):

    try:

        return json.loads(
            _extract_json(
                text
            )
        )

    except Exception:

        return None


# ==========================================================
# VALIDATION
# ==========================================================

def _validate_knowledge(
    data,
) -> bool:

    if not isinstance(
        data,
        dict,
    ):
        return False

    # ======================================================
    # TITLE
    # ======================================================

    title = str(
        data.get(
            "title",
            "",
        )
    ).strip()

    if not title:
        return False

    # ======================================================
    # SUMMARY
    # ======================================================

    summary = str(
        data.get(
            "summary",
            "",
        )
    ).strip()

    if not summary:
        return False

    # ======================================================
    # TOPICS
    # ======================================================

    topics = data.get(
        "topics",
        [],
    )

    if not isinstance(
        topics,
        list,
    ):
        return False

    cleaned_topics = []

    seen_topics = set()

    used_regions = set()

    # ======================================================
    # CLEAN TOPICS
    # ======================================================

    for topic in topics:

        if not isinstance(
            topic,
            dict,
        ):
            continue

        name = str(
            topic.get(
                "topic",
                "",
            )
        ).strip()

        points = topic.get(
            "points",
            [],
        )

        if not name:
            continue

        if not isinstance(
            points,
            list,
        ):
            continue

        normalized_name = (
            name.casefold()
        )

        if (
            normalized_name
            in seen_topics
        ):
            continue

        cleaned_points = []

        seen_points = set()

        # ==================================================
        # CLEAN POINTS
        # ==================================================

        for point_item in points:

            if not isinstance(
                point_item,
                dict,
            ):
                continue

            point = str(
                point_item.get(
                    "point",
                    "",
                )
            ).strip()

            region = point_item.get(
                "region"
            )

            evidence = str(
                point_item.get(
                    "evidence",
                    "",
                )
            ).strip()

            # ----------------------------------------------
            # REQUIRED POINT
            # ----------------------------------------------

            if len(point) < 5:
                continue

            # ----------------------------------------------
            # REQUIRED REGION
            # ----------------------------------------------

            if (
                region
                not in VALID_REGIONS
            ):
                continue

            # ----------------------------------------------
            # REQUIRED EVIDENCE
            # ----------------------------------------------

            if len(evidence) < 3:
                continue

            normalized_point = (
                point.casefold()
            )

            if (
                normalized_point
                in seen_points
            ):
                continue

            seen_points.add(
                normalized_point
            )

            used_regions.add(
                region
            )

            cleaned_points.append(
                {
                    "point": point,
                    "region": region,
                    "evidence": evidence,
                }
            )

        if not cleaned_points:
            continue

        seen_topics.add(
            normalized_name
        )

        cleaned_topics.append(
            {
                "topic": name,
                "points": (
                    cleaned_points[:5]
                ),
            }
        )

    # ======================================================
    # FINAL VALIDATION
    # ======================================================

    if not cleaned_topics:
        return False

    # We do not require all five regions here because some
    # regions may contain repetition, examples, or little
    # educational material.
    #
    # However, whole-video knowledge should normally use
    # more than one source region.

    if (
        len(VALID_REGIONS) > 1
        and len(used_regions) < 2
    ):
        return False

    data["title"] = title

    data["summary"] = summary

    data["topics"] = (
        cleaned_topics[:8]
    )

    data["source_regions"] = sorted(
        used_regions
    )

    return True


# ==========================================================
# PUBLIC GENERATOR
# ==========================================================

def generate_free_knowledge(
    regions: list[dict],
) -> dict:

    if (
        not isinstance(
            regions,
            list,
        )
        or not regions
    ):

        return {
            "success": False,
            "knowledge": None,
            "provider": None,
            "model": None,
            "error": (
                "No video regions supplied."
            ),
        }

    # ======================================================
    # PROMPT
    # ======================================================

    prompt = build_knowledge_prompt(
        regions
    )

    # ======================================================
    # FREE OPENROUTER CALL
    # ======================================================

    result = (
        generate_with_openrouter(
            prompt=prompt,
            task="knowledge",
            json_mode=True,
            max_tokens=2200,
            temperature=0.1,
        )
    )

    # ======================================================
    # PROVIDER FAILURE
    # ======================================================

    if not result.success:

        return {
            "success": False,
            "knowledge": None,

            "provider": getattr(
                result,
                "provider",
                None,
            ),

            "model": getattr(
                result,
                "model",
                None,
            ),

            "error": getattr(
                result,
                "error",
                "Knowledge AI failed.",
            ),
        }

    # ======================================================
    # GET RESPONSE
    # ======================================================

    raw_text = getattr(
        result,
        "text",
        "",
    )

    data = _parse_json(
        raw_text
    )

    # ======================================================
    # JSON FAILURE
    # ======================================================

    if data is None:

        print("\n" + "=" * 60)
        print("INVALID KNOWLEDGE JSON FROM AI")
        print("=" * 60)
        print(raw_text)
        print("=" * 60 + "\n")

        return {
            "success": False,
            "knowledge": None,

            "provider": getattr(
                result,
                "provider",
                None,
            ),

            "model": getattr(
                result,
                "model",
                None,
            ),

            "error": (
                "Knowledge AI returned "
                "invalid JSON."
            ),
        }

    # ======================================================
    # VALIDATION FAILURE
    # ======================================================

    if not _validate_knowledge(
        data
    ):

        return {
            "success": False,
            "knowledge": None,

            "provider": getattr(
                result,
                "provider",
                None,
            ),

            "model": getattr(
                result,
                "model",
                None,
            ),

            "error": (
                "Generated knowledge "
                "failed validation."
            ),
        }

    # ======================================================
    # SUCCESS
    # ======================================================

    return {
        "success": True,

        "knowledge": data,

        "provider": getattr(
            result,
            "provider",
            "openrouter",
        ),

        "model": getattr(
            result,
            "model",
            None,
        ),

        "error": None,
    }