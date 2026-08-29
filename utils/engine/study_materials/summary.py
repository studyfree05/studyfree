"""
StudyFree Summary Generator
"""


def generate_summary(graph):

    lines = []

    lines.append(graph.get("title", ""))

    lines.append("")

    for topic in graph.get("topics", []):

        lines.append("# " + topic["name"])

        if topic["summary"]:

            lines.append(topic["summary"])

        if topic["keywords"]:

            lines.append("Keywords:")

            for word in topic["keywords"]:

                lines.append("- " + word)

        lines.append("")

    return "\n".join(lines)