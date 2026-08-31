"""
StudyFree Learning Feedback Engine
----------------------------------

Generates educational feedback AFTER a student answers
a quiz question.

This module does NOT:
- generate quiz questions
- modify quiz answers
- modify source evidence
- score MCQs
- replace the written-answer evaluator

It only creates the learning material shown after an answer.
"""

from __future__ import annotations

import json

from utils.engine.providers.openai_provider import (
    generate_with_openai,
)


# ==========================================================
# PROMPT
# ==========================================================

def _build_prompt(
    question: dict,
    student_answer: str,
    status: str,
) -> str:

    payload = {
        "type": str(
            question.get(
                "type",
                "",
            )
        ),
        "question": str(
            question.get(
                "question",
                "",
            )
        ),
        "correct_answer": str(
            question.get(
                "answer",
                "",
            )
        ),
        "student_answer": str(
            student_answer
        ),
        "status": str(
            status
        ),
        "source_evidence": str(
            question.get(
                "evidence",
                "",
            )
        ),
    }

    return """
You are the StudyFree learning-feedback tutor.

A student has just answered ONE question from a
video-based educational quiz.

Your job is NOT to grade the answer.

The grading status has already been decided.

Your job is to help the student UNDERSTAND and REMEMBER
the concept after answering.

============================================================
SOURCE GROUNDING
============================================================

The supplied source_evidence comes directly from the
original video lesson.

The source evidence may be:

- English
- Telugu
- Hindi
- Tamil
- Kannada
- Malayalam
- mixed language
- another language

Understand its meaning.

The question and correct answer were already generated
from this source evidence.

Do NOT contradict the source evidence.

Do NOT introduce unrelated facts.

Do NOT change the supplied correct answer.

If the evidence is narrow, keep the teaching material
narrow too.

============================================================
LANGUAGE
============================================================

Write the learning feedback in clear, simple English.

Technical terms may remain in their normal technical form.


CRITICAL OUTPUT LANGUAGE RULE:

All student-facing learning content MUST be written
entirely in English.

This includes:
- explanation
- real-life example
- memory trick
- common mistake
- exam tip
- practice question
- related concepts

The video transcript may be in another language,
but NEVER copy Telugu, Hindi, Tamil, Kannada,
Malayalam, or other non-English text into the
student-facing response.

Return English only.
============================================================
EXPLANATION
============================================================

Explain WHY the correct answer is correct.

Make it useful for a student who did not understand
the concept.

Use approximately 2 to 4 concise sentences.

Do NOT simply repeat the correct answer.

============================================================
REAL-LIFE EXAMPLE
============================================================

Give ONE short example that makes the concept easier
to understand.

The example must illustrate the supported concept.

Do not introduce a new unsupported lesson topic.

If a meaningful real-life example is not appropriate,
use a simple educational/example scenario instead.

============================================================
MEMORY TRICK
============================================================

Give ONE short memory trick.

It should be easy to remember.

Do not invent a false scientific or technical rule merely
to make a mnemonic.

============================================================
COMMON MISTAKE
============================================================

Give ONE likely misunderstanding related directly to
this question.

Keep it short.

If there is no meaningful common mistake, return an
empty string.

============================================================
EXAM TIP
============================================================

Give ONE concise study/exam tip about how to correctly
answer or recognize this concept.

Do not claim that something will definitely appear in
an examination.

============================================================
PRACTICE QUESTION
============================================================

Create THREE similar practice questions testing the SAME
supported concept.

Each question must test the same concept from a different
angle.

The questions must NOT simply copy the original question.

Each question must have its own correct answer.

Keep all three questions within the concepts supported by
the supplied source evidence.

Do not introduce unrelated concepts.

Make the three questions progressively useful for practice:
- Question 1: basic understanding
- Question 2: application or recognition
- Question 3: another application or slightly different angle

============================================================
RELATED CONCEPTS
============================================================

Return zero to three short concept names that are directly
supported by or strongly connected to the supplied lesson
content.

If none can safely be identified, return an empty list.

============================================================
OUTPUT
============================================================

Return valid JSON only.

Return exactly this structure:

{
  "explanation": "...",
  "real_life_example": "...",
  "memory_trick": "...",
  "common_mistake": "...",
  "exam_tip": "...",
  
  
  "practice_questions": [
        {
            "question": "...",
            "answer": "..."
        },
        {
            "question": "...",
            "answer": "..."
        },
        {
            "question": "...",
            "answer": "..."
        }
    ],
  
    
    "related_concepts": [
        "..."
    ]
    }

    Do not include markdown.

    Do not include text outside the JSON.

STUDENT QUESTION DATA:

""" + json.dumps(
        payload,
        ensure_ascii=False,
    )


# ==========================================================
# TEXT VALIDATION
# ==========================================================

def _clean_text(
    value,
    max_length: int,
) -> str:

    if not isinstance(
        value,
        str,
    ):
        return ""

    value = value.strip()

    if not value:
        return ""

    if len(value) > max_length:
        return ""

    return value


# ==========================================================
# RESPONSE VALIDATION
# ==========================================================

# ==========================================================
# ENGLISH / GENERIC-FEEDBACK VALIDATION
# ==========================================================

def _english_text_ok(
    text: str,
) -> bool:
    """
    Return True when student-facing feedback is
    predominantly English.

    Allows:
    - English letters
    - numbers
    - punctuation
    - normal technical symbols

    Rejects feedback containing substantial
    non-Latin script.
    """

    text = str(
        text or ""
    ).strip()

    if not text:
        return False

    letters = [
        char
        for char in text
        if char.isalpha()
    ]

    if not letters:
        return False

    latin_letters = sum(
        1
        for char in letters
        if (
            "A" <= char <= "Z"
            or "a" <= char <= "z"
        )
    )

    ratio = (
        latin_letters
        / len(letters)
    )

    return ratio >= 0.80


def _contains_generic_feedback(
    text: str,
) -> bool:
    """
    Reject obvious filler that does not teach the
    specific concept.
    """

    normalized = " ".join(
        str(text or "")
        .casefold()
        .split()
    )

    generic_phrases = (
        "remember the key idea",
        "remember the main idea",
        "the key concept you should remember",
        "the main idea you should remember",
        "think of one everyday situation",
        "connecting a lesson to something familiar",
        "make sure your answer directly explains",
        "first identify the exact concept",
        "write the key fact or explanation clearly",
        "the lesson presents an important idea",
        "this section presents an important idea",
        "the correct idea is",
        "this is the key concept",
        "what key idea should you remember about this question",
        "how would you explain the correct idea",
        "what important point would you include",
    )

    return any(
        phrase in normalized
        for phrase in generic_phrases
    )



def _validate_feedback(
    data,
) -> dict | None:

    if not isinstance(
        data,
        dict,
    ):
        return None

    explanation = _clean_text(
        data.get(
            "explanation"
        ),
        1200,
    )

    real_life_example = _clean_text(
        data.get(
            "real_life_example"
        ),
        800,
    )

    memory_trick = _clean_text(
        data.get(
            "memory_trick"
        ),
        500,
    )

    common_mistake = _clean_text(
        data.get(
            "common_mistake",
            "",
        ),
        700,
    )

    exam_tip = _clean_text(
        data.get(
            "exam_tip"
        ),
        700,
    )

    # These are the core learning fields.
    if not (
        explanation
        and real_life_example
        and memory_trick
        and exam_tip
    ):
        return None

    # Student-facing content must be English.
    for value in (
        explanation,
        real_life_example,
        memory_trick,
        common_mistake,
        exam_tip,
    ):
        if value and not _english_text_ok(value):
            return None

    # Reject obvious generic filler.
    for value in (
        explanation,
        real_life_example,
        memory_trick,
        common_mistake,
        exam_tip,
    ):
        if _contains_generic_feedback(value):
            return None

    

    # ------------------------------------------------------
    # PRACTICE QUESTIONS
    # ------------------------------------------------------

    raw_practice_questions = data.get(
        "practice_questions",
        [],
    )

    if not isinstance(
        raw_practice_questions,
        list,
    ):
        return None

    if len(
        raw_practice_questions
    ) != 3:
        return None


    practice_questions = []


    for practice in raw_practice_questions:

        if not isinstance(
            practice,
            dict,
        ):
            return None


        practice_question = _clean_text(
            practice.get(
                "question"
            ),
            700,
        )


        practice_answer = _clean_text(
            practice.get(
                "answer"
            ),
            700,
        )


        if not (
            practice_question
            and practice_answer
        ):
            return None


        practice_questions.append({
            "question": (
                practice_question
            ),
            "answer": (
                practice_answer
            ),
        })

    normalized_practice = {
        " ".join(
            item["question"]
            .casefold()
            .split()
        )
        for item in practice_questions
    }

    if len(normalized_practice) != 3:
        return None

    # ------------------------------------------------------
    # RELATED CONCEPTS
    # ------------------------------------------------------

    raw_concepts = data.get(
        "related_concepts",
        [],
    )

    related_concepts = []

    if isinstance(
        raw_concepts,
        list,
    ):

        for concept in raw_concepts:

            concept = _clean_text(
                concept,
                120,
            )

            if not concept:
                continue

            if not _english_text_ok(concept):
                continue

            if _contains_generic_feedback(concept):
                continue

            if concept in related_concepts:
                continue

            related_concepts.append(
                concept
            )

            if len(
                related_concepts
            ) >= 3:
                break

    return {
        "explanation": explanation,
        "real_life_example": (
            real_life_example
        ),
        "memory_trick": memory_trick,
        "common_mistake": (
            common_mistake
        ),
        "exam_tip": exam_tip,
        "practice_questions": (
            practice_questions
        ),
        "related_concepts": (
            related_concepts
        ),
    }


# ==========================================================
# PUBLIC FUNCTION
# ==========================================================

# ==========================================================
# PUBLIC FUNCTION
# ==========================================================

def _offline_learning_feedback(
    question,
    student_answer,
    status,
):
    student_answer = str(
        student_answer or ""
    ).strip()

    status = str(
        status or "incorrect"
    ).strip().lower()

    # ------------------------------------------------------
    # Extract actual question data
    # ------------------------------------------------------

    if isinstance(question, dict):

        question_text = str(
            question.get(
                "question",
                "",
            )
        ).strip()

        correct_answer = str(
            question.get(
                "answer",
                "",
            )
        ).strip()

        question_type = str(
            question.get(
                "type",
                "",
            )
        ).strip().lower()

    else:

        question_text = str(
            question or ""
        ).strip()

        correct_answer = ""
        question_type = ""

    # ------------------------------------------------------
    # Safe fallbacks
    # ------------------------------------------------------

    if not question_text:
        question_text = "the question concept"

    if not correct_answer:
        correct_answer = (
            "the key concept explained in the lesson"
        )

    # ------------------------------------------------------
    # EXPLANATION
    # ------------------------------------------------------

    explanation = (
        f"The correct idea is {correct_answer}. "
        "This is the key concept you should remember "
        "when answering this question."
    )

    if status == "correct":

        explanation += (
            " Your answer shows that you understood "
            "the main idea."
        )

    elif status == "partial":

        explanation += (
            " Your answer contains part of the idea, "
            "but some important detail is missing."
        )

    elif status == "incorrect":

        explanation += (
            " Your answer needs correction, so focus "
            "on understanding the concept before "
            "trying the question again."
        )

    # ------------------------------------------------------
    # REAL-LIFE EXAMPLE
    # ------------------------------------------------------

    real_life_example = (
        "Think of one everyday situation where the "
        "same idea could be used. Connecting a lesson "
        "to something familiar makes it easier to remember."
    )

    # ------------------------------------------------------
    # MEMORY TRICK
    # ------------------------------------------------------

    short_answer = correct_answer

    if len(short_answer) > 90:

        short_answer = (
            short_answer[:90]
            .rsplit(
                " ",
                1,
            )[0]
            + "..."
        )

    memory_trick = (
        f"Memory trick: remember the key phrase "
        f"'{short_answer}'."
    )

    # ------------------------------------------------------
    # COMMON MISTAKE
    # ------------------------------------------------------

    common_mistake = (
        "Do not memorize unrelated words. "
        "Make sure your answer directly explains "
        "the concept asked in the question."
    )

    # ------------------------------------------------------
    # EXAM TIP
    # ------------------------------------------------------

    exam_tip = (
        "First identify the exact concept in the question. "
        "Then write the key fact or explanation clearly "
        "and directly."
    )

    # ------------------------------------------------------
    # PRACTICE QUESTIONS
    # ------------------------------------------------------

    practice_questions = [

        {
            "question": (
                f"What key idea should you remember "
                f"about this question?"
            ),
            "answer": correct_answer,
        },

        {
            "question": (
                f"How would you explain the correct idea "
                f"in your own words?"
            ),
            "answer": correct_answer,
        },

        {
            "question": (
                f"What important point would you include "
                f"when answering this question in an exam?"
            ),
            "answer": correct_answer,
        },

    ]

    normalized_practice = {
        " ".join(
            item["question"]
            .casefold()
            .split()
        )
        for item in practice_questions
    }

    if len(normalized_practice) != 3:
        return None

    # ------------------------------------------------------
    # RELATED CONCEPTS
    # ------------------------------------------------------

    related_concepts = []

    if question_type:

        related_concepts.append(
            question_type
        )

    return {
        "explanation": explanation,
        "real_life_example": real_life_example,
        "memory_trick": memory_trick,
        "common_mistake": common_mistake,
        "exam_tip": exam_tip,
        "practice_questions": practice_questions,
        "related_concepts": related_concepts,
    }
    
    
def generate_learning_feedback(
    question: dict,
    student_answer: str,
    status: str,
) -> dict:

    if not isinstance(
        question,
        dict,
    ):

        return {
            "success": False,
            "feedback": None,
            "provider": "",
            "model": "",
            "error": (
                "Question must be a dictionary."
            ),
        }

    question_text = str(
        question.get(
            "question",
            "",
        )
    ).strip()

    correct_answer = str(
        question.get(
            "answer",
            "",
        )
    ).strip()

    evidence = str(
        question.get(
            "evidence",
            "",
        )
    ).strip()

    if not question_text:

        return {
            "success": False,
            "feedback": None,
            "provider": "",
            "model": "",
            "error": (
                "Question text is missing."
            ),
        }

    if not correct_answer:

        return {
            "success": False,
            "feedback": None,
            "provider": "",
            "model": "",
            "error": (
                "Correct answer is missing."
            ),
        }

    if not evidence:

        return {
            "success": False,
            "feedback": None,
            "provider": "",
            "model": "",
            "error": (
                "Source evidence is missing."
            ),
        }

    status = str(
        status
    ).strip().lower()

    if status not in {
        "correct",
        "partial",
        "incorrect",
    }:

        return {
            "success": False,
            "feedback": None,
            "provider": "",
            "model": "",
            "error": (
                "Invalid evaluation status."
            ),
        }

    prompt = _build_prompt(
        question,
        student_answer,
        status,
    )

    result = generate_with_openai(
        prompt=prompt,
        task="learning_feedback",
        json_mode=True,
        max_tokens=1100,
        temperature=0.1,
    )

    if not result.success:

        print('[LEARNING FEEDBACK] OpenAI error:', result.error, 'model:', result.model)

        print(
            "[LEARNING FEEDBACK] "
            "OpenAI unavailable. "
            "Refusing to serve ungrounded generic feedback."
        )

        return {
            "success": False,
            "feedback": None,
            "provider": "openai",
            "model": result.model,
            "error": (
                "High-quality learning feedback is "
                "temporarily unavailable. Please try again."
            ),
        }

    try:

        data = json.loads(
            result.text
        )

    except Exception:

        print(
            "[LEARNING FEEDBACK] "
            "OpenAI returned invalid JSON."
        )

        return {
            "success": False,
            "feedback": None,
            "provider": result.provider,
            "model": result.model,
            "error": (
                "The learning-feedback response was invalid. "
                "Please try again."
            ),
        }

    feedback = _validate_feedback(
        data
    )

    if feedback is None:

        print(
            "[LEARNING FEEDBACK] "
            "OpenAI feedback failed validation."
        )

        return {
            "success": False,
            "feedback": None,
            "provider": result.provider,
            "model": result.model,
            "error": (
                "The learning feedback did not pass "
                "quality validation. Please try again."
            ),
        }

    return {
        "success": True,
        "feedback": feedback,
        "provider": result.provider,
        "model": result.model,
        "error": None,
    }