"""
Revision Sheet
"""


def generate_revision_sheet(graph):

    sheet = []

    for topic in graph["topics"]:

        sheet.append(topic["name"])

        for keyword in topic["keywords"]:

            sheet.append(

                "• " + keyword

            )

        sheet.append("")

    return "\n".join(sheet)