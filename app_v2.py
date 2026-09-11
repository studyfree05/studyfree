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
from werkzeug.security import generate_password_hash, check_password_hash

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
import sqlite3
import secrets
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone

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
# USER ACCOUNTS + EMAIL OTP VERIFICATION
# ==========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "studyfree_users.db")

MAIL_HOST = os.environ.get("STUDYFREE_MAIL_HOST", "smtp.gmail.com")
MAIL_PORT = int(os.environ.get("STUDYFREE_MAIL_PORT", "587"))
MAIL_USERNAME = os.environ.get("STUDYFREE_MAIL_USERNAME", "")
MAIL_PASSWORD = os.environ.get("STUDYFREE_MAIL_PASSWORD", "")
MAIL_FROM = os.environ.get("STUDYFREE_MAIL_FROM", MAIL_USERNAME)


def get_db():
    db = sqlite3.connect(DATABASE_PATH)
    db.row_factory = sqlite3.Row
    return db


def init_user_db():
    db = get_db()
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            email_verified INTEGER NOT NULL DEFAULT 0,
            verification_otp TEXT,
            verification_otp_expires TEXT,
            verification_attempts INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    db.commit()
    db.close()


def upgrade_user_db():
    db = get_db()
    columns = {row["name"] for row in db.execute("PRAGMA table_info(users)").fetchall()}

    if not columns:
        db.close()
        init_user_db()
        return

    if "email_verified" not in columns:
        db.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0")
    if "verification_otp" not in columns:
        db.execute("ALTER TABLE users ADD COLUMN verification_otp TEXT")
    if "verification_otp_expires" not in columns:
        db.execute("ALTER TABLE users ADD COLUMN verification_otp_expires TEXT")
    if "verification_attempts" not in columns:
        db.execute("ALTER TABLE users ADD COLUMN verification_attempts INTEGER NOT NULL DEFAULT 0")

    db.commit()
    db.close()


def send_verification_email(email, full_name, otp):
    if not MAIL_USERNAME or not MAIL_PASSWORD or not MAIL_FROM:
        raise RuntimeError(
            "Email is not configured. Set STUDYFREE_MAIL_USERNAME, "
            "STUDYFREE_MAIL_PASSWORD and STUDYFREE_MAIL_FROM."
        )

    message = EmailMessage()
    message["Subject"] = "Your StudyFree05 verification code"
    message["From"] = MAIL_FROM
    message["To"] = email
    message.set_content(
        f"""Hi {full_name},

Welcome to StudyFree05!

Your 6-digit email verification code is:

{otp}

This code expires in 10 minutes.

If you did not create this account, you can ignore this email.

StudyFree05
"""
    )

    with smtplib.SMTP(MAIL_HOST, MAIL_PORT, timeout=20) as server:
        server.starttls()
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        server.send_message(message)


def send_password_reset_email(email, full_name, otp):
    if not MAIL_USERNAME or not MAIL_PASSWORD or not MAIL_FROM:
        raise RuntimeError(
            "Email is not configured. Set STUDYFREE_MAIL_USERNAME, "
            "STUDYFREE_MAIL_PASSWORD and STUDYFREE_MAIL_FROM."
        )

    message = EmailMessage()
    message["Subject"] = "Your StudyFree05 password reset code"
    message["From"] = MAIL_FROM
    message["To"] = email
    message.set_content(
        f"""Hi {full_name},

We received a request to reset your StudyFree05 password.

Your 6-digit password reset code is:

{otp}

This code expires in 10 minutes.

If you did not request a password reset, you can ignore this email.

StudyFree05
"""
    )

    with smtplib.SMTP(MAIL_HOST, MAIL_PORT, timeout=20) as server:
        server.starttls()
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        server.send_message(message)


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None

    db = get_db()
    user = db.execute(
        """
        SELECT id, full_name, email, created_at, email_verified
        FROM users WHERE id = ?
        """,
        (user_id,),
    ).fetchone()
    db.close()
    return user


init_user_db()
upgrade_user_db()


# ==========================================================
# AUTHENTICATION
# ==========================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    error = None

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not full_name or not email or not password or not confirm_password:
            error = "Please fill in all fields."
        elif "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            error = "Please enter a valid email address."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif password != confirm_password:
            error = "Passwords do not match."
        else:
            db = get_db()
            existing = db.execute(
                "SELECT id FROM users WHERE email = ?", (email,)
            ).fetchone()

            if existing:
                db.close()
                error = "An account with this email already exists."
            else:
                otp = f"{secrets.randbelow(1000000):06d}"
                expires = (
                    datetime.now(timezone.utc) + timedelta(minutes=10)
                ).isoformat()

                cursor = db.execute(
                    """
                    INSERT INTO users
                    (full_name, email, password_hash, email_verified,
                     verification_otp, verification_otp_expires, verification_attempts)
                    VALUES (?, ?, ?, 0, ?, ?, 0)
                    """,
                    (
                        full_name,
                        email,
                        generate_password_hash(password),
                        otp,
                        expires,
                    ),
                )
                db.commit()
                user_id = cursor.lastrowid
                db.close()

                try:
                    send_verification_email(email, full_name, otp)
                except Exception as exc:
                    print(f"Verification email error: {exc}")
                    db = get_db()
                    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
                    db.commit()
                    db.close()
                    error = "We couldn't send the verification email. Please try again."
                else:
                    session["pending_verification_email"] = email
                    return redirect(url_for("verify_otp"))

    return render_template("register.html", error=error)


@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    email = session.get("pending_verification_email")
    if not email:
        return redirect(url_for("register"))

    error = None

    if request.method == "POST":
        otp = request.form.get("otp", "").strip()

        if not otp.isdigit() or len(otp) != 6:
            error = "Enter the 6-digit verification code."
        else:
            db = get_db()
            user = db.execute(
                """
                SELECT id, full_name, email, email_verified, verification_otp,
                       verification_otp_expires, verification_attempts
                FROM users WHERE email = ?
                """,
                (email,),
            ).fetchone()

            if not user:
                db.close()
                error = "Account not found. Please register again."
            elif user["email_verified"]:
                db.close()
                session.pop("pending_verification_email", None)
                return redirect(url_for("login"))
            elif user["verification_attempts"] >= 5:
                db.close()
                error = "Too many incorrect attempts. Please use Resend Code."
            else:
                try:
                    expires = datetime.fromisoformat(user["verification_otp_expires"])
                except (TypeError, ValueError):
                    expires = datetime.min.replace(tzinfo=timezone.utc)

                if expires < datetime.now(timezone.utc):
                    db.close()
                    error = "This code has expired. Please use Resend Code."
                elif otp != user["verification_otp"]:
                    db.execute(
                        "UPDATE users SET verification_attempts = verification_attempts + 1 WHERE id = ?",
                        (user["id"],),
                    )
                    db.commit()
                    db.close()
                    error = "Incorrect verification code."
                else:
                    db.execute(
                        """
                        UPDATE users
                        SET email_verified = 1,
                            verification_otp = NULL,
                            verification_otp_expires = NULL,
                            verification_attempts = 0
                        WHERE id = ?
                        """,
                        (user["id"],),
                    )
                    db.commit()
                    db.close()
                    session.pop("pending_verification_email", None)
                    session["user_id"] = user["id"]
                    session["user_name"] = user["full_name"]
                    return redirect(url_for("ai_quiz"))

    return render_template("verify_otp.html", email=email, error=error)


@app.route("/resend-verification", methods=["POST"])
def resend_verification():
    email = session.get("pending_verification_email")
    if not email:
        return redirect(url_for("register"))

    db = get_db()
    user = db.execute(
        "SELECT id, full_name, email_verified FROM users WHERE email = ?",
        (email,),
    ).fetchone()

    if not user:
        db.close()
        return redirect(url_for("register"))

    if user["email_verified"]:
        db.close()
        session.pop("pending_verification_email", None)
        return redirect(url_for("login"))

    otp = f"{secrets.randbelow(1000000):06d}"
    expires = (
        datetime.now(timezone.utc) + timedelta(minutes=10)
    ).isoformat()

    db.execute(
        """
        UPDATE users
        SET verification_otp = ?,
            verification_otp_expires = ?,
            verification_attempts = 0
        WHERE id = ?
        """,
        (otp, expires, user["id"]),
    )
    db.commit()
    db.close()

    try:
        send_verification_email(email, user["full_name"], otp)
    except Exception as exc:
        print(f"Resend verification email error: {exc}")
        return render_template(
            "verify_otp.html",
            email=email,
            error="We couldn't resend the code. Please try again.",
        )

    return render_template(
        "verify_otp.html",
        email=email,
        error="A new verification code has been sent.",
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    error = None

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute(
            """
            SELECT id, full_name, email, password_hash, email_verified
            FROM users WHERE email = ?
            """,
            (email,),
        ).fetchone()
        db.close()

        if not user or not check_password_hash(user["password_hash"], password):
            error = "Incorrect email or password."
        elif not user["email_verified"]:
            session["pending_verification_email"] = email
            error = "Please verify your email before logging in."
        else:
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["full_name"]
            return redirect(url_for("ai_quiz"))

    return render_template("login.html", error=error)


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if session.get("user_id"):
        return redirect(url_for("ai_quiz"))

    error = None

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()

        if not email:
            error = "Please enter your email address."
        else:
            db = get_db()
            user = db.execute(
                "SELECT id, full_name, email FROM users WHERE email = ?",
                (email,),
            ).fetchone()

            if not user:
                db.close()
                error = "No account was found with that email address."
            else:
                otp = f"{secrets.randbelow(1000000):06d}"
                expires = (
                    datetime.now(timezone.utc) + timedelta(minutes=10)
                ).isoformat()

                db.execute(
                    """
                    UPDATE users
                    SET verification_otp = ?,
                        verification_otp_expires = ?,
                        verification_attempts = 0
                    WHERE id = ?
                    """,
                    (otp, expires, user["id"]),
                )
                db.commit()
                db.close()

                try:
                    send_password_reset_email(
                        user["email"], user["full_name"], otp
                    )
                except Exception as exc:
                    print(f"Password reset email error: {exc}")
                    error = "We couldn't send the reset code. Please try again."
                else:
                    session["password_reset_email"] = email
                    return redirect(url_for("reset_password"))

    return render_template("forgot_password.html", error=error)


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    email = session.get("password_reset_email")
    if not email:
        return redirect(url_for("forgot_password"))

    error = None

    if request.method == "POST":
        otp = request.form.get("otp", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not otp.isdigit() or len(otp) != 6:
            error = "Enter the 6-digit reset code."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif password != confirm_password:
            error = "Passwords do not match."
        else:
            db = get_db()
            user = db.execute(
                """
                SELECT id, verification_otp, verification_otp_expires,
                       verification_attempts
                FROM users WHERE email = ?
                """,
                (email,),
            ).fetchone()

            if not user:
                db.close()
                error = "Account not found."
            elif user["verification_attempts"] >= 5:
                db.close()
                error = "Too many incorrect attempts. Please request a new code."
            else:
                try:
                    expires = datetime.fromisoformat(user["verification_otp_expires"])
                except (TypeError, ValueError):
                    expires = datetime.min.replace(tzinfo=timezone.utc)

                if expires < datetime.now(timezone.utc):
                    db.close()
                    error = "This code has expired. Please request a new one."
                elif otp != user["verification_otp"]:
                    db.execute(
                        "UPDATE users SET verification_attempts = verification_attempts + 1 WHERE id = ?",
                        (user["id"],),
                    )
                    db.commit()
                    db.close()
                    error = "Incorrect reset code."
                else:
                    db.execute(
                        """
                        UPDATE users
                        SET password_hash = ?,
                            verification_otp = NULL,
                            verification_otp_expires = NULL,
                            verification_attempts = 0
                        WHERE id = ?
                        """,
                        (generate_password_hash(password), user["id"]),
                    )
                    db.commit()
                    db.close()
                    session.pop("password_reset_email", None)
                    return redirect(url_for("login"))

    return render_template("reset_password.html", email=email, error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    if not user["email_verified"]:
        session.clear()
        return redirect(url_for("login"))
    return redirect(url_for("ai_quiz"))


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


@app.route("/robots.txt")
def robots_txt():
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Sitemap: https://studyfree05.com/sitemap.xml\n",
        200,
        {"Content-Type": "text/plain"}
    )


@app.route("/sitemap.xml")
def sitemap():
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        '<url><loc>https://studyfree05.com/about</loc></url>'
        '<url><loc>https://studyfree05.com/ai-quiz</loc></url>'
        '</urlset>',
        200,
        {"Content-Type": "application/xml"}
    )

# ==========================================================
# GENERATE QUIZ
# ==========================================================

@app.route(
    "/ai-quiz",
    methods=["GET", "POST"],
)
def ai_quiz():

    user = current_user()
    if not user or not user["email_verified"]:
        return redirect(url_for("login"))

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