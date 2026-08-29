import json
import re
import time

from langchain_ollama import ChatOllama

llm = ChatOllama(
    model="qwen2.5:3b",
    temperature=0.1
)
PROMPT = """
You are an expert teacher.

Use ONLY the lecture.

Never invent facts.

Create {count} questions.

Difficulty:
{difficulty}

Question Type:
{qtype}

Lecture

{lecture}

Return ONLY a JSON array.

Example

[
  {{
    "id":1,
    "type":"mcq",
    "question":"...",
    "answer":"..."
  }},
  {{
    "id":2,
    "type":"mcq",
    "question":"...",
    "answer":"..."
  }}
]

Do not write anything except JSON.
"""

def clean(text):

    text = text.strip()

    text = re.sub(r"^```json", "", text)

    text = re.sub(r"^```", "", text)

    text = re.sub(r"```$", "", text)

    return text.strip()


def repair(text):

    text = clean(text)

    text = re.sub(r",\s*}", "}", text)

    text = re.sub(r",\s*]", "]", text)

    return text

def generate_batch(items):

    lecture = "\n\n".join(
        item["knowledge"]["text"] for item in items
    )

    prompt = PROMPT.format(
        count=len(items),
        difficulty=items[0]["difficulty"],
        qtype=items[0]["type"],
        lecture=lecture
    )

    print("=" * 80)
    print("Generating Batch")
    print("=" * 80)

    start = time.time()

    response = llm.invoke(prompt)

    elapsed = round(time.time() - start, 2)

    print("Time:", elapsed, "sec")

    return json.loads(repair(response.content))

