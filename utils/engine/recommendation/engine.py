"""
StudyFree Recommendation Engine
"""


def build_recommendations(graph, weak_topics):

    recommendations = []

    topics = graph.get("topics", [])

    for topic in topics:

        name = topic.get("name", "")

        if name not in weak_topics:
            continue

        recommendations.append({

            "topic": name,

            "summary": topic.get(
                "summary",
                "",
            ),

            "keywords": topic.get(
                "keywords",
                [],
            ),

            "study": [

                "Read Summary",

                "Review Notes",

                "Practice Flashcards",

                "Attempt Another Quiz",

            ]

        })

    return recommendations