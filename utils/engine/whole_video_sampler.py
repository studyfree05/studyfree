"""
whole_video_sampler.py
----------------------

Builds balanced evidence contexts from the ENTIRE
educational video.

Production goals:
- very fast
- zero AI calls
- support short and long videos
- preserve whole-video coverage
- give MCQ / short / long generators different evidence
- reduce repeated concepts
- remain backward compatible with "context"
"""

from __future__ import annotations

import re
import time


DEFAULT_REGIONS = 5
DEFAULT_CONTEXT_CHARS = 2200


# ==========================================================
# CLEAN SAMPLE
# ==========================================================

def _clean_sample(
    text: str,
) -> str:
    """
    Normalize whitespace without translating or changing
    the original language.
    """

    text = str(
        text or ""
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# ==========================================================
# REGION BOUNDS
# ==========================================================

def _region_bounds(
    text_length: int,
    regions: int,
) -> list[tuple[int, int]]:
    """
    Divide the complete transcript into approximately
    equal timeline regions.
    """

    if text_length <= 0:
        return []

    regions = max(
        1,
        min(
            int(regions),
            text_length,
        ),
    )

    bounds = []

    for index in range(
        regions
    ):

        start = int(
            index
            * text_length
            / regions
        )

        end = int(
            (index + 1)
            * text_length
            / regions
        )

        bounds.append(
            (
                start,
                end,
            )
        )

    return bounds


# ==========================================================
# SAFE WINDOW
# ==========================================================

def _window_around(
    text: str,
    center_ratio: float,
    max_chars: int,
) -> str:
    """
    Extract a context window around a relative position
    inside one video region.

    center_ratio:
        0.0 = beginning
        0.5 = middle
        1.0 = end
    """

    text = str(
        text or ""
    ).strip()

    if not text:
        return ""

    if len(text) <= max_chars:
        return _clean_sample(
            text
        )

    max_chars = min(
        max_chars,
        len(text),
    )

    center = int(
        len(text)
        * center_ratio
    )

    start = (
        center
        - (max_chars // 2)
    )

    start = max(
        0,
        start,
    )

    start = min(
        start,
        len(text)
        - max_chars,
    )

    end = (
        start
        + max_chars
    )

    return _clean_sample(
        text[start:end]
    )


# ==========================================================
# LEGACY BALANCED SAMPLE
# ==========================================================

def _sample_region(
    text: str,
    start: int,
    end: int,
    max_chars: int,
) -> str:
    """
    Build the original balanced beginning + middle + end
    sample.

    This remains available as "context" so existing code
    and tests remain compatible.
    """

    region = text[
        start:end
    ].strip()

    if not region:
        return ""

    if len(region) <= max_chars:

        return _clean_sample(
            region
        )

    piece_chars = max(
        1,
        max_chars // 3,
    )

    # Beginning
    first = region[
        :piece_chars
    ]

    # Middle
    middle_center = (
        len(region)
        // 2
    )

    middle_start = max(
        0,
        middle_center
        - (piece_chars // 2),
    )

    middle = region[
        middle_start:
        middle_start
        + piece_chars
    ]

    # End
    last = region[
        -piece_chars:
    ]

    sample = (
        first
        + "\n"
        + middle
        + "\n"
        + last
    )

    return _clean_sample(
        sample
    )


# ==========================================================
# DIVERSITY CONTEXTS
# ==========================================================

def _build_diversity_contexts(
    region_text: str,
    max_chars: int,
) -> dict:
    """
    Create three different evidence windows from one
    timeline region.

    MCQ:
        earlier part of region

    SHORT:
        middle part of region

    LONG:
        later part of region

    The positions intentionally overlap slightly.
    This keeps enough educational context while reducing
    the chance that all three AI calls choose exactly the
    same concept.
    """

    region_text = str(
        region_text or ""
    ).strip()

    if not region_text:

        return {
            "mcq_context": "",
            "short_context": "",
            "long_context": "",
        }

    # ------------------------------------------------------
    # SHORT REGION
    #
    # If the region itself is small, all generators receive
    # the complete region. We prefer correct grounding over
    # artificial diversity.
    # ------------------------------------------------------

    if len(region_text) <= max_chars:

        cleaned = _clean_sample(
            region_text
        )

        return {
            "mcq_context": cleaned,
            "short_context": cleaned,
            "long_context": cleaned,
        }

    # ------------------------------------------------------
    # DIFFERENT POSITIONS
    #
    # 20% = early
    # 50% = middle
    # 80% = late
    #
    # Each still gets the full chars_per_region budget.
    # ------------------------------------------------------

    mcq_context = _window_around(
        region_text,
        center_ratio=0.20,
        max_chars=max_chars,
    )

    short_context = _window_around(
        region_text,
        center_ratio=0.50,
        max_chars=max_chars,
    )

    long_context = _window_around(
        region_text,
        center_ratio=0.80,
        max_chars=max_chars,
    )

    # ------------------------------------------------------
    # SAFETY FALLBACK
    # ------------------------------------------------------

    fallback = _clean_sample(
        region_text[
            :max_chars
        ]
    )

    if not mcq_context:
        mcq_context = fallback

    if not short_context:
        short_context = fallback

    if not long_context:
        long_context = fallback

    return {
        "mcq_context": mcq_context,
        "short_context": short_context,
        "long_context": long_context,
    }


# ==========================================================
# BUILD VIDEO REGIONS
# ==========================================================

def build_video_regions(
    text: str,
    regions: int = DEFAULT_REGIONS,
    chars_per_region: int = DEFAULT_CONTEXT_CHARS,
) -> dict:
    """
    Divide the complete transcript into balanced timeline
    regions.

    Every region contains:

    context
        Legacy beginning + middle + end sample.

    mcq_context
        Earlier evidence window.

    short_context
        Middle evidence window.

    long_context
        Later evidence window.

    This gives the three parallel question generators
    different evidence without adding another AI call.
    """

    start_time = (
        time.perf_counter()
    )

    # ------------------------------------------------------
    # VALIDATE TEXT
    # ------------------------------------------------------

    if not isinstance(
        text,
        str,
    ):

        return {
            "success": False,
            "regions": [],
            "count": 0,
            "original_chars": 0,
            "context_chars": 0,
            "diversity_context_chars": 0,
            "time": 0,
            "error": (
                "Transcript must be text."
            ),
        }

    text = text.strip()

    if not text:

        return {
            "success": False,
            "regions": [],
            "count": 0,
            "original_chars": 0,
            "context_chars": 0,
            "diversity_context_chars": 0,
            "time": 0,
            "error": (
                "Empty transcript."
            ),
        }

    # ------------------------------------------------------
    # SETTINGS
    # ------------------------------------------------------

    regions = max(
        1,
        int(regions),
    )

    chars_per_region = max(
        300,
        int(chars_per_region),
    )

    # ------------------------------------------------------
    # REGION BOUNDS
    # ------------------------------------------------------

    bounds = _region_bounds(
        len(text),
        regions,
    )

    output = []

    # ------------------------------------------------------
    # BUILD EACH REGION
    # ------------------------------------------------------

    for index, (
        region_start,
        region_end,
    ) in enumerate(
        bounds,
        start=1,
    ):

        region_text = text[
            region_start:
            region_end
        ].strip()

        if not region_text:
            continue

        # Existing balanced sample
        sample = _sample_region(
            text,
            region_start,
            region_end,
            chars_per_region,
        )

        if not sample:
            continue

        # New role-specific samples
        diversity = (
            _build_diversity_contexts(
                region_text,
                chars_per_region,
            )
        )

        mcq_context = (
            diversity[
                "mcq_context"
            ]
        )

        short_context = (
            diversity[
                "short_context"
            ]
        )

        long_context = (
            diversity[
                "long_context"
            ]
        )

        output.append({
            "region": index,

            "start_char":
                region_start,

            "end_char":
                region_end,

            "source_chars": (
                region_end
                - region_start
            ),

            # Backward-compatible context
            "context":
                sample,

            "context_chars":
                len(sample),

            # New diversity contexts
            "mcq_context":
                mcq_context,

            "mcq_context_chars":
                len(mcq_context),

            "short_context":
                short_context,

            "short_context_chars":
                len(short_context),

            "long_context":
                long_context,

            "long_context_chars":
                len(long_context),
        })

    # ------------------------------------------------------
    # STATS
    # ------------------------------------------------------

    total_context_chars = sum(
        item[
            "context_chars"
        ]
        for item in output
    )

    diversity_context_chars = sum(

        item[
            "mcq_context_chars"
        ]
        +
        item[
            "short_context_chars"
        ]
        +
        item[
            "long_context_chars"
        ]

        for item in output
    )

    # ------------------------------------------------------
    # RESULT
    # ------------------------------------------------------

    return {
        "success":
            bool(output),

        "regions":
            output,

        "count":
            len(output),

        "original_chars":
            len(text),

        "context_chars":
            total_context_chars,

        "diversity_context_chars":
            diversity_context_chars,

        "time":
            round(
                time.perf_counter()
                - start_time,
                4,
            ),

        "error": (
            None
            if output
            else
            "No video regions created."
        ),
    }


# ==========================================================
# BUILD COMBINED CONTEXT
# ==========================================================

def build_combined_context(
    result: dict,
) -> str:
    """
    Backward-compatible combined context builder.

    Uses the legacy balanced "context" field.
    """

    if not result.get(
        "success"
    ):

        return ""

    blocks = []

    for item in result.get(
        "regions",
        [],
    ):

        blocks.append(
            "[VIDEO REGION "
            + str(
                item["region"]
            )
            + "]\n"
            + item["context"]
        )

    return "\n\n".join(
        blocks
    )