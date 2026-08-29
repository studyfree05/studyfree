"""
StudyFree Knowledge Graph Schema
"""

KNOWLEDGE_GRAPH_SCHEMA = {

    "type": "object",

    "properties": {

        "title": {
            "type": "string"
        },

        "language": {
            "type": "string"
        },

        "topics": {

            "type": "array",

            "items": {

                "type": "object",

                "properties": {

                    "name": {
                        "type": "string"
                    },

                    "summary": {
                        "type": "string"
                    },

                    "definitions": {
                        "type": "array"
                    },

                    "examples": {
                        "type": "array"
                    },

                    "keywords": {
                        "type": "array"
                    },

                    "formulas": {
                        "type": "array"
                    },

                    "facts": {
                        "type": "array"
                    },

                    "relationships": {
                        "type": "array"
                    }

                }

            }

        }

    }

}