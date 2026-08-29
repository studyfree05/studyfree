"""
StudyFree Flashcards
"""


def generate_flashcards(graph):

    cards = []

    for topic in graph["topics"]:

        cards.append({

            "front": topic["name"],

            "back": topic["summary"]

        })

        for keyword in topic["keywords"]:

            cards.append({

                "front": keyword,

                "back": topic["name"]

            })

    return cards