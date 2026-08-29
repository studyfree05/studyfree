from .transcript import (
    extract_video_id,
    fetch_transcript
)


import json



from .transcript import extract_video_id, fetch_transcript
from .evaluator import evaluate_answer
import threading
from .free_quiz_pipeline import generate_free_quiz


# ==========================================================
# QUIZ ENGINE
# ==========================================================

class QuizEngine:
    
    def __init__(self):

        self.remaining_questions = []

        self.background_running = False

        self.background_thread = None

        print("=" * 80)
        print("QUIZ ENGINE INITIALIZED")
        print("=" * 80)
    
    # ======================================================
    # BACKGROUND GENERATOR
    # ======================================================

    def _generate_remaining_questions(self, plan):

        try:

            print("=" * 80)
            print("BACKGROUND GENERATION STARTED")
            print("=" * 80)

            raw = generate_questions(
                plan,
                start=5,
                count=10
            )

            questions = parse_questions(raw)

            self.remaining_questions = questions

            print("=" * 80)
            print(f"BACKGROUND COMPLETE : {len(questions)} QUESTIONS")
            print("=" * 80)

        except Exception as e:

            print("Background Generation Error:", e)

        finally:

            self.background_running = False
    # ======================================================
    # GET REMAINING QUESTIONS
    # ======================================================

    
        
    

    # ======================================================
    # GENERATE QUIZ
    # ======================================================

    def generate_quiz(
        self,
        video_url: str,
    ):

        result = generate_free_quiz(
            video_url,
            use_cache=True,
        )

        if not result.get("success"):
            raise ValueError(
                result.get(
                    "error",
                    "Quiz generation failed.",
                )
            )

        questions = result.get(
            "questions",
            [],
        )

        if not questions:
            raise ValueError(
                "No valid questions generated."
            )

        print("=" * 80)
        print(
            f"QUIZ READY : {len(questions)} QUESTIONS"
        )
        print(
            f"PROVIDERS  : {result.get('providers', {})}"
        )
        print("=" * 80)

        return questions

    # ======================================================
    # EVALUATE QUESTION
    # ======================================================

    def evaluate_question(
        self,
        question: dict,
        student_answer: str,
    ):

        return evaluate_answer(
            question=question.get(
                "question",
                "",
            ),
            correct_answer=question.get(
                "answer",
                "",
            ),
            student_answer=student_answer,
            evidence=question.get(
                "evidence",
                "",
            ),
            question_type=question.get(
                "type",
                "general",
            ),
        )