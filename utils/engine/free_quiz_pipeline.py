"""
free_quiz_pipeline.py
---------------------

Production FREE quiz-generation pipeline.

Flow:
1. Check quiz cache FIRST.
2. Fetch transcript on cache miss.
3. Clean transcript.
4. Detect language.
5. Build balanced whole-video regions.
6. Generate MCQ / short / long batches in parallel.
7. Validate all 15 questions.
8. Check whole-video coverage.
9. Validate quiz quality.
10. Build analytics.
11. Cache only a complete valid quiz.
12. Return result.

IMPORTANT:
- Quiz generation uses THREE parallel AI calls.
- Knowledge generation is NOT part of this pipeline.
- No paid AI fallback is used here.
"""

from __future__ import annotations


import time
import re
import json
from concurrent.futures import ThreadPoolExecutor

from .transcript import fetch_transcript
from .cleaner import clean_transcript
from .whole_video_sampler import build_video_regions

from .free_batch_question_generator import (
    generate_mcq_batch,
    generate_short_batch,
    generate_long_batch,
)

from .providers.provider_router import (
    generate_with_provider_router,
)

from .quiz_cache import (
    load_quiz_cache,
    save_quiz_cache,
)

from utils.engine.language.detector import (
    detect_language,
)

from utils.engine.validators.question_validator import (
    validate_question,
)

from utils.engine.coverage.coverage import (
    calculate_coverage,
)

from utils.engine.analytics.analytics import (
    build_analytics,
)

from .quiz_quality import (
    validate_quiz_quality,
)

from utils.engine.hallucination.detector import (
    ground_quiz,
)

from .offline_mcq_generator import (
    generate_offline_quiz,
)

# ==========================================================
# SETTINGS
# ==========================================================

REGION_COUNT = 5

CHARS_PER_REGION = 850

EXPECTED_PER_TYPE = 5

EXPECTED_TOTAL = 15


def _english_quiz_text_ok(text):
    """
    Lightweight English-language sanity check for generated quiz text.
    Returns True when the text contains normal English alphabetic content.
    """
    if not text:
        return False

    text = str(text).strip()

    if not text:
        return False

    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False

    english_letters = sum(
        1 for c in letters
        if ("a" <= c.lower() <= "z")
    )

    return (english_letters / len(letters)) >= 0.70


# ==========================================================
# TIMED AI CALL
# ==========================================================

def _timed_call(
    function,
    regions: list[dict],
):

    start = time.perf_counter()

    result = function(
        regions
    )

    elapsed = (
        time.perf_counter()
        - start
    )

    return result, elapsed


# ==========================================================
# BATCH VALIDATION
# ==========================================================

def _valid_batch(
    batch: dict,
    expected_type: str,
) -> bool:

    if not isinstance(
        batch,
        dict,
    ):
        return False

    if not batch.get(
        "success"
    ):
        return False

    questions = batch.get(
        "questions",
        [],
    )

    if len(
        questions
    ) != EXPECTED_PER_TYPE:
        return False

    regions = set()

    for question in questions:

        if not isinstance(
            question,
            dict,
        ):
            return False

        # --------------------------------------------------
        # TYPE
        # --------------------------------------------------

        if (
            question.get("type")
            != expected_type
        ):
            return False

        # --------------------------------------------------
        # REGION
        # --------------------------------------------------

        region = question.get(
            "region"
        )

        if region not in {
            1,
            2,
            3,
            4,
            5,
        }:
            return False

        regions.add(
            region
        )

        # --------------------------------------------------
        # QUESTION + ANSWER
        # --------------------------------------------------

        text = question.get(
            "question"
        )

        answer = question.get(
            "answer"
        )

        if (
            not isinstance(
                text,
                str,
            )
            or not text.strip()
            or not isinstance(
                answer,
                str,
            )
            or not answer.strip()
        ):
            return False

        # --------------------------------------------------
        # EVIDENCE
        # --------------------------------------------------

        evidence = question.get(
            "evidence"
        )

        if (
            not isinstance(
                evidence,
                str,
            )
            or not evidence.strip()
        ):
            return False

        # --------------------------------------------------
        # MCQ
        # --------------------------------------------------

        if expected_type == "mcq":

            options = question.get(
                "options",
                [],
            )

            if (
                not isinstance(
                    options,
                    list,
                )
                or len(options) != 4
                or answer not in options
            ):
                return False

    # Exactly one question from each region.

    return regions == {
        1,
        2,
        3,
        4,
        5,
    }


# ==========================================================
# MAIN PIPELINE
# ==========================================================

def _find_cross_type_topic_duplicates(
    questions: list[dict],
) -> list[int]:
    """
    Return 1-based question numbers that repeat a main topic across
    different question types.

    This is deliberately conservative. It focuses on technical/code
    expressions and strong concept-word overlap, rather than ordinary
    educational words.
    """
    stop = {
        "what","why","how","does","do","did","is","are","was","were",
        "the","a","an","and","or","of","to","in","for","from","with",
        "on","by","as","can","could","would","should","this","that",
        "which","when","where","explain","describe","discuss","using",
        "used","use","following","statement","value","result","given",
        "example","question","operator","assignment","initial","current",
        "variable","variables","during","execution","program","code",
    }

    def features(q):
        text = str(q.get("question", "") or "").casefold()
        words = set(re.findall(r"[a-z][a-z0-9_]{2,}", text)) - stop
        technical = set(re.findall(
            r"(?:[a-z_][a-z0-9_]*\s*(?:\+=|-=|\*=|/=|%=|==|!=|<=|>=)\s*[a-z0-9_]+)"
            r"|(?:[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*)"
            r"|(?:\+=|-=|\*=|/=|%=|==|!=|<=|>=)",
            text,
        ))
        return words, technical

    parsed = [
        (i, str(q.get("type", "")).casefold(), *features(q))
        for i, q in enumerate(questions, 1)
        if isinstance(q, dict)
    ]

    duplicate_numbers = set()

    for pos, (i, ti, wi, xi) in enumerate(parsed):
        for j, tj, wj, xj in parsed[pos + 1:]:
            if ti == tj:
                continue

            if xi & xj:
                duplicate_numbers.add(j)
                continue

            if wi and wj:
                overlap = len(wi & wj) / min(len(wi), len(wj))
                if overlap >= 0.75:
                    duplicate_numbers.add(j)

    return sorted(duplicate_numbers)


def _repair_cross_type_topics(
    questions: list[dict],
    regions: list[dict],
) -> list[dict]:
    """
    One targeted Gemini repair call. Only runs when the local detector
    finds cross-type topic repetition. Non-duplicate questions are
    preserved exactly as generated.
    """
    duplicate_numbers = _find_cross_type_topic_duplicates(questions)

    if not duplicate_numbers:
        return questions

    print(
        "[QUALITY] Repeated topics found in questions:",
        duplicate_numbers,
    )

    evidence_parts = []
    for region in regions:
        if not isinstance(region, dict):
            continue
        number = region.get("region")
        context = (
            region.get("mcq_context")
            or region.get("short_context")
            or region.get("long_context")
            or region.get("context")
            or ""
        )
        if context:
            evidence_parts.append(
                f"REGION {number}:\n{str(context)[:5000]}"
            )

    compact_questions = []
    for i, q in enumerate(questions, 1):
        compact_questions.append({
            "number": i,
            "type": q.get("type"),
            "region": q.get("region"),
            "question": q.get("question"),
            "answer": q.get("answer"),
            "options": q.get("options"),
        })

    prompt = """
You are repairing an educational quiz.

Some questions repeat the SAME MAIN EDUCATIONAL TOPIC across different
question types. Replace ONLY the numbered questions listed as duplicates.

MANDATORY:
- Every replacement must be based ONLY on the supplied lesson evidence.
- Choose a genuinely different concept, fact, rule, example, behavior,
  or application from the evidence.
- Do NOT merely reword the old question.
- Do NOT reuse the same operator, code expression, definition, example,
  property, or fact already tested by another question.
- Preserve the question type and region number.
- Preserve MCQ format with exactly 4 options and an answer matching one option.
- Preserve short/long answer format.
- Return JSON only.

Return:
{
  "replacements": [
    {
      "number": 6,
      "question": "...",
      "answer": "...",
      "options": ["...", "...", "...", "..."]
    }
  ]
}

DUPLICATE QUESTION NUMBERS:
""" + json.dumps(duplicate_numbers) + """

CURRENT QUESTIONS:
""" + json.dumps(compact_questions, ensure_ascii=False) + """

LESSON EVIDENCE:
""" + "\n\n".join(evidence_parts)

    result = generate_with_provider_router(
        prompt=prompt,
        task="cross_type_topic_repair",
        json_mode=True,
        max_tokens=2200,
        temperature=0.15,
    )

    if not result.success:
        print(
            "[QUALITY] Topic repair failed:",
            result.error,
        )
        return questions

    raw = (result.text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
        raw = re.sub(r"\s*```$", "", raw)

    try:
        start = raw.find("{")
        end = raw.rfind("}")
        data = json.loads(raw[start:end + 1])
    except Exception as exc:
        print("[QUALITY] Topic repair JSON failed:", exc)
        return questions

    replacements = data.get("replacements", [])
    if not isinstance(replacements, list):
        return questions

    repaired = [dict(q) for q in questions]

    for item in replacements:
        if not isinstance(item, dict):
            continue

        try:
            number = int(item.get("number"))
        except Exception:
            continue

        if number < 1 or number > len(repaired):
            continue

        target = repaired[number - 1]
        if not isinstance(item.get("question"), str):
            continue
        if not isinstance(item.get("answer"), str):
            continue

        target["question"] = item["question"].strip()
        target["answer"] = item["answer"].strip()

        if target.get("type") == "mcq":
            options = item.get("options")
            if (
                isinstance(options, list)
                and len(options) == 4
                and all(isinstance(x, str) and x.strip() for x in options)
                and len({x.strip().casefold() for x in options}) == 4
            ):
                options = [x.strip() for x in options]
                answer_cf = target["answer"].casefold()
                match = next(
                    (x for x in options if x.casefold() == answer_cf),
                    None,
                )
                if match is None:
                    continue
                target["options"] = options
                target["answer"] = match

    # Keep only the repaired set if it is still structurally complete
    # and the same local detector no longer finds cross-type duplicates.
    if not all(
        isinstance(q.get("question"), str) and q["question"].strip()
        and isinstance(q.get("answer"), str) and q["answer"].strip()
        for q in repaired
    ):
        return questions

    if _find_cross_type_topic_duplicates(repaired):
        print(
            "[QUALITY] Topic repair still has overlap; "
            "keeping original valid quiz."
        )
        return questions

    print("[QUALITY] Cross-type topic repair PASSED.")
    return repaired


def generate_free_quiz(
    youtube_url: str,
    use_cache: bool = True,
) -> dict:

    total_start = (
        time.perf_counter()
    )

    # ======================================================
    # 1. CACHE FIRST
    # ======================================================

    if use_cache:

        cache_start = (
            time.perf_counter()
        )

        cached = load_quiz_cache(
            youtube_url
        )

        cache_time = (
            time.perf_counter()
            - cache_start
        )

        if cached is not None:

            result = dict(
                cached
            )

            result["cached"] = True

            result["cache_time"] = round(
                cache_time,
                4,
            )

            result["time"] = round(
                time.perf_counter()
                - total_start,
                4,
            )

            return result

    # ======================================================
    # 2. TRANSCRIPT
    # ======================================================

    transcript_start = (
        time.perf_counter()
    )

    transcript = fetch_transcript(
        youtube_url
    )

    transcript_time = (
        time.perf_counter()
        - transcript_start
    )

    if not transcript.get(
        "success"
    ):

        return {
            "success": False,
            "questions": [],
            "count": 0,
            "cached": False,
            "error": transcript.get(
                "error",
                "Transcript failed.",
            ),
            "time": round(
                time.perf_counter()
                - total_start,
                2,
            ),
        }

    # ======================================================
    # 3. CLEAN TRANSCRIPT
    # ======================================================

    clean_start = (
        time.perf_counter()
    )

    cleaned = clean_transcript(
        transcript["text"]
    )

    clean_time = (
        time.perf_counter()
        - clean_start
    )

    if not cleaned.get(
        "success"
    ):

        return {
            "success": False,
            "questions": [],
            "count": 0,
            "cached": False,
            "error": cleaned.get(
                "error",
                "Cleaning failed.",
            ),
            "time": round(
                time.perf_counter()
                - total_start,
                2,
            ),
        }

    # ======================================================
    # 4. LANGUAGE DETECTION
    # ======================================================

    language_start = (
        time.perf_counter()
    )

    language = detect_language(
        cleaned["text"]
    )

    language_time = (
        time.perf_counter()
        - language_start
    )

    # ======================================================
    # 5. WHOLE-VIDEO REGIONS
    # ======================================================

    region_start = (
        time.perf_counter()
    )

    region_result = build_video_regions(
        cleaned["text"],
        regions=REGION_COUNT,
        chars_per_region=CHARS_PER_REGION,
    )

    region_time = (
        time.perf_counter()
        - region_start
    )

    if not region_result.get(
        "success"
    ):

        return {
            "success": False,
            "questions": [],
            "count": 0,
            "cached": False,
            "language": language,
            "error": region_result.get(
                "error",
                "Region building failed.",
            ),
            "time": round(
                time.perf_counter()
                - total_start,
                2,
            ),
        }

    regions = region_result[
        "regions"
    ]

    # ======================================================
    # 6. THREE QUESTION CALLS IN PARALLEL
    # ======================================================

    ai_wall_start = (
        time.perf_counter()
    )

    with ThreadPoolExecutor(
        max_workers=3
    ) as executor:

        # --------------------------------------------------
        # MCQ
        # --------------------------------------------------

        mcq_future = executor.submit(
            _timed_call,
            generate_mcq_batch,
            regions,
        )

        # --------------------------------------------------
        # SHORT ANSWER
        # --------------------------------------------------

        short_future = executor.submit(
            _timed_call,
            generate_short_batch,
            regions,
        )

        # --------------------------------------------------
        # LONG ANSWER
        # --------------------------------------------------

        long_future = executor.submit(
            _timed_call,
            generate_long_batch,
            regions,
        )

        # --------------------------------------------------
        # COLLECT RESULTS
        # --------------------------------------------------

        mcq, mcq_time = (
            mcq_future.result()
        )

        short, short_time = (
            short_future.result()
        )

        long_result, long_time = (
            long_future.result()
        )

    ai_wall_time = (
        time.perf_counter()
        - ai_wall_start
    )

    # ======================================================
    # 7. VALIDATE GENERATED BATCHES
    # ======================================================

    print(
        "AI TIMES:",
        {
            "mcq": round(mcq_time, 2),
            "short": round(short_time, 2),
            "long": round(long_time, 2),
            "wall": round(ai_wall_time, 2),
        }
    )

    mcq_valid = _valid_batch(
        mcq,
        "mcq",
    )

    short_valid = _valid_batch(
        short,
        "short",
    )

    long_valid = _valid_batch(
        long_result,
        "long",
    )

    if not (
        mcq_valid
        and short_valid
        and long_valid
    ):

        errors = []

        if not mcq_valid:

            errors.append(
                "MCQ: "
                + str(
                    mcq.get(
                        "error"
                    )
                )
            )

        if not short_valid:

            errors.append(
                "Short: "
                + str(
                    short.get(
                        "error"
                    )
                )
            )

        if not long_valid:

            errors.append(
                "Long: "
                + str(
                    long_result.get(
                        "error"
                    )
                )
            )

        # ======================================================
        # COMPLETE OFFLINE FALLBACK
        # ======================================================

        offline_result = generate_offline_quiz(
            regions
        )

        if offline_result.get("success"):

            print(
                "[OFFLINE FALLBACK] "
                "Online AI batches failed. "
                "Using offline 15-question generator."
            )

            questions = offline_result.get(
                "questions",
                [],
            )

            return {
                "success": True,
                "questions": questions,
                "count": len(questions),
                "counts": offline_result.get(
                    "counts",
                    {},
                ),
                "cached": False,
                "language": language,
                "provider": "offline",
                "model": "rule-based-full",
                "validator": None,
                "coverage": None,
                "quiz_quality": None,
                "grounding": None,
                "error": None,
                "ai_times": {
                    "mcq": round(mcq_time, 2),
                    "short": round(short_time, 2),
                    "long": round(long_time, 2),
                    "wall": round(ai_wall_time, 2),
                },
                "processing_times": {
                    "transcript": round(transcript_time, 3),
                    "clean": round(clean_time, 3),
                    "language": round(language_time, 3),
                    "regions": round(region_time, 3),
                },
                "time": round(
                    time.perf_counter()
                    - total_start,
                    2,
                ),
            }

        return {
            "success": False,
            "questions": [],
            "count": 0,
            "cached": False,
            "language": language,
            "error": " | ".join(errors),
            "ai_times": {
                "mcq": round(mcq_time, 2),
                "short": round(short_time, 2),
                "long": round(long_time, 2),
                "wall": round(ai_wall_time, 2),
            },
            "processing_times": {
                "transcript": round(transcript_time, 3),
                "clean": round(clean_time, 3),
                "language": round(language_time, 3),
                "regions": round(region_time, 3),
            },
            "time": round(
                time.perf_counter()
                - total_start,
                2,
            ),
        }

    # ======================================================
    # 8. COMBINE QUESTIONS
    # ======================================================

    questions = (
        mcq.get(
            "questions",
            [],
        )
        + short.get(
            "questions",
            [],
        )
        + long_result.get(
            "questions",
            [],
        )
    )


    # ------------------------------------------------------
    # TARGETED CROSS-TYPE TOPIC FIX
    # ------------------------------------------------------
    # Normal generation is untouched. This runs only if the
    # completed 15-question set repeats a main topic.
    # ------------------------------------------------------
    questions = _repair_cross_type_topics(
        questions,
        regions,
    )


    print("\n========== FINAL QUESTION LANGUAGE DEBUG ==========")

    for i, q in enumerate(questions, start=1):

        print(
            f"Q{i} [{q.get('type', 'unknown')}] "
            f"EnglishQuestion={_english_quiz_text_ok(str(q.get('question', '')))}"
        )

        print(
            "QUESTION:",
            q.get("question", "")
        )

        print(
            "ANSWER:",
            q.get("answer", "")
        )

    print("===================================================\n")

    # ======================================================
    # 9. FINAL COUNT CHECK
    # ======================================================

    if len(
        questions
    ) != EXPECTED_TOTAL:

        return {
            "success": False,
            "questions": questions,
            "count": len(
                questions
            ),
            "cached": False,
            "language": language,
            "error": (
                "Expected "
                f"{EXPECTED_TOTAL} questions "
                "but received "
                f"{len(questions)}."
            ),
            "ai_times": {
                "mcq": round(
                    mcq_time,
                    2,
                ),
                "short": round(
                    short_time,
                    2,
                ),
                "long": round(
                    long_time,
                    2,
                ),
                "wall": round(
                    ai_wall_time,
                    2,
                ),
            },
            "time": round(
                time.perf_counter()
                - total_start,
                2,
            ),
        }

    # ======================================================
    # 10. QUESTION VALIDATION
    # ======================================================

    validation_results = []

    for question in questions:

        validation = (
            validate_question(
                question
            )
        )

        validation_results.append(
            validation
        )

    validator = {
        "valid": all(
            item.get(
                "valid",
                False,
            )
            for item
            in validation_results
        ),
        "results": (
            validation_results
        ),
    }

    if not validator[
        "valid"
    ]:

        validation_errors = []

        for index, item in enumerate(
            validation_results,
            start=1,
        ):

            if item.get(
                "valid",
                False,
            ):
                continue

            for error in item.get(
                "errors",
                [],
            ):

                validation_errors.append(
                    f"Question {index}: "
                    f"{error}"
                )

        return {
            "success": False,
            "questions": questions,
            "count": len(
                questions
            ),
            "cached": False,
            "language": language,
            "validator": validator,
            "error": (
                "Question validation failed: "
                + " | ".join(
                    validation_errors
                )
            ),
            "ai_times": {
                "mcq": round(
                    mcq_time,
                    2,
                ),
                "short": round(
                    short_time,
                    2,
                ),
                "long": round(
                    long_time,
                    2,
                ),
                "wall": round(
                    ai_wall_time,
                    2,
                ),
            },
            "time": round(
                time.perf_counter()
                - total_start,
                2,
            ),
        }

    # ======================================================
    # 11. COVERAGE
    # ======================================================

    coverage = calculate_coverage(
        questions
    )

    # ======================================================
    # 12. UNIVERSAL QUIZ QUALITY
    # ======================================================

    quiz_quality = (
        validate_quiz_quality(
            questions
        )
    )

    if not quiz_quality.get(
        "valid",
        False,
    ):

        return {
            "success": False,
            "questions": questions,
            "count": len(
                questions
            ),
            "cached": False,
            "language": language,
            "validator": validator,
            "coverage": coverage,
            "quiz_quality": (
                quiz_quality
            ),
            "error": (
                "Final quiz failed "
                "quality validation: "
                + " | ".join(
                    quiz_quality.get(
                        "errors",
                        [],
                    )
                )
            ),
            "ai_times": {
                "mcq": round(
                    mcq_time,
                    2,
                ),
                "short": round(
                    short_time,
                    2,
                ),
                "long": round(
                    long_time,
                    2,
                ),
                "wall": round(
                    ai_wall_time,
                    2,
                ),
            },
            "time": round(
                time.perf_counter()
                - total_start,
                2,
            ),
        }



    # ======================================================
    # 13. EVIDENCE GROUNDING
    # ======================================================

    grounding = ground_quiz(
        questions,
        regions,
    )

    if not grounding.get(
        "grounded",
        False,
    ):

        return {
            "success": False,
            "questions": questions,
            "count": len(
                questions
            ),
            "cached": False,
            "language": language,
            "validator": validator,
            "coverage": coverage,
            "quiz_quality": quiz_quality,
            "grounding": grounding,
            "error": (
                "Final quiz failed "
                "source-evidence grounding. "
                f"{grounding.get('grounded_count', 0)} "
                f"of {grounding.get('question_count', 0)} "
                "questions were grounded."
            ),
            "ai_times": {
                "mcq": round(
                    mcq_time,
                    2,
                ),
                "short": round(
                    short_time,
                    2,
                ),
                "long": round(
                    long_time,
                    2,
                ),
                "wall": round(
                    ai_wall_time,
                    2,
                ),
            },
            "time": round(
                time.perf_counter()
                - total_start,
                2,
            ),
        }


    # ======================================================
    # 14. FINAL RESULT
    # ======================================================

    result = {
        "success": True,



        "questions": questions,

        "count": len(
            questions
        ),

        "counts": {
            "mcq": len(
                mcq["questions"]
            ),
            "short": len(
                short["questions"]
            ),
            "long": len(
                long_result[
                    "questions"
                ]
            ),
        },

        "cached": False,
        "grounding": grounding,

        # --------------------------------------------------
        # PROVIDERS
        # --------------------------------------------------

        "providers": {
            "mcq": mcq.get(
                "provider"
            ),
            "short": short.get(
                "provider"
            ),
            "long": long_result.get(
                "provider"
            ),
        },

        # --------------------------------------------------
        # MODELS
        # --------------------------------------------------

        "models": {
            "mcq": mcq.get(
                "model"
            ),
            "short": short.get(
                "model"
            ),
            "long": long_result.get(
                "model"
            ),
        },

        # --------------------------------------------------
        # AI TIMES
        # --------------------------------------------------

        "ai_times": {
            "mcq": round(
                mcq_time,
                2,
            ),
            "short": round(
                short_time,
                2,
            ),
            "long": round(
                long_time,
                2,
            ),
            "wall": round(
                ai_wall_time,
                2,
            ),
        },

        # --------------------------------------------------
        # PROCESSING TIMES
        # --------------------------------------------------

        "processing_times": {
            "transcript": round(
                transcript_time,
                3,
            ),
            "clean": round(
                clean_time,
                3,
            ),
            "language": round(
                language_time,
                3,
            ),
            "regions": round(
                region_time,
                3,
            ),
        },

        # --------------------------------------------------
        # LANGUAGE
        # --------------------------------------------------

        "language": language,

        # --------------------------------------------------
        # VALIDATION
        # --------------------------------------------------

        "validator": validator,

        "coverage": coverage,

        "quiz_quality": (
            quiz_quality
        ),

        "error": None,
    }

    # ======================================================
    # 14. ANALYTICS
    # ======================================================

    result["analytics"] = (
        build_analytics(
            result
        )
    )

    # ======================================================
    # 15. CACHE
    # ======================================================

    cache_saved = save_quiz_cache(
        youtube_url,
        result,
    )

    result["cache_saved"] = (
        cache_saved
    )

    result["time"] = round(
        time.perf_counter()
        - total_start,
        2,
    )

    return result
