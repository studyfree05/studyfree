"""
StudyFree Coverage Engine
"""

from collections import Counter


def calculate_coverage(questions):
    """
    Calculate topic/region coverage for a quiz.
    """

    if not questions:
        return {
            "coverage": 0,
            "regions": {},
            "balanced": False,
        }

    regions = []

    for q in questions:

        region = q.get("region", 0)

        regions.append(region)

    counts = Counter(regions)

    total_regions = max(regions)

    covered = len(counts)

    coverage = round(
        (covered / total_regions) * 100,
        1,
    )

    balanced = True

    average = len(questions) / total_regions

    for count in counts.values():

        if count > average * 2:

            balanced = False

    return {

        "coverage": coverage,

        "regions": dict(counts),

        "balanced": balanced,

        "total_regions": total_regions,

    }