"""
StudyFree Analytics Engine
"""

from datetime import datetime


def build_analytics(result):

    return {

        "generated_at": datetime.now().isoformat(),

        "question_count": result.get(
            "count",
            0,
        ),

        "cached": result.get(
            "cached",
            False,
        ),

        "generation_time": result.get(
            "time",
            0,
        ),

        "providers": result.get(
            "providers",
            {},
        ),

        "models": result.get(
            "models",
            {},
        ),

        "coverage": result.get(
            "coverage",
            {},
        ),

        "quality": result.get(
            "quality",
            {},
        ),

    }