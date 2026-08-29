"""
StudyFree Quality Score Engine
"""


def calculate_quality(

    validator,

    coverage,

    duplicates,

):

    score = 100

    # Validation

    if not validator.get(

        "valid",

        True,

    ):

        score -= 30

    # Coverage

    score -= max(

        0,

        100 - coverage.get(

            "coverage",

            100,

        ),

    ) * 0.3

    # Duplicate penalty

    score -= duplicates * 10

    score = max(

        0,

        round(score),

    )

    return {

        "score": score,

        "ready": score >= 90,

    }