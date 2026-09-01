"""
free_batch_question_generator.py
--------------------------------

Generates:
- 5 MCQs
- 5 short-answer questions
- 5 long-answer questions

using only THREE AI calls.

Designed for:
- whole-video coverage
- multilingual transcripts
- free-provider efficiency
- strict JSON validation
- source-evidence grounding
"""

from __future__ import annotations

from json_repair import repair_json

import json
import re

from .ai_provider import AIResult
from .providers.provider_router import (
    generate_with_provider_router,
)


# ==========================================================
# SETTINGS
# ==========================================================

QUESTION_COUNT = 5


# ==========================================================
# BUILD REGION EVIDENCE
# ==========================================================


QUESTION_QUALITY_RULES = '\nFINAL QUESTION QUALITY RULES:\n- Moderate difficulty: require application, prediction, interpretation,\n  comparison, cause/effect, or reasoning when the video supports it.\n- Do not repeat the same main learning target across MCQ, short, and long.\n  Rewording the same fact does not count as a new question.\n- MCQ should primarily test a decision, result, scenario, distinction,\n  or interpretation.\n- Short should primarily test why/how, consequence, explanation, or a\n  small application that is different from the MCQ target.\n- Long should primarily test a deeper process, comparison, multi-step\n  reasoning, or broader application that is different from both.\n- Use only information supported by the supplied video evidence.\n- Never invent a concept merely to create variety.\n'
def build_region_evidence(
    regions: list[dict],
    context_key: str = "context",
) -> str:
    """
    Select exactly QUESTION_COUNT representative regions
    spread across the ENTIRE video.

    The video itself is not limited to 5 regions.
    Only the number of questions generated in this batch
    is limited to QUESTION_COUNT.
    """

    if not regions:
        return ""

    total_regions = len(regions)

    # --------------------------------------------------
    # SELECT REPRESENTATIVE REGIONS ACROSS FULL VIDEO
    # --------------------------------------------------

    if total_regions <= QUESTION_COUNT:

        selected_regions = regions

    else:

        selected_indexes = []

        for i in range(QUESTION_COUNT):

            position = round(
                i * (total_regions - 1)
                / (QUESTION_COUNT - 1)
            )

            selected_indexes.append(
                position
            )

        selected_regions = [
            regions[index]
            for index in selected_indexes
        ]

    # --------------------------------------------------
    # BUILD EVIDENCE
    # --------------------------------------------------

    parts = []

    for index, region in enumerate(
        selected_regions,
        start=1,
    ):

        context = str(
            region.get(
                context_key,
                "",
            )
        ).strip()

        # Safe fallback
        if not context:

            context = str(
                region.get(
                    "context",
                    "",
                )
            ).strip()

        if not context:
            continue

        parts.append(
            f"""
[VIDEO REGION {index}]
{context}
""".strip()
        )

    return "\n\n".join(
        parts
    )

# ==========================================================
# COMMON PROMPT
# ==========================================================

def _common_instructions(
    evidence: str,
) -> str:

    return f""" + '\nQUESTION QUALITY RULES — APPLY TO THIS BATCH:\n1. MODERATE DIFFICULTY: avoid trivial definition/one-step recall questions.\n   Prefer application, prediction, interpretation, comparison, cause/effect,\n   or reasoning that is directly supported by the evidence.\n2. DISTINCT LEARNING TARGET: each question must test a meaningfully different\n   learning target. Changing only the wording or answer format does NOT make\n   a new question.\n3. AVOID CROSS-TYPE REPEATS: MCQ, short-answer, and long-answer questions\n   should not ask about the same main fact, operator, expression, example,\n   value, definition, or property when another supported concept/aspect exists.\n4. USE DIFFERENT ASPECTS: when the same region contains several ideas, spread\n   those ideas across the question types instead of asking all three types\n   about the most obvious idea.\n5. DO NOT INVENT CONTENT: diversity must come only from concepts actually\n   present in the supplied evidence.\n'
You are creating an educational quiz directly from
a video lesson.

The lesson evidence may contain:
- English
- Telugu
- Hindi
- Tamil
- Kannada
- Malayalam
- another language
- mixed-language teaching
- English technical terms written in another script

Understand the MEANING of the lesson.

IMPORTANT WHOLE-VIDEO COVERAGE RULE:

There are 5 labelled VIDEO REGIONS.

Create exactly ONE question from EACH region.

Therefore:

Question 1 -> VIDEO REGION 1
Question 2 -> VIDEO REGION 2
Question 3 -> VIDEO REGION 3
Question 4 -> VIDEO REGION 4
Question 5 -> VIDEO REGION 5

Do not create multiple questions from the same region.

Questions must test useful educational concepts actually
taught in that region.

Do NOT ask questions about:
- the teacher
- the speaker
- the video itself
- greetings
- motivational speech
- instructions to students
- filler conversation

Do not ask vague questions such as:
"What is the main concept?"

STRICT OUTPUT LANGUAGE:

All generated quiz content MUST be in English.

This applies to:
- questions
- answers
- MCQ options
- explanations
- labels inside generated quiz content

NEVER generate questions, answers, or MCQ options in Hindi,
Telugu, Tamil, Kannada, Malayalam, Bengali, Gujarati, Arabic,
or any other non-English script.

The source evidence may remain in its original language,
but the QUESTION, ANSWER, and OPTIONS must be English.

If the lesson is Hindi or multilingual, understand the lesson
and translate the educational meaning into clear English.

Do NOT copy the source language into the question, answer,
or MCQ options.

Do not invent unsupported concepts.
QUESTION WRITING QUALITY RULES:

Every question must be understandable when shown
to the student by itself.

Never refer to the source material using phrases such as:

- "in the provided code"
- "in the code above"
- "in the example above"
- "in the previous example"
- "as shown above"
- "in the provided dataset"
- "in the video"
- "according to the video"
- "according to the speaker"
- "according to the teacher"

Do NOT mention the teacher, speaker, video,
transcript, dataset, example, or source in the question.

Instead, ask directly about the actual concept,
fact, process, principle, calculation, or application
taught in the assigned VIDEO REGION.

The question must contain enough information to be
understood independently.

MCQ QUESTIONS:
- Must be clear and specific.
- Must end with a question mark.
- Must have exactly 4 meaningful and distinct options.
- Only one option should be clearly correct.
- Distractors must be plausible.
- Do not use "all of the above" or "none of the above"
  unless specifically required by the lesson.

SHORT-ANSWER QUESTIONS:
- Must be clear and specific.
- Must end with a question mark.
- Should normally require a concise explanation,
  definition, relationship, reason, or calculation.
- Avoid extremely broad prompts such as
  "Explain everything" or "Describe everything."
- Do not ask simple yes/no questions unless the lesson
  specifically requires that distinction.

LONG-ANSWER QUESTIONS:
- Must require a meaningful multi-part explanation,
  derivation, comparison, application, or detailed reasoning.
- Avoid questions that can be answered with one word
  or one short sentence.
- Do not begin with weak prompts such as:
  "What is...",
  "Who is...",
  "Name the...",
  "State the...",
  or "Define..."
  when a deeper question can be created.
- The question should still be understandable
  independently.

For ALL question types:

Before returning a question, mentally check:

1. Can a student understand this question without seeing
   the transcript or video?
2. Does it directly test something actually taught
   in the assigned region?
3. Does it avoid referring to the source or surrounding
   context?
4. Is it specific rather than vague?
5. Is the answer supported by the supplied evidence?

If any answer is NO, generate a different question.


EVIDENCE REQUIREMENT:

Every generated question MUST contain an
"evidence" field.

The evidence must:
- be copied directly from the assigned VIDEO REGION
- remain in the ORIGINAL source language
- NOT be translated
- NOT be paraphrased
- contain source text supporting the question and answer
- preferably contain about 8 to 40 words
- come only from that question's assigned region

For Telugu-English, Hindi-English, Tamil-English,
Kannada-English, Malayalam-English, or any other
mixed-language lecture, preserve the source excerpt
exactly as it appears in the supplied region.

The evidence field is NOT an explanation.

It is a short SOURCE EXCERPT.

Never invent evidence.

If you cannot find evidence supporting a question,
create a different question that is supported.

Return valid JSON only.

Do not use markdown code fences.


LESSON EVIDENCE:

{evidence}
""".strip()


# ==========================================================
# QUESTION QUALITY GUARD
# ==========================================================

# ==========================================================
# ENGLISH QUIZ TEXT GUARD
# ==========================================================

def _contains_non_english_script(
    value: str,
) -> bool:

    text = str(value)

    for char in text:

        code = ord(char)

        # Devanagari
        if 0x0900 <= code <= 0x097F:
            return True

        # Telugu
        if 0x0C00 <= code <= 0x0C7F:
            return True

        # Tamil
        if 0x0B80 <= code <= 0x0BFF:
            return True

        # Kannada
        if 0x0C80 <= code <= 0x0CFF:
            return True

        # Malayalam
        if 0x0D00 <= code <= 0x0D7F:
            return True

        # Bengali
        if 0x0980 <= code <= 0x09FF:
            return True

        # Gujarati
        if 0x0A80 <= code <= 0x0AFF:
            return True

        # Gurmukhi
        if 0x0A00 <= code <= 0x0A7F:
            return True

        # Arabic script
        if 0x0600 <= code <= 0x06FF:
            return True

    return False


def _english_quiz_text_ok(
    value: str,
) -> bool:

    if not isinstance(
        value,
        str,
    ):
        return False

    if not value.strip():
        return False

    return not _contains_non_english_script(
        value
    )

def _normalize_quality_text(value: str) -> str:

    return " ".join(
        str(value)
        .strip()
        .casefold()
        .split()
    )


def _question_quality_ok(
    item: dict,
    question_type: str,
) -> bool:

    question = str(
        item.get(
            "question",
            "",
        )
    ).strip()

    answer = str(
        item.get(
            "answer",
            "",
        )
    ).strip()

    evidence = str(
        item.get(
            "evidence",
            "",
        )
    ).strip()
    
    # ------------------------------------------------------
    # ENGLISH OUTPUT REQUIREMENT
    # ------------------------------------------------------

    if not _english_quiz_text_ok(
        question
    ):
        return False

    if not _english_quiz_text_ok(
        answer
    ):
        return False


    # ------------------------------------------------------
    # BASIC READABILITY
    # ------------------------------------------------------

    if len(question) < 12:
        return False

    if len(question) > 500:
        return False

    if len(answer) < 1:
        return False

    if len(evidence) < 8:
        return False


    # Questions should normally be actual questions.

    # MCQ and short-answer questions should normally
    # be written as direct questions.
    #
    # Long-answer exam prompts may correctly use
    # imperative forms such as:
    # "Explain..."
    # "Compare..."
    # "Describe..."
    # and therefore may end with a period.

    if (
        question_type
        in {
            "mcq",
            "short",
        }
        and not question.endswith("?")
    ):
        return False


    normalized_question = (
        _normalize_quality_text(
            question
        )
    )


    # ------------------------------------------------------
    # VAGUE / VIDEO-META QUESTIONS
    # ------------------------------------------------------

    bad_phrases = (
        "what is the main concept",
        "what is discussed in the video",
        "what does the video discuss",
        "what does the teacher say",
        "what does the speaker say",
        "according to the speaker",
        "according to the teacher",
        "in this video",
        "in the video",
        "the instructor",
        "the lecturer",
    )

    for phrase in bad_phrases:

        if phrase in normalized_question:
            return False


    # ------------------------------------------------------
    # CONTEXT-DEPENDENT WORDING
    #
    # A quiz question should make sense when displayed
    # independently to the student.
    # ------------------------------------------------------

    weak_context_phrases = (
        "in the provided dataset",
        "in the given dataset",
        "in the above example",
        "in the example above",
        "as shown above",
        "in the previous example",
        "in the previous code",
        "in the code above",
        "in the provided code",
    )

    for phrase in weak_context_phrases:

        if phrase in normalized_question:
            return False


    # ------------------------------------------------------
    # SHORT / LONG DEPTH
    # ------------------------------------------------------

    if question_type == "short":

        # Avoid extremely broad prompts.
        broad_short = (
            "explain everything",
            "describe everything",
            "write everything",
        )

        for phrase in broad_short:

            if phrase in normalized_question:
                return False


    if question_type == "long":

        # Long questions should normally require more than
        # one-word recognition.
        weak_long_starts = (
            "what is ",
            "who is ",
            "name the ",
            "state the ",
            "define ",
        )

        if normalized_question.startswith(
            weak_long_starts
        ):
            return False


    # ------------------------------------------------------
    # MCQ OPTION QUALITY
    # ------------------------------------------------------

    if question_type == "mcq":

        options = item.get(
            "options",
            [],
        )

        if not isinstance(
            options,
            list,
        ):
            return False

        if len(options) != 4:
            return False
        
        if any(
            not _english_quiz_text_ok(option)
            for option in options
        ):
            return False
        

        normalized_options = [
            _normalize_quality_text(
                option
            )
            for option in options
        ]

        if len(
            set(normalized_options)
        ) != 4:
            return False


        # Reject empty/useless distractors.

        bad_options = {
            "",
            "none",
            "n/a",
            "na",
        }

        if any(
            option in bad_options
            for option in normalized_options
        ):
            return False


    return True

# ==========================================================
# DUPLICATE QUESTION GUARD
# ==========================================================

def _question_words(text: str) -> set[str]:

    normalized = (
        _normalize_quality_text(
            text
        )
    )

    words = {
        word.strip(
            ".,!?;:()[]{}\"'"
        )
        for word in normalized.split()
    }

    # Remove very common question words because they
    # should not make two questions look similar.
    stop_words = {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "what",
        "why",
        "how",
        "when",
        "where",
        "which",
        "who",
        "does",
        "do",
        "did",
        "can",
        "could",
        "would",
        "should",
        "in",
        "on",
        "of",
        "to",
        "for",
        "from",
        "with",
        "and",
        "or",
        "by",
        "using",
        "used",
    }

    return {
        word
        for word in words
        if word
        and word not in stop_words
        and len(word) > 1
    }


def _questions_too_similar(
    first: str,
    second: str,
) -> bool:

    first_words = _question_words(
        first
    )

    second_words = _question_words(
        second
    )

    if not first_words:
        return False

    if not second_words:
        return False

    intersection = (
        first_words
        &
        second_words
    )

    union = (
        first_words
        |
        second_words
    )

    if not union:
        return False

    jaccard = (
        len(intersection)
        /
        len(union)
    )

    smaller = min(
        len(first_words),
        len(second_words),
    )

    containment = (
        len(intersection)
        /
        smaller
    )

    # High overall similarity OR one question largely
    # contains the meaningful vocabulary of the other.
    return (
        jaccard >= 0.72
        or containment >= 0.85
    )


def _batch_has_duplicate_questions(
    questions: list[dict],
) -> bool:

    for first_index in range(
        len(questions)
    ):

        for second_index in range(
            first_index + 1,
            len(questions),
        ):

            first = questions[
                first_index
            ]

            second = questions[
                second_index
            ]

            if _questions_too_similar(
                str(
                    first.get(
                        "question",
                        "",
                    )
                ),
                str(
                    second.get(
                        "question",
                        "",
                    )
                ),
            ):

                print(
                    "Duplicate-like questions "
                    "detected:"
                )

                print(
                    " -",
                    first.get(
                        "question",
                        "",
                    ),
                )

                print(
                    " -",
                    second.get(
                        "question",
                        "",
                    ),
                )

                return True

    return False



def _extract_json_object(text: str) -> str:
    """
    Extract the first complete top-level JSON object while respecting
    quoted strings and escaped characters. This handles harmless
    ```json ... ``` wrappers without changing the JSON itself.
    """
    value = str(text or "").strip()

    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.I)
        value = re.sub(r"\s*```$", "", value).strip()

    start = value.find("{")
    if start < 0:
        return value

    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(value)):
        char = value[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return value[start:index + 1]

    # Leave an incomplete response untouched so the normal error path
    # reports it instead of inventing missing content.
    return value[start:]


# ==========================================================
# PARSE
# ==========================================================

def _parse_questions(
    result: AIResult,
    question_type: str,
) -> dict:

    if not result.success:

        return {
            "success": False,
            "questions": [],
            "count": 0,
            "provider": result.provider,
            "model": result.model,
            "error": result.error,
        }

    # ======================================================
    # JSON PARSING
    # ======================================================

    try:

        json_text = _extract_json_object(
            result.text
        )

        # First try normal JSON.
        try:

            data = json.loads(
                json_text
            )

        except json.JSONDecodeError:

            # Gemini sometimes returns small JSON formatting
            # errors such as an unterminated string or missing
            # comma. Repair the JSON locally instead of failing
            # the entire quiz batch.

            data = repair_json(
                json_text,
                return_objects=True,
            )

    except Exception as exc:

        return {
            "success": False,
            "questions": [],
            "count": 0,
            "provider": result.provider,
            "model": result.model,
            "error": (
                f"Invalid JSON: {exc}"
            ),
        }

    if not isinstance(
        data,
        dict,
    ):
    

        return {
            "success": False,
            "questions": [],
            "count": 0,
            "provider": result.provider,
            "model": result.model,
            "error": (
                "AI response must be "
                "a JSON object."
            ),
        }

    questions = data.get(
        "questions",
        [],
    )

    if not isinstance(
        questions,
        list,
    ):

        questions = []

    valid = []

    for item in questions:

        if not isinstance(
            item,
            dict,
        ):
            continue

        region = item.get(
            "region"
        )

        question = item.get(
            "question"
        )

        answer = item.get(
            "answer"
        )

        evidence = item.get(
            "evidence"
        )

        # --------------------------------------------------
        # COMMON VALIDATION
        # --------------------------------------------------

        if (
            region not in {
                1,
                2,
                3,
                4,
                5,
            }
            or not isinstance(
                question,
                str,
            )
            or not question.strip()
            or not isinstance(
                answer,
                str,
            )
            or not answer.strip()
            or not isinstance(
                evidence,
                str,
            )
            or not evidence.strip()
        ):
            continue

        # Normalize whitespace around generated values.

        item["question"] = (
            question.strip()
        )

        item["answer"] = (
            answer.strip()
        )

        item["evidence"] = (
            evidence.strip()
        )
        
        # --------------------------------------------------
        # FINAL ENGLISH OUTPUT GUARD
        # --------------------------------------------------

        if not _english_quiz_text_ok(
            item["question"]
        ):
            print(
                "Rejected non-English question "
                f"from region {region}"
            )
            continue

        if not _english_quiz_text_ok(
            item["answer"]
        ):
            print(
                "Rejected non-English answer "
                f"from region {region}"
            )
            continue

        # --------------------------------------------------
        # MCQ VALIDATION
        # --------------------------------------------------

        if question_type == "mcq":

            options = item.get(
                "options",
                [],
            )

            if (
                not isinstance(
                    options,
                    list,
                )
                or len(options) != 4
                or not all(
                    isinstance(
                        option,
                        str,
                    )
                    and option.strip()
                    for option in options
                )
            ):
                continue

            options = [
                option.strip()
                for option in options
            ]

            # No duplicate MCQ options.

            if len(
                set(options)
            ) != 4:
                continue
            
            
            # Correct answer should match one option.
            #
            # Free models may occasionally return harmless
            # case/whitespace differences. Normalize only for
            # matching, but preserve the original option text.

            answer_normalized = (
                item["answer"]
                .strip()
                .casefold()
            )

            matched_option = None

            for option in options:

                if (
                    option
                    .strip()
                    .casefold()
                    == answer_normalized
                ):

                    matched_option = option
                    break

            if matched_option is None:
                continue

            # Store the exact option text as the answer so
            # downstream MCQ validators always see an exact match.

            item["answer"] = (
                matched_option
            )

            item["options"] = (
                options
            )


        # --------------------------------------------------
        # LOCAL QUESTION QUALITY
        # --------------------------------------------------

        if not _question_quality_ok(
            item,
            question_type,
        ):

            print(
                "Rejected low-quality "
                f"{question_type} question "
                f"from region {region}: "
                f"{item['question']}"
            )

            continue


        # --------------------------------------------------
        # TYPE
        # --------------------------------------------------

        item["type"] = (
            question_type
        )

        valid.append(
            item
        )

    # ======================================================
    # EXACTLY ONE QUESTION PER REGION
    # ======================================================

    region_numbers = [
        item["region"]
        for item in valid
    ]

    coverage_ok = (
        len(valid)
        == QUESTION_COUNT
        and set(
            region_numbers
        )
        == {
            1,
            2,
            3,
            4,
            5,
        }
        and len(
            region_numbers
        )
        == len(
            set(region_numbers)
        )
    )

    if not coverage_ok:
        
        print(
        "\n--- BATCH VALIDATION DEBUG ---"
        )

        print(
            "Question type:",
            question_type,
        )

        print(
            "Raw question count:",
            len(questions),
        )

        print(
            "Valid question count:",
            len(valid),
        )

        print(
            "Valid regions:",
            region_numbers,
        )

        print(
            "--- END DEBUG ---\n"
        )

        return {
            "success": False,
            "questions": valid,
            "count": len(valid),
            "provider": result.provider,
            "model": result.model,
            "error": (
                "Question batch failed "
                "question structure or "
                "whole-video region/evidence "
                "validation."
            ),
        }

    valid.sort(
        key=lambda item: (
            item["region"]
        )
    )


    # ======================================================
    # DUPLICATE QUALITY CHECK
    # ======================================================

    if _batch_has_duplicate_questions(
        valid
    ):
    

        return {
            "success": False,
            "questions": valid,
            "count": len(valid),
            "provider": result.provider,
            "model": result.model,
            "error": (
                "Question batch contains "
                "duplicate or highly similar "
                "questions."
            ),
        }




    return {
        "success": True,
        "questions": valid,
        "count": len(valid),
        "provider": result.provider,
        "model": result.model,
        "error": None,
    }


# ==========================================================
# MCQ
# ==========================================================

def generate_mcq_batch(
    regions: list[dict],
) -> dict:

    evidence = build_region_evidence(
        regions,
        context_key="mcq_context",
    )

    prompt = (
        _common_instructions(
            evidence
        ) + QUESTION_QUALITY_RULES
        + """
        
        

CRITICAL LANGUAGE RULE — HIGHEST PRIORITY:

The quiz output language is ENGLISH ONLY.

The source evidence may be Hindi, Telugu, Tamil,
Kannada, Malayalam, or another language.

DO NOT copy the source language into the question.

For every MCQ:

- "question" MUST be English.
- Every "options" value MUST be English.
- "answer" MUST be English.
- Use normal English/Latin alphabet.
- NEVER write the question in Hindi.
- NEVER write an option in Hindi.
- NEVER write the answer in Hindi.
- NEVER translate the question into the source language.

ONLY the "evidence" field may contain the original
source language.

Example:

{
  "question": "What is the main function of reproduction?",
  "options": [
    "Producing new organisms",
    "Producing energy",
    "Breaking down food",
    "Removing waste"
  ],
  "answer": "Producing new organisms",
  "evidence": "ORIGINAL SOURCE TEXT HERE"
}

Even when the supplied evidence is entirely Hindi,
the question, options, and answer MUST remain English.

If you cannot create an English question supported by
a region, create a different English question from
that same region.



Create exactly 5 MULTIPLE-CHOICE questions.

Return exactly this JSON structure:

LANGUAGE REQUIREMENT — VERY IMPORTANT:

The quiz is ENGLISH ONLY.

The question MUST be written entirely in English.

ALL FOUR OPTIONS MUST be written entirely in English.

The answer MUST be written entirely in English.

Do NOT translate the quiz into Hindi, Telugu, Tamil,
Kannada, Malayalam, or any other language.

The source evidence may contain another language,
but NEVER copy non-English source text into the
question, options, or answer.

If the source is Hindi or another language, understand
its meaning and formulate the question, options, and
answer in clear English.

Do not use Devanagari or any other non-English script
in question, options, or answer.

{
  "questions": [
    {
      "region": 1,
      "question": "...",
      "options": [
        "...",
        "...",
        "...",
        "..."
      ],
      "answer": "...",
      "evidence": "exact source excerpt from VIDEO REGION 1"
    },
    {
      "region": 2,
      "question": "...",
      "options": [
        "...",
        "...",
        "...",
        "..."
      ],
      "answer": "...",
      "evidence": "exact source excerpt from VIDEO REGION 2"
    },
    {
      "region": 3,
      "question": "...",
      "options": [
        "...",
        "...",
        "...",
        "..."
      ],
      "answer": "...",
      "evidence": "exact source excerpt from VIDEO REGION 3"
    },
    {
      "region": 4,
      "question": "...",
      "options": [
        "...",
        "...",
        "...",
        "..."
      ],
      "answer": "...",
      "evidence": "exact source excerpt from VIDEO REGION 4"
    },
    {
      "region": 5,
      "question": "...",
      "options": [
        "...",
        "...",
        "...",
        "..."
      ],
      "answer": "...",
      "evidence": "exact source excerpt from VIDEO REGION 5"
    }
  ]
}

Requirements:

- exactly 5 questions
- exactly one question per video region
- exactly 4 options per question
- exactly one correct answer
- answer must exactly match one option
- evidence must be copied directly from the assigned region
- evidence must support both the question and correct answer

QUESTION DIVERSITY ROLE:

You are generating the MULTIPLE-CHOICE layer of a
three-level quiz.

The same five video regions are also being used
independently to create short-answer and long-answer
questions.

For MCQs, prefer concepts that can be tested clearly
through recognition, identification, interpretation,
or choosing the correct result.

Prefer:

- identifying a concept
- recognizing correct syntax or behavior
- choosing the correct result
- distinguishing between clearly different choices
- identifying the purpose of a feature
- selecting the correct statement

Avoid forcing deep explanations into an MCQ.

Distractors must be plausible but clearly incorrect
according to the assigned region.

Do not create trick questions.

Do not use options that differ only by meaningless
wording.

Do not introduce outside knowledge merely to make
the options different.

The question and correct answer must be fully supported
by the assigned VIDEO REGION.

Evidence grounding has higher priority than diversity.
"""
    )

    # ------------------------------------------------------
    # INITIAL GENERATION
    # ------------------------------------------------------

    result = generate_with_provider_router(
        prompt=prompt,
        task="mcq_batch",
        json_mode=True,
        max_tokens=2500,
        temperature=0.1,
    )

    parsed = _parse_questions(
        result,
        "mcq",
    )

    if parsed.get("success"):
        return parsed

    valid_questions = parsed.get(
        "questions",
        [],
    )

    valid_regions = {
        item.get("region")
        for item in valid_questions
        if isinstance(item, dict)
    }

    expected_regions = {
        1,
        2,
        3,
        4,
        5,
    }

    missing_regions = sorted(
        expected_regions
        - valid_regions
    )

    # ------------------------------------------------------
    # REPAIR ONLY WHEN REGIONS ARE MISSING
    # ------------------------------------------------------

    if not missing_regions:

        return parsed

    # ------------------------------------------------------
    # BUILD EVIDENCE ONLY FOR MISSING REGIONS
    # ------------------------------------------------------

    repair_parts = []

    for region_number in missing_regions:

        index = (
            region_number - 1
        )

        if (
            index < 0
            or index >= len(regions)
        ):
            continue

        region = regions[index]

        context = str(
            region.get(
                "mcq_context",
                "",
            )
        ).strip()

        if not context:

            context = str(
                region.get(
                    "context",
                    "",
                )
            ).strip()

        if not context:
            continue

        repair_parts.append(
            f"""
[VIDEO REGION {region_number}]
{context}
""".strip()
        )

    if not repair_parts:

        return parsed

    repair_evidence = "\n\n".join(
        repair_parts
    )

    repair_prompt = f"""
You are repairing a failed educational MCQ batch.
IMPORTANT LANGUAGE REQUIREMENT:

The source evidence may be in Hindi or another language.

ALL GENERATED QUIZ CONTENT MUST BE IN ENGLISH.

This applies to:
- question
- all four options
- answer

Do NOT generate Hindi, Telugu, Tamil, Kannada, Malayalam,
Bengali, Gujarati, Arabic, or any other non-English script
in the question, options, or answer.

Understand the source evidence and express its educational
meaning in clear English.

ONLY the evidence field may remain in the original source
language.

The original batch was supposed to contain one valid
MCQ for each of VIDEO REGIONS 1 through 5.

Some questions failed validation.

You must create ONLY the missing regions listed below.

MISSING REGIONS:

{", ".join(
    str(region)
    for region in missing_regions
)}

Do NOT create questions for any other region.

Do NOT reuse questions from another region.

Do NOT mention the video, transcript, teacher, speaker,
dataset, or source in the question.

The question must be independently understandable.

Use only the supplied evidence.

LANGUAGE REQUIREMENT:

The question, all four options, and answer MUST be
ENGLISH ONLY.

Do NOT write the question, options, or answer in Hindi,
Telugu, Tamil, Kannada, Malayalam, or any other language.

The evidence is the ONLY field that may remain in the
original source language.

If the evidence is Hindi, understand it and create the
question, options, and answer in English.

Never copy non-English script into the question,
options, or answer.

For every missing region create:

- exactly one MCQ
- exactly four distinct options
- exactly one correct answer
- answer must exactly match one option
- question must end with ?
- evidence must be a direct source excerpt

Return valid JSON only.

Return exactly:

{{
  "questions": [
    {{
      "region": 1,
      "question": "...",
      "options": [
        "...",
        "...",
        "...",
        "..."
      ],
      "answer": "...",
      "evidence": "..."
    }}
  ]
}}

Only include the requested missing regions.

MISSING REGION EVIDENCE:

{repair_evidence}
""".strip()

    # ------------------------------------------------------
    # ONE REPAIR CALL ONLY
    # ------------------------------------------------------

    repair_result = generate_with_provider_router(
        prompt=repair_prompt,
        task="mcq_region_repair",
        json_mode=True,
        max_tokens=1800,
        temperature=0.1,
    )

    repair_parsed = _parse_questions(
        repair_result,
        "mcq",
    )

    repaired_questions = repair_parsed.get(
        "questions",
        [],
    )

    # ------------------------------------------------------
    # COMBINE VALID ORIGINAL + REPAIRED
    # ------------------------------------------------------

    combined = []

    used_regions = set()

    for item in valid_questions:

        region = item.get(
            "region"
        )

        if region in used_regions:
            continue

        used_regions.add(
            region
        )

        combined.append(
            item
        )

    for item in repaired_questions:

        region = item.get(
            "region"
        )

        if region in used_regions:
            continue

        used_regions.add(
            region
        )

        combined.append(
            item
        )

    combined.sort(
        key=lambda item: (
            item.get(
                "region",
                999,
            )
        )
    )

    # ------------------------------------------------------
    # FINAL COVERAGE CHECK
    # ------------------------------------------------------

    final_regions = {
        item.get(
            "region"
        )
        for item in combined
    }

    if (
        len(combined) == QUESTION_COUNT
        and final_regions == expected_regions
    ):

        # Preserve the same provider/model information
        # style used by the normal successful result.

        return {
            "success": True,
            "questions": combined,
            "count": len(combined),
            "provider": (
                repair_result.provider
                or result.provider
            ),
            "model": (
                repair_result.model
                or result.model
            ),
            "error": None,
        }

    # ------------------------------------------------------
    # REPAIR ALSO FAILED
    # ------------------------------------------------------

    return {
        "success": False,
        "questions": combined,
        "count": len(combined),
        "provider": (
            repair_result.provider
            or result.provider
        ),
        "model": (
            repair_result.model
            or result.model
        ),
        "error": (
            "MCQ generation could not produce "
            "one valid question for every video region."
        ),
    }




# ==========================================================
# SHORT
# ==========================================================

def generate_short_batch(
    regions: list[dict],
) -> dict:

    evidence = build_region_evidence(
        regions,
        context_key="short_context",
    )

    prompt = (
        _common_instructions(
            evidence
        )
        + """
        
Create exactly 5 SHORT-ANSWER questions.

A student should normally answer each in approximately
1 to 3 sentences.

Return exactly this JSON structure:

{
  "questions": [
    {
      "region": 1,
      "question": "...",
      "answer": "...",
      "evidence": "exact source excerpt from VIDEO REGION 1"
    },
    {
      "region": 2,
      "question": "...",
      "answer": "...",
      "evidence": "exact source excerpt from VIDEO REGION 2"
    },
    {
      "region": 3,
      "question": "...",
      "answer": "...",
      "evidence": "exact source excerpt from VIDEO REGION 3"
    },
    {
      "region": 4,
      "question": "...",
      "answer": "...",
      "evidence": "exact source excerpt from VIDEO REGION 4"
    },
    {
      "region": 5,
      "question": "...",
      "answer": "...",
      "evidence": "exact source excerpt from VIDEO REGION 5"
    }
  ]
}

Requirements:

- exactly 5 questions
- exactly one question per video region
- concise factual or conceptual answers
- questions should test understanding, not trivia
- evidence must be copied directly from the assigned region
- evidence must support both the question and answer
- question, answer, and evidence must be non-empty
- question must end with ?
- return JSON only

QUESTION DIVERSITY ROLE:

You are generating the SHORT-ANSWER layer of a
three-level quiz.

The same five video regions are also being used
independently to create MCQ and long-answer questions.

Therefore, for each region, do NOT automatically choose
the most obvious definition or recognition fact.

For short-answer questions, prefer:

- explaining why something happens
- describing the purpose of a concept
- applying a concept to a small situation
- explaining a result
- distinguishing closely related ideas
- describing how something is used
- concise cause-and-effect reasoning

Avoid simple recognition questions when the region
contains enough evidence for a more meaningful
understanding question.

BAD:
"What is a variable?"

BETTER:
"How does changing a variable's value affect the
result of a later calculation?"

BAD:
"What does += mean?"

BETTER:
"How does += change the current value of a variable?"

The question must still be answerable ONLY from its
assigned region.

Never introduce outside knowledge merely to make
the question different.

Evidence grounding has higher priority than diversity.

IMPORTANT LANGUAGE REQUIREMENT:

The quiz output must be ENGLISH ONLY.

The source evidence may be Hindi, Telugu, Tamil,
Kannada, Malayalam, or another language.

The question and answer MUST be written in English.

ONLY the evidence field may contain the original
source language.

Return valid JSON only.
"""
    )

    # ------------------------------------------------------
    # INITIAL GENERATION
    # ------------------------------------------------------

    result = generate_with_provider_router(
        prompt=prompt,
        task="short_batch",
        json_mode=True,
        max_tokens=1300,
        temperature=0.1,
    )

    parsed = _parse_questions(
        result,
        "short",
    )

    if parsed.get("success"):
        return parsed

    # ------------------------------------------------------
    # FIND MISSING REGIONS
    # ------------------------------------------------------

    valid_questions = parsed.get(
        "questions",
        [],
    )

    valid_regions = {
        item.get("region")
        for item in valid_questions
        if isinstance(item, dict)
    }

    expected_regions = {
        1,
        2,
        3,
        4,
        5,
    }

    missing_regions = sorted(
        expected_regions
        - valid_regions
    )

    # If the problem was not missing coverage,
    # preserve the original error.
    if not missing_regions:
        return parsed

    print(
        "[SHORT REPAIR] Missing regions:",
        missing_regions,
    )

    # ------------------------------------------------------
    # BUILD EVIDENCE ONLY FOR MISSING REGIONS
    # ------------------------------------------------------

    repair_parts = []

    for region_number in missing_regions:

        index = region_number - 1

        if (
            index < 0
            or index >= len(regions)
        ):
            continue

        region = regions[index]

        context = str(
            region.get(
                "short_context",
                "",
            )
        ).strip()

        if not context:
            context = str(
                region.get(
                    "context",
                    "",
                )
            ).strip()

        if not context:
            continue

        repair_parts.append(
            f"""
[VIDEO REGION {region_number}]
{context}
""".strip()
        )

    if not repair_parts:
        return parsed

    repair_evidence = "\n\n".join(
        repair_parts
    )

    # ------------------------------------------------------
    # REPAIR PROMPT
    # ------------------------------------------------------

    repair_prompt = f"""
You are repairing a failed educational SHORT-ANSWER batch.

The original batch was supposed to contain exactly
one valid short-answer question for each of VIDEO
REGIONS 1 through 5.

Some questions failed validation.

Create ONLY the missing regions listed below.

MISSING REGIONS:

{", ".join(
    str(region)
    for region in missing_regions
)}

IMPORTANT:

- Create exactly ONE question for each missing region.
- Do NOT create questions for other regions.
- Do NOT repeat an existing question.
- Use ONLY the supplied evidence.
- Do NOT invent information.
- The question must be independently understandable.
- The answer must directly answer the question.
- Evidence must directly support both the question and answer.
- Evidence must be copied directly from the supplied region.
- The question must end with ?.
- Answer should normally be 1 to 3 sentences.

LANGUAGE REQUIREMENT:

The question MUST be English.
The answer MUST be English.

The evidence field may remain in the original
source language.

Do NOT generate Hindi, Telugu, Tamil, Kannada,
Malayalam, Bengali, Gujarati, Arabic, or other
non-English script in the question or answer.

Return JSON only.

Return exactly:

{{
  "questions": [
    {{
      "region": 1,
      "question": "...",
      "answer": "...",
      "evidence": "..."
    }}
  ]
}}

Only include the requested missing regions.

MISSING REGION EVIDENCE:

{repair_evidence}
""".strip()

    # ------------------------------------------------------
    # ONE REPAIR CALL ONLY
    # ------------------------------------------------------

    repair_result = generate_with_provider_router(
        prompt=repair_prompt,
        task="short_region_repair",
        json_mode=True,
        max_tokens=700,
        temperature=0.1,
    )

    repair_parsed = _parse_questions(
        repair_result,
        "short",
    )

    repaired_questions = repair_parsed.get(
        "questions",
        [],
    )

    # ------------------------------------------------------
    # COMBINE ORIGINAL + REPAIRED
    # ------------------------------------------------------

    combined = []
    used_regions = set()

    for item in valid_questions:

        region = item.get(
            "region"
        )

        if region in used_regions:
            continue

        used_regions.add(
            region
        )

        combined.append(
            item
        )

    for item in repaired_questions:

        region = item.get(
            "region"
        )

        if region in used_regions:
            continue

        used_regions.add(
            region
        )

        combined.append(
            item
        )

    combined.sort(
        key=lambda item: item.get(
            "region",
            999,
        )
    )

    # ------------------------------------------------------
    # FINAL COVERAGE CHECK
    # ------------------------------------------------------

    final_regions = {
        item.get(
            "region"
        )
        for item in combined
    }

    if (
        len(combined) == QUESTION_COUNT
        and final_regions == expected_regions
    ):
        print(
            "[SHORT REPAIR] Successfully recovered missing regions."
        )

        return {
            "success": True,
            "questions": combined,
            "count": len(combined),
            "provider": (
                repair_result.provider
                or result.provider
            ),
            "model": (
                repair_result.model
                or result.model
            ),
            "error": None,
        }

    # ------------------------------------------------------
    # REPAIR FAILED
    # ------------------------------------------------------

    print(
        "[SHORT REPAIR] Repair failed.",
        "Final regions:",
        sorted(final_regions),
    )

    return {
        "success": False,
        "questions": combined,
        "count": len(combined),
        "provider": (
            repair_result.provider
            or result.provider
        ),
        "model": (
            repair_result.model
            or result.model
        ),
        "error": (
            "Short-answer generation could not "
            "produce one valid question for every "
            "video region."
        ),
    }


# ==========================================================
# LONG
# ==========================================================

def generate_long_batch(
    regions: list[dict],
) -> dict:

    evidence = build_region_evidence(
        regions,
        context_key="long_context",
    )

    prompt = (
        _common_instructions(
            evidence
        ) + QUESTION_QUALITY_RULES
        + """

Create exactly 5 LONG-ANSWER study questions.

IMPORTANT:

At this stage we only need a COMPACT reference answer.

Do NOT write full essays.

Each answer must:

- be 2 to 4 sentences
- contain the key points needed to answer
- stay grounded in that video's region
- remain concise

The detailed explanation, real-life example,
memory trick, common mistake, exam tip,
practice question and related concepts will be
generated separately when the student needs them.

Return exactly this JSON structure:

{
  "questions": [
    {
      "region": 1,
      "question": "...",
      "answer": "...",
      "evidence": "exact source excerpt from VIDEO REGION 1"
    },
    {
      "region": 2,
      "question": "...",
      "answer": "...",
      "evidence": "exact source excerpt from VIDEO REGION 2"
    },
    {
      "region": 3,
      "question": "...",
      "answer": "...",
      "evidence": "exact source excerpt from VIDEO REGION 3"
    },
    {
      "region": 4,
      "question": "...",
      "answer": "...",
      "evidence": "exact source excerpt from VIDEO REGION 4"
    },
    {
      "region": 5,
      "question": "...",
      "answer": "...",
      "evidence": "exact source excerpt from VIDEO REGION 5"
    }
  ]
}

Requirements:

- exactly 5 questions
- exactly one question from each region
- questions should require explanation,
  reasoning, comparison or application
- no answer longer than 4 sentences
- evidence must be copied directly from the assigned region
- evidence must support both the question and answer
- return JSON only

QUESTION DIVERSITY ROLE:

You are generating the LONG-ANSWER layer of a
three-level quiz.

The same five video regions are also being used
independently for MCQ and short-answer questions.

A long-answer question should therefore test deeper
understanding rather than simply repeating a definition
that could be used as an MCQ or short-answer question.

For long-answer questions, prefer:

- explaining a process step by step
- reasoning about why something works
- comparing supported concepts
- applying a concept to a supported example
- explaining consequences
- connecting two concepts taught in the same region
- explaining both HOW and WHY where evidence supports it

Avoid merely expanding a simple recognition question.

BAD LONG-ANSWER STYLE:
"What is a list and tuple?"

BETTER LONG-ANSWER STYLE:
"Compare lists and tuples in terms of mutability and
explain their different behavior."

BAD LONG-ANSWER STYLE:
"What does += mean?"

BETTER LONG-ANSWER STYLE:
"Explain how an assignment operator such as += updates
a variable using the example taught in the lesson."

Do not artificially combine unrelated concepts simply
to make a question appear deeper.

Every part of the question and answer MUST be supported
by that question's assigned VIDEO REGION.

Evidence grounding is more important than diversity.

Never invent material just to make the question different.
"""
    )

    result = (
        generate_with_provider_router(
            prompt=prompt,
            task="long_batch",
            json_mode=True,
            max_tokens=4000,
            temperature=0.1,
        )
    )

    return _parse_questions(
        result,
        "long",
    )