import time
import re

from langchain_ollama import ChatOllama


llm = ChatOllama(
    model="qwen2.5:3b",
    temperature=0.05
)

PROMPT = """
You are an expert Python teacher.

Use ONLY the concept below.

Your job is to test the Python topic being explained.

IMPORTANT:
- Ignore stories, analogies and examples.
- Focus only on the Python concept.
- Do NOT ask about grocery items, teachers, people or examples.
- Ask about Python only.

Concept:
{concept}

Return exactly:

Question: <one Python question>

Answer: <correct answer from the concept>
"""


def parse_output(text):

    question = ""
    answer = ""

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for line in lines:

        lower = line.lower()

        if lower.startswith("question:"):
            question = line.split(":", 1)[1].strip()

        elif lower.startswith("answer:"):
            answer = line.split(":", 1)[1].strip()

    # If the model swapped them
    if question == "" and answer.endswith("?"):
        question = answer
        answer = ""

    # If only one line was returned
    if question == "" and len(lines) == 1:
        question = lines[0]

    return {
        "question": question,
        "answer": answer
    }


def generate_question(concept, qid, qtype="mcq"):

    prompt = PROMPT.format(concept=concept)

    print("=" * 80)
    print(f"Generating Question {qid}")
    print("=" * 80)

    start = time.time()

    response = llm.invoke(prompt)
    print("\nRAW AI OUTPUT\n")
    print(response.content)
    print("\n" + "=" * 80)

    elapsed = round(time.time() - start, 2)

    print("Time:", elapsed, "sec")

    data = parse_output(response.content)

    return {
        "id": qid,
        "type": qtype,
        "question": data["question"],
        "answer": data["answer"]
    }
    
