"""
StudyFree AI Teacher
"""


def evaluate_answer(

    question,

    expected,

    student,

):

    student = str(student).strip()

    expected = str(expected).strip()

    if student == "":

        return {

            "score": 0,

            "status": "skipped",

            "feedback": "Question skipped.",

            "missing": [],

            "next_topic": "",

        }

    if student.lower() == expected.lower():

        return {

            "score": 1,

            "status": "correct",

            "feedback": "Excellent! Correct answer.",

            "missing": [],

            "next_topic": "",

        }

    return {

        "score": 0,

        "status": "incorrect",

        "feedback": "Answer does not fully match.",

        "missing": [

            expected

        ],

        "next_topic": "",

    }