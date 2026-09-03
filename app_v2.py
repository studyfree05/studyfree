"""
StudyFree v1
"""

from flask import (
    Flask,
    render_template,
    request,
    session,
    redirect,
    url_for,
    send_file,
    after_this_request,
)

from flask_session import Session

from services.scorer import (
    score_mcq,
)

from services.answer_evaluator import (
    evaluate_written_answers,
)

from services.learning_feedback import (
    generate_learning_feedback,
)

from services.learning_feedback import (
    generate_learning_feedback,
)

from services.quiz_service import (
    create_quiz,
)

import os
import tempfile

import random

from utils.pdf_report import generate_pdf


from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "studyfree-local-development-key",
)

# ==========================================================
# SERVER-SIDE SESSION
# ==========================================================

app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_USE_SIGNER"] = True
app.config["SESSION_FILE_DIR"] = os.path.join(
    tempfile.gettempdir(),
    "studyfree_sessions",
)

app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024
app.config["SESSION_COOKIE_NAME"] = "studyfree_session"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_PATH"] = "/"

Session(app)

# ==========================================================
# HOME
# ==========================================================
@app.route("/")
def home():

    return redirect(
        url_for("ai_quiz")
    )


@app.route("/about")
def about():
    return render_template("about.html")

# ==========================================================
# GENERATE QUIZ
# ==========================================================

@app.route(
    "/ai-quiz",
    methods=["GET", "POST"],
)
def ai_quiz():

    if request.method == "POST":

        youtube_url = request.form.get(
            "youtube_url",
            "",
        ).strip()

        print("[URL DEBUG]", repr(youtube_url))
        force_new_quiz = session.pop(
            "force_new_quiz",
            False,
        )

        if youtube_url == "":

            return render_template(
                "ai_quiz.html",
                error=(
                    "Please enter a "
                    "YouTube URL."
                ),
            )

        print("=" * 60)
        print("Generating Quiz...")
        print("=" * 60)

        # ---------- START NEW QUIZ ----------
        session.pop("quiz", None)
        session.pop("current_question", None)
        session.pop("score", None)
        session.pop("answers", None)
        session.pop("quiz_completed", None)

        session.modified = True
        # -----------------------------------
        
        
        quiz = create_quiz(
            youtube_url,
            use_cache=not force_new_quiz,
        )
        session["quiz"] = quiz["questions"]
        session["current_question"] = 0
        session["score"] = 0
        session["answers"] = []
        session["quiz_completed"] = False

        session.modified = True

        print("=" * 60)

        if not quiz.get(
            "success"
        ):

            return render_template(
                "ai_quiz.html",
                error=quiz.get(
                    "error",
                    "Quiz generation failed.",
                ),
            )

        questions = quiz.get(
            "questions",
            [],
        )
        print("\n" + "=" * 60)
        print("GENERATED QUESTIONS DEBUG")
        print("=" * 60)

        for i, q in enumerate(questions, start=1):

            print(f"\nQUESTION {i}")
            print("Type:", q.get("type"))
            print("Question:", q.get("question"))
            print("Answer:", q.get("answer"))
            print("Options:", q.get("options"))
            print("Evidence:", q.get("evidence"))

        print("=" * 60 + "\n")

        if not questions:

            return render_template(
                "ai_quiz.html",
                error=(
                    "No questions were "
                    "generated."
                ),
            )

        # Start fresh quiz state.
        

        # ------------------------------------------------------
        # BALANCE / RANDOMIZE MCQ CORRECT-ANSWER POSITIONS
        # ------------------------------------------------------
        def _shuffle_mcq_answers(question_list):
            positions = [0, 1, 2, 3]

            mcq_index = 0

            for q in question_list:
                if str(q.get("type", "")).lower() != "mcq":
                    continue

                options = q.get("options")
                answer = str(q.get("answer", "")).strip()

                if not isinstance(options, list) or len(options) != 4:
                    continue

                options = [str(x).strip() for x in options]

                if answer not in options:
                    continue

                # Deterministic balanced sequence rather than random clustering.
                target_position = positions[mcq_index % 4]

                remaining = [x for x in options if x != answer]
                random.shuffle(remaining)

                new_options = (
                    remaining[:target_position]
                    + [answer]
                    + remaining[target_position:]
                )

                q["options"] = new_options
                q["answer"] = answer

                mcq_index += 1

            return question_list

        
        questions = _shuffle_mcq_answers(questions)
        session["questions"] = questions
        session["current"] = 0
        
        session.pop(
            "question_feedback",
            None,
        )

        session.pop(
            "feedback",
            None,
        )

        session.pop(
            "answer",
            None,
        )

        session.pop(
            "last_answer",
            None,
        )
        
        session["answers"] = []
        
        session.pop(
            "last_result",
            None,
        )

        print(
            "Questions loaded:",
            len(questions),
        )

        response = redirect(
            url_for("quiz")
        )

        print(
            "[COOKIE SET DEBUG]",
            "set_cookie=",
            response.headers.get("Set-Cookie"),
        )

        return response

    return render_template(
        "ai_quiz.html"
    )

# ==========================================================
# NEW VIDEO / RESET QUIZ
# ==========================================================

@app.route("/new-video")
def new_video():
    session.clear()          # Remove every previous quiz/session value
    session.modified = True
    print("[QUIZ] New video requested - session completely cleared.")
    return redirect(url_for("ai_quiz"))
    
    

# ==========================================================
# QUIZ
# ==========================================================
@app.route(
    "/quiz",
    methods=["GET", "POST"],
)
def quiz():

    questions = session.get(
        "questions",
        [],
    )

    print("[SESSION DEBUG]", "count=", len(questions), "keys=", list(session.keys()), "cookie=", request.cookies.get("studyfree_session"), "sid=", getattr(session, "sid", None))

    current = session.get(
        "current",
        0,
    )

    if not questions:

        return redirect(
            url_for("ai_quiz")
        )

    if current >= len(questions):

        return redirect(
            url_for("results")
        )

    question = questions[current]
    print(
        "QUIZ DEBUG:",
        "current=", current,
        "type=", question.get("type"),
        "number=", current + 1,
        "action_pending=", request.form.get("action")
    )

    # ======================================================
    # POST
    # ======================================================

    if request.method == "POST":

        action = request.form.get(
            "action",
            "check",
        )

        print(
            "ACTION =",
            repr(action),
        )

        # --------------------------------------------------
        # LEARN
        # --------------------------------------------------

        if action == "learn":

            feedback = session.get(
                "question_feedback"
            )

            if not feedback:

                return redirect(
                    url_for("quiz")
                )

            if feedback.get("learning"):

                return redirect(
                    url_for("quiz")
                )

            student_answer = str(
                feedback.get(
                    "student_answer",
                    "",
                )
            ).strip()

            status = str(
                feedback.get(
                    "status",
                    "incorrect",
                )
            ).strip().lower()

            if status == "skipped":

                return redirect(
                    url_for("quiz")
                )

            learning = (
                generate_learning_feedback(
                    question=question,
                    student_answer=student_answer,
                    status=status,
                )
            )

            if learning.get("success"):

                feedback["learning"] = (
                    learning.get(
                        "feedback",
                        {},
                    )
                )

                session[
                    "question_feedback"
                ] = feedback

            return redirect(
                url_for("quiz")
            )
            
            
            
        
        
        # --------------------------------------------------
        # NEXT QUESTION
        # --------------------------------------------------
        if action == "next":

            current_feedback = session.get(
                "question_feedback"
            )

            # --------------------------------------------------
            # Only allow Next when feedback belongs to
            # the CURRENT question.
            # This prevents stale feedback from an
            # older question/quiz being reused.
            # --------------------------------------------------
            if (
                not current_feedback
                or current_feedback.get(
                    "question_index"
                ) != current
            ):

                return render_template(
                    "quiz.html",
                    question=question,
                    number=current + 1,
                    total=len(questions),
                    feedback=None,
                    error=(
                        "Please check your answer "
                        "before moving to the next question."
                    ),
                )

            # --------------------------------------------------
            # Move to next question
            # --------------------------------------------------
            current += 1

            session["current"] = current

            # Clear feedback from the previous question
            session.pop(
                "question_feedback",
                None,
            )

            # --------------------------------------------------
            # Final question completed
            # --------------------------------------------------
            if current >= len(questions):

                return redirect(
                    url_for("results")
                )

            # --------------------------------------------------
            # Load next question
            # --------------------------------------------------
            return redirect(
                url_for("quiz")
            )
        
        
        # --------------------------------------------------
        # CHECK ANSWER
        # --------------------------------------------------

        
        answer = str(
            request.form.get(
                "answer",
                "",
            )
        ).strip()

        answers = session.get(
            "answers",
            [],
        )

        qtype = str(
            question.get(
                "type",
                "mcq",
            )
        ).lower()

        expected = str(
            question.get(
                "answer",
                "",
            )
        ).strip()

        # --------------------------------------------------
        # SKIPPED
        # --------------------------------------------------

        if not answer:

            status = "skipped"
            score = 0

            evaluator_feedback = (
                "Question skipped."
            )

        # --------------------------------------------------
        # MCQ
        # --------------------------------------------------

        elif qtype == "mcq":

            evaluation = score_mcq(
                answer,
                expected,
            )

            status = evaluation.get(
                "status",
                "incorrect",
            )

            score = evaluation.get(
                "score",
                0,
            )

            if status == "correct":

                evaluator_feedback = (
                    "Correct answer."
                )

            else:

                evaluator_feedback = (
                    "Your answer does not match "
                    "the correct answer."
                )

        # --------------------------------------------------
        # SHORT / LONG
        # --------------------------------------------------

        else:

            evaluation = (
                evaluate_written_answers(
                    [
                        {
                            "type": qtype,
                            "question": str(
                                question.get(
                                    "question",
                                    "",
                                )
                            ),
                            "expected_answer": expected,
                            "student_answer": answer,
                        }
                    ]
                )
            )

            if not evaluation.get(
                "success"
            ):

                return render_template(
                    "quiz.html",
                    question=question,
                    number=current + 1,
                    total=len(questions),
                    feedback=None,
                    error=(
                        "Your answer could not "
                        "be evaluated. "
                        "Please try again."
                    ),
                )

            evaluations = evaluation.get(
                "evaluations",
                [],
            )

            if not evaluations:

                return render_template(
                    "quiz.html",
                    question=question,
                    number=current + 1,
                    total=len(questions),
                    feedback=None,
                    error=(
                        "No evaluation was "
                        "returned. Please try again."
                    ),
                )

            item = evaluations[0]

            status = item.get(
                "status",
                "incorrect",
            )

            score = item.get(
                "score",
                0,
            )

            evaluator_feedback = str(
                item.get(
                    "feedback",
                    "",
                )
            )

        # --------------------------------------------------
        # SAVE ANSWER
        # --------------------------------------------------

        if len(answers) <= current:

            answers.append(
                answer
            )

        else:

            answers[current] = answer

        session["answers"] = answers

        # Learning is generated ONLY when the
        # user presses "Learn This Question".

        feedback = {
            "question_index": current,
            "status": status,
            "score": score,
            "student_answer": answer,
            "correct_answer": expected,
            "evaluator_feedback": evaluator_feedback,
            "learning": {},
        }

        session[
            "question_feedback"
        ] = feedback

        return render_template(
            "quiz.html",
            question=question,
            number=current + 1,
            total=len(questions),
            feedback=feedback,
            error=None,
        )

    # ======================================================
    # GET
    # ======================================================

    feedback = session.get(
        "question_feedback"
    )

    if feedback and feedback.get(
        "question_index"
    ) != current:

        session.pop(
            "question_feedback",
            None,
        )

        feedback = None

    # ------------------------------------------------------
    # STALE FEEDBACK PROTECTION
    # ------------------------------------------------------

    if feedback:

        feedback_index = feedback.get(
            "question_index"
        )

        if feedback_index != current:

            print(
                "[QUIZ] Stale feedback detected. "
                "Clearing old feedback."
            )

            session.pop(
                "question_feedback",
                None,
            )

            feedback = None


    return render_template(
        "quiz.html",
        question=question,
        number=current + 1,
        total=len(questions),
        feedback=feedback,
        error=None,
    )
        

# ==========================================================
# RESULTS
# ==========================================================

@app.route("/results")
def results():
    
    saved_result = session.get(
        "last_result"
    )

    if saved_result:

        return render_template(
            "results.html",
            score=saved_result.get("score", 0),
            max_score=saved_result.get("max_score", 0),
            percentage=saved_result.get("percentage", 0),
            correct=saved_result.get("correct", 0),
            partial=saved_result.get("partial", 0),
            incorrect=saved_result.get("incorrect", 0),
            skipped=saved_result.get("skipped", 0),
            error=None,
        )

    questions = session.get(
        "questions",
        [],
    )

    answers = session.get(
        "answers",
        [],
    )

    if not questions:

        return redirect(
            url_for("ai_quiz")
        )

    # ======================================================
    # COUNTERS
    # ======================================================

    correct = 0
    partial = 0
    incorrect = 0
    skipped = 0
    question_details = []

    # ======================================================
    # BUILD WRITTEN ANSWER BATCH
    # ======================================================

    written_items = []

    # Maps AI evaluation result back to
    # the original question.
    written_question_indexes = []

    for index, question in enumerate(
        questions
    ):

        user_answer = ""

        if index < len(
            answers
        ):

            user_answer = str(
                answers[index]
            ).strip()

        # ----------------------------------------------
        # SKIPPED
        # ----------------------------------------------

        if user_answer == "":

            skipped += 1

            question_details.append({
                "number": index + 1,
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
                "student_answer": "",
                "expected_answer": str(
                    question.get(
                        "answer",
                        "",
                    )
                ),
                "status": "skipped",
                "feedback": "Question skipped.",
            })

            continue

        qtype = str(
            question.get(
                "type",
                "mcq",
            )
        ).lower()

        expected = str(
            question.get(
                "answer",
                "",
            )
        ).strip()

        # ----------------------------------------------
        # MCQ — LOCAL
        # ----------------------------------------------

        if qtype == "mcq":

            result = score_mcq(
                user_answer,
                expected,
            )

            if (
                result["status"]
                == "correct"
            ):

                correct += 1

            else:

                incorrect += 1
                
            question_details.append({
                "number": index + 1,
                "type": "mcq",
                "question": str(
                    question.get(
                        "question",
                        "",
                    )
                ),
                "student_answer": user_answer,
                "expected_answer": expected,
                "status": result["status"],
                "feedback": (
                    "Correct answer."
                    if result["status"] == "correct"
                    else "Your answer does not match the correct answer."
                ),
            })
            

            continue

        # ----------------------------------------------
        # WRITTEN — BATCH LATER
        # ----------------------------------------------

        written_items.append({
            "type": qtype,

            "question": str(
                question.get(
                    "question",
                    "",
                )
            ),

            "expected_answer":
                expected,

            "student_answer":
                user_answer,
        })

        written_question_indexes.append(
            index
        )

    # ======================================================
    # ONE AI CALL FOR ALL WRITTEN ANSWERS
    # ======================================================

    if written_items:

        evaluation = (
            evaluate_written_answers(
                written_items
            )
        )

        if not evaluation.get(
            "success"
        ):

            print("=" * 60)
            print(
                "ANSWER EVALUATION FAILED"
            )
            print(
                evaluation.get(
                    "error"
                )
            )
            print("=" * 60)

            # Do NOT silently mark answers wrong if
            # the AI provider failed.
            return render_template(
                "results.html",
                error=(
                    "Written answers could "
                    "not be evaluated. "
                    "Please try again."
                ),
                score=0,
                max_score=len(
                    questions
                ),
                percentage=0,
                correct=0,
                partial=0,
                incorrect=0,
                skipped=skipped,
            )

        evaluations = (
            evaluation.get(
                "evaluations",
                []
            )
        )

        for position, item in enumerate(
            evaluations
        ):

            status = item.get(
                "status"
            )

            if status == "correct":

                correct += 1

            elif status == "partial":

                partial += 1

            else:

                incorrect += 1

            original_index = (
                written_question_indexes[
                    position
                ]
            )

            question = questions[
                original_index
            ]

            user_answer = answers[
                original_index
            ]

            question_details.append({
                "number": original_index + 1,
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
                "student_answer": str(
                    user_answer
                ),
                "expected_answer": str(
                    question.get(
                        "answer",
                        "",
                    )
                ),
                "status": status,
                "feedback": str(
                    item.get(
                        "feedback",
                        "",
                    )
                ),
            })

    # ======================================================
    # FINAL SCORE
    # ======================================================

    score = (
        correct
        + (
            partial
            * 0.5
        )
    )

    max_score = len(
        questions
    )

    percentage = 0

    if max_score > 0:

        percentage = round(
            (
                score
                / max_score
            )
            * 100,
            1,
        )

    print("=" * 60)
    print("QUIZ RESULTS")
    print("=" * 60)
    print("Correct   :", correct)
    print("Partial   :", partial)
    print("Incorrect :", incorrect)
    print("Skipped   :", skipped)
    print(
        "Score     :",
        score,
        "/",
        max_score,
    )
    print(
        "Percentage:",
        percentage,
    )
    print("=" * 60)
    
    # ======================================================
    # SAVE RESULT FOR PDF REPORT
    # ======================================================


    question_details.sort(
        key=lambda item: item["number"]
    )


    session["last_result"] = {
        "score": score,
        "max_score": max_score,
        "percentage": percentage,
        "correct": correct,
        "partial": partial,
        "incorrect": incorrect,
        "skipped": skipped,
        "questions": question_details,
    }

    return render_template(
        "results.html",
        score=score,
        max_score=max_score,
        percentage=percentage,
        correct=correct,
        partial=partial,
        incorrect=incorrect,
        skipped=skipped,
        error=None,
    )
    
    
# ==========================================================
# DOWNLOAD PDF REPORT
# ==========================================================

@app.route("/download-report")
def download_report():

    result = session.get(
        "last_result"
    )

    if not result:

        return redirect(
            url_for("ai_quiz")
        )

    temp_file = tempfile.NamedTemporaryFile(
        suffix=".pdf",
        delete=False,
    )

    filename = temp_file.name
    temp_file.close()
    generate_pdf(
        filename=filename,
        score=result.get(
            "score",
            0,
        ),
        max_score=result.get(
            "max_score",
            0,
        ),
        percentage=result.get(
            "percentage",
            0,
        ),
        correct=result.get(
            "correct",
            0,
        ),
        partial=result.get(
            "partial",
            0,
        ),
        incorrect=result.get(
            "incorrect",
            0,
        ),
        skipped=result.get(
            "skipped",
            0,
        ),
        questions=result.get(
            "questions",
            [],
        ),
        
    )
    
    @after_this_request
    def cleanup_pdf(response):

        try:
            os.remove(filename)

        except OSError:
            pass

        return response

    return send_file(
        filename,
        as_attachment=True,
        download_name=(
            "StudyFree_AI_Learning_Report.pdf"
        ),
        mimetype="application/pdf",
    )


# ==========================================================
# RUN
# ==========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5050,
        debug=os.environ.get(
            "FLASK_DEBUG",
            "0",
        ) == "1",
    )