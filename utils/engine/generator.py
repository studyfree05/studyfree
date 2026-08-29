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

Use ONLY the lecture below.

Never invent facts.

Create ONLY ONE question.

Rules

1. Use ONLY information from lecture.
2. Do not greet.
3. Do not explain.
4. Do not add memory tricks.
5. Do not add examples.
6. Do not add common mistakes.
7. Return ONLY JSON.

Difficulty:
{difficulty}

Lecture

{lecture}

JSON

{{
"id":{id},
"type":"{type}",
"question":"...",
"answer":"..."
}}
"""

def clean_response(text):

    text = text.strip()

    text = re.sub(r"^```json", "", text)

    text = re.sub(r"^```", "", text)

    text = re.sub(r"```$", "", text)

    return text.strip()

def repair_json(text):

    text = clean_response(text)

    text = re.sub(r",\s*}", "}", text)

    text = re.sub(r",\s*]", "]", text)

    return text
def generate_question(item):

    qtype = "mcq"

    if item["id"] > 5:
        qtype = "short"

    if item["id"] > 10:
        qtype = "concept"

    prompt = PROMPT.format(

        id=item["id"],

        difficulty=item["difficulty"],

        lecture=item["knowledge"]["text"],

        type=qtype

    )

    print("=" * 80)
    print(f"Generating Question {item['id']}")
    print("=" * 80)

    start = time.time()

    response = llm.invoke(prompt)

    elapsed = round(time.time() - start, 2)

    print("Time:", elapsed, "sec")

    text = repair_json(response.content)

    return json.loads(text)

