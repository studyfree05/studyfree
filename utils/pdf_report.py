from datetime import datetime

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import (
    ParagraphStyle,
    getSampleStyleSheet,
)
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)


def _safe(value):

    value = str(
        value
        if value is not None
        else ""
    )

    return (
        value
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def generate_pdf(
    filename,
    score,
    max_score,
    percentage,
    correct,
    partial,
    incorrect,
    skipped,
    questions=None,
):

    questions = questions or []

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "StudyFreeTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        spaceAfter=5 * mm,
    )

    heading_style = ParagraphStyle(
        "QuestionHeading",
        parent=styles["Heading2"],
        spaceBefore=4 * mm,
        spaceAfter=2 * mm,
    )

    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["BodyText"],
        leading=16,
        spaceAfter=2 * mm,
    )

    pdf = SimpleDocTemplate(
        filename,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="StudyFree AI Learning Report",
        author="StudyFree AI",
    )

    story = []

    story.append(
        Paragraph(
            "StudyFree AI",
            title_style,
        )
    )

    story.append(
        Paragraph(
            "AI Learning Report",
            styles["Heading2"],
        )
    )

    story.append(
        Spacer(
            1,
            4 * mm,
        )
    )

    story.append(
        Paragraph(
            "<b>Date:</b> "
            + datetime.now().strftime(
                "%d %B %Y %I:%M %p"
            ),
            body_style,
        )
    )

    story.append(
        Paragraph(
            f"<b>Score:</b> {_safe(score)} / {_safe(max_score)}",
            body_style,
        )
    )

    story.append(
        Paragraph(
            f"<b>Percentage:</b> {_safe(percentage)}%",
            body_style,
        )
    )

    story.append(
        Spacer(
            1,
            5 * mm,
        )
    )

    story.append(
        Paragraph(
            "Statistics",
            styles["Heading2"],
        )
    )

    story.append(
        Paragraph(
            f"<b>Correct:</b> {_safe(correct)}",
            body_style,
        )
    )

    story.append(
        Paragraph(
            f"<b>Partial:</b> {_safe(partial)}",
            body_style,
        )
    )

    story.append(
        Paragraph(
            f"<b>Incorrect:</b> {_safe(incorrect)}",
            body_style,
        )
    )

    story.append(
        Paragraph(
            f"<b>Skipped:</b> {_safe(skipped)}",
            body_style,
        )
    )

    if questions:

        story.append(
            Spacer(
                1,
                7 * mm,
            )
        )

        story.append(
            Paragraph(
                "Question Review",
                styles["Heading1"],
            )
        )

        for item in questions:

            number = item.get(
                "number",
                "",
            )

            qtype = str(
                item.get(
                    "type",
                    "",
                )
            ).upper()

            status = str(
                item.get(
                    "status",
                    "",
                )
            ).upper()

            student_answer = (
                item.get(
                    "student_answer"
                )
                or
                "Not answered"
            )

            feedback = (
                item.get(
                    "feedback"
                )
                or
                "No additional feedback."
            )

            block = [

                Paragraph(
                    f"Question {_safe(number)} "
                    f"({_safe(qtype)})",
                    heading_style,
                ),

                Paragraph(
                    "<b>Question:</b><br/>"
                    + _safe(
                        item.get(
                            "question",
                            "",
                        )
                    ),
                    body_style,
                ),

                Paragraph(
                    "<b>Your Answer:</b><br/>"
                    + _safe(
                        student_answer
                    ),
                    body_style,
                ),

                Paragraph(
                    "<b>Correct / Expected Answer:</b><br/>"
                    + _safe(
                        item.get(
                            "expected_answer",
                            "",
                        )
                    ),
                    body_style,
                ),

                Paragraph(
                    "<b>Result:</b> "
                    + _safe(status),
                    body_style,
                ),

                Paragraph(
                    "<b>AI Feedback:</b><br/>"
                    + _safe(feedback),
                    body_style,
                ),

                Spacer(
                    1,
                    4 * mm,
                ),
            ]

            story.append(
                KeepTogether(
                    block
                )
            )

    story.append(
        Spacer(
            1,
            7 * mm,
        )
    )

    story.append(
        Paragraph(
            "<b>Generated by StudyFree AI</b>",
            styles["Heading3"],
        )
    )

    story.append(
        Paragraph(
            "Learn Smarter with Artificial Intelligence.",
            body_style,
        )
    )

    pdf.build(
        story
    )