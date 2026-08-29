"""
StudyFree Notes Generator
"""


def generate_notes(graph):

    notes = []

    for topic in graph["topics"]:

        notes.append({

            "title": topic["name"],

            "summary": topic["summary"],

            "keywords": topic["keywords"],

            "definitions": topic["definitions"],

            "examples": topic["examples"]

        })

    return notes