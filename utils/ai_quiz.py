"""
ai_quiz.py

Main production AI Quiz pipeline.

Uses:
- Free Quiz Pipeline
- Cache
- Whole-video sampling
- Parallel AI generation
- Universal validation
"""

from __future__ import annotations

import time

from .engine.free_quiz_pipeline import (
    generate_free_quiz,
)


def generate_quiz(
    youtube_url: str,
):
    """
    Main production quiz generator.

    This is the ONLY entry point used by the website.

    Pipeline:

        Cache
          ↓
        Transcript
          ↓
        Cleaning
          ↓
        Whole-video sampling
          ↓
        Parallel AI generation
          ↓
        Validation
          ↓
        Cache
          ↓
        Return quiz
    """

    start = time.perf_counter()

    print("=" * 60)
    print("AI QUIZ PIPELINE")
    print("=" * 60)

    print("Video:")
    print(youtube_url)

    print()

    result = generate_free_quiz(
        youtube_url=youtube_url,
        use_cache=True,
    )

    result["time"] = round(
        time.perf_counter() - start,
        2,
    )

    print()

    print("=" * 60)

    if result.get("success"):

        print("QUIZ GENERATED SUCCESSFULLY")

        print("-" * 60)

        print(
            "Questions :",
            result.get("count"),
        )

        print(
            "Cached    :",
            result.get("cached"),
        )

        if result.get("cached"):

            print(
                "Cache time:",
                result.get(
                    "cache_time",
                    0,
                ),
                "seconds",
            )

        else:

            print(
                "Providers:",
                result.get(
                    "providers",
                ),
            )

            print(
                "Models:",
                result.get(
                    "models",
                ),
            )

            print(
                "AI times:",
                result.get(
                    "ai_times",
                ),
            )

            print(
                "Processing:",
                result.get(
                    "processing_times",
                ),
            )

        print(
            "Total time:",
            result.get("time"),
            "seconds",
        )

    else:

        print("QUIZ GENERATION FAILED")

        print("-" * 60)

        print(
            "Error:",
            result.get(
                "error",
            ),
        )

        print(
            "Time:",
            result.get("time"),
            "seconds",
        )

    print("=" * 60)

    return result