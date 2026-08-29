"""
StudyFree Knowledge Graph Builder

Supports evidence-grounded structured knowledge.
"""

from __future__ import annotations

from .schema import KNOWLEDGE_GRAPH_SCHEMA


def build_graph(
    knowledge: dict,
) -> dict:

    if not isinstance(
        knowledge,
        dict,
    ):

        return {
            "title": "",
            "language": "english",
            "summary": "",
            "source_regions": [],
            "topics": [],
        }

    graph = {

        "title": str(
            knowledge.get(
                "title",
                "",
            )
        ).strip(),

        "language": str(
            knowledge.get(
                "language",
                "english",
            )
        ).strip(),

        "summary": str(
            knowledge.get(
                "summary",
                "",
            )
        ).strip(),

        "source_regions": (
            knowledge.get(
                "source_regions",
                [],
            )
        ),

        "topics": [],
    }

    for topic in knowledge.get(
        "topics",
        [],
    ):

        if not isinstance(
            topic,
            dict,
        ):
            continue

        name = str(
            topic.get(
                "topic",
                "",
            )
        ).strip()

        if not name:
            continue

        raw_points = topic.get(
            "points",
            [],
        )

        if not isinstance(
            raw_points,
            list,
        ):
            raw_points = []

        points = []

        facts = []

        evidence = []

        regions = set()

        for item in raw_points:

            # ==============================================
            # NEW EVIDENCE-AWARE FORMAT
            # ==============================================

            if isinstance(
                item,
                dict,
            ):

                point = str(
                    item.get(
                        "point",
                        "",
                    )
                ).strip()

                region = item.get(
                    "region"
                )

                source_evidence = str(
                    item.get(
                        "evidence",
                        "",
                    )
                ).strip()

                if not point:
                    continue

                points.append(
                    point
                )

                facts.append(
                    point
                )

                evidence_item = {
                    "point": point,
                    "region": region,
                    "evidence": (
                        source_evidence
                    ),
                }

                evidence.append(
                    evidence_item
                )

                if region is not None:

                    try:

                        regions.add(
                            int(region)
                        )

                    except (
                        TypeError,
                        ValueError,
                    ):

                        pass

            # ==============================================
            # OLD FORMAT — BACKWARD COMPATIBILITY
            # ==============================================

            else:

                point = str(
                    item
                ).strip()

                if not point:
                    continue

                points.append(
                    point
                )

                facts.append(
                    point
                )

        graph["topics"].append(
            {
                "name": name,

                "summary": " ".join(
                    points
                ),

                "points": points,

                "definitions": [],

                "examples": [],

                "keywords": [],

                "formulas": [],

                "facts": facts,

                "evidence": evidence,

                "source_regions": sorted(
                    regions
                ),

                "relationships": [],
            }
        )

    return graph