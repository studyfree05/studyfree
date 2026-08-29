"""
Final local/offline quiz generator.

Runtime:
    llama.cpp HTTP server at 127.0.0.1:8080
    Gemma 4 E2B GGUF (or any compatible model exposed by the server)

Goals:
- No cloud API, Ollama, or Qwen.
- Subject-independent and transcript-grounded.
- Strong educational-evidence selection before generation.
- 5 MCQ + 5 short + 5 long.
- No forcing questions from filler-heavy regions.
- Question-level validation and targeted repair.
- Robust parsing of JSON fences, concatenated JSON objects, and MCQ letter answers.
- Keep public function names compatible with the existing project.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any

QUESTION_COUNT = 5
TOTAL_COUNT = 15
KINDS = ("mcq", "short", "long")

LOCAL_SERVER_URL = os.getenv("LOCAL_LLM_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
LOCAL_MODEL = os.getenv("LOCAL_LLM_MODEL", "ggml-org/gemma-4-E2B-it-GGUF:Q4_0")
LOCAL_TIMEOUT = int(os.getenv("LOCAL_LLM_TIMEOUT", "240"))
MAX_OUTPUT_TOKENS = int(os.getenv("LOCAL_LLM_MAX_TOKENS", "750"))
REPAIR_MAX_TOKENS = int(os.getenv("LOCAL_LLM_REPAIR_MAX_TOKENS", "450"))
MAX_SOURCE_CHARS_PER_KIND = int(os.getenv("LOCAL_LLM_SOURCE_CHARS", "520"))

_CACHE_KEY: str | None = None
_CACHE_RESULT: dict | None = None

# Strong technical anchors appearing in many educational transcripts.
# We deliberately use these for evidence selection, not as facts to invent.
ANCHORS = {
    "variable": ("variable", "variables"),
    "constant": ("constant", "constants"),
    "assignment": ("assign", "assignment", "assigned"),
    "print": ("print",),
    "data_type": ("data type", "datatype", "integer", "float", "boolean", "bool", "string"),
    "conversion": ("convert", "conversion", "converted", "type conversion"),
    "operator": ("operator", "operators", "operand", "expression"),
    "floor": ("floor", "//"),
    "swap": ("swap", "swapping"),
    "naming": ("variable name", "variable names", "underscore", "case sensitive"),
    "precedence": ("precedence", "priority", "division", "multiplication"),
    "code": ("code", "python", "syntax"),
}

FILLER_PATTERNS = (
    r"\bwelcome back\b",
    r"\bcongratulations\b",
    r"\bcomment section\b",
    r"\battendance\b",
    r"\bfirst video\b",
    r"\bsecond video\b",
    r"\bthird video\b",
    r"\bpercent(?:age)? of (?:people|students|users)\b",
    r"\bpeople are .* ahead\b",
    r"\bhomework\b",
    r"\blike\b",
    r"\bfile\s*(?:created|create|name)\b",
    r"\bopen\s+vs\s*code\b",
    r"\bvideo\b",
    r"\bsubscribe\b",
    r"\blike and share\b",
)

GENERIC_BAD = (
    "main idea of this section",
    "main idea in this section",
    "key idea in this section",
    "important idea in this section",
    "this section presents",
    "what does this section explain",
    "what is the main idea",
    "what is the key idea",
    "summarize the main idea",
    "the lesson explains",
    "the lesson presents",
    "the source explains",
    "what did the teacher explain",
    "how far ahead",
    "what percentage of people",
)


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _latin_ok(text: str, allow_numeric: bool = False) -> bool:
    text = _clean_text(text)
    if not text:
        return False
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return allow_numeric and bool(re.search(r"\d", text))
    latin = sum(1 for c in letters if ("A" <= c <= "Z") or ("a" <= c <= "z"))
    return (latin / len(letters)) >= 0.80


def _is_filler(text: str) -> bool:
    t = _clean_text(text).casefold()
    return any(re.search(p, t) for p in FILLER_PATTERNS)


def _generic_bad(text: str) -> bool:
    t = " ".join(_clean_text(text).casefold().split())
    return any(p in t for p in GENERIC_BAD)


def _normalize_question(text: str) -> str:
    t = _clean_text(text).casefold()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    stop = {
        "what", "why", "how", "does", "do", "is", "are", "the", "a", "an",
        "and", "of", "to", "in", "for", "can", "this", "that", "which",
        "explain", "describe", "discuss", "with", "from", "about", "should",
        "when", "if", "will", "would", "could", "be", "used", "use",
    }
    return " ".join(w for w in t.split() if w not in stop)


def _extract_json_objects(text: str) -> list[dict]:
    """Parse one JSON object, fenced JSON, or multiple concatenated JSON objects."""
    raw = str(text or "").strip()
    if not raw:
        return []

    decoder = json.JSONDecoder()
    objects: list[dict] = []
    pos = 0
    while pos < len(raw):
        start = raw.find("{", pos)
        if start < 0:
            break
        try:
            obj, end = decoder.raw_decode(raw, start)
        except json.JSONDecodeError:
            pos = start + 1
            continue
        if isinstance(obj, dict):
            objects.append(obj)
        pos = end

    if objects:
        return objects

    # Fenced JSON without an object scanner hit.
    cleaned = raw.replace("```json", "").replace("```", "").strip()
    try:
        obj = json.loads(cleaned)
        return [obj] if isinstance(obj, dict) else []
    except Exception:
        return []


def _merge_question_objects(objects: list[dict]) -> dict | None:
    merged: list[dict] = []
    for obj in objects:
        q = obj.get("questions")
        if isinstance(q, list):
            merged.extend(x for x in q if isinstance(x, dict))
        elif isinstance(obj.get("question"), str):
            merged.append(obj)
        else:
            # Repair responses sometimes use {"1": {...}, "2": {...}}
            vals = [v for v in obj.values() if isinstance(v, dict) and "question" in v]
            if vals:
                merged.extend(vals)
    return {"questions": merged} if merged else None


def _server_model() -> str | None:
    req = urllib.request.Request(f"{LOCAL_SERVER_URL}/v1/models", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        ids = [str(x.get("id", "")) for x in payload.get("data") or [] if x.get("id")]
        if LOCAL_MODEL in ids:
            return LOCAL_MODEL
        return ids[0] if ids else None
    except Exception as exc:
        print("[LOCAL LLM] server unavailable:", repr(exc))
        return None


def _anchor_hits(text: str) -> set[str]:
    t = _clean_text(text).casefold()
    hits: set[str] = set()
    for key, variants in ANCHORS.items():
        if any(v in t for v in variants):
            hits.add(key)
    return hits


def _candidate_units_for_text(text: str, region_no: int, field_name: str, max_units: int = 6) -> list[dict]:
    text = _clean_text(text)
    if not text:
        return []
    # Use overlapping windows around technical anchors instead of arbitrary chunks.
    anchor_positions = []
    low = text.casefold()
    for variants in ANCHORS.values():
        for v in variants:
            pos = 0
            vl = v.casefold()
            while True:
                pos = low.find(vl, pos)
                if pos < 0:
                    break
                anchor_positions.append(pos)
                pos += max(1, len(vl))
    anchor_positions = sorted(set(anchor_positions))
    windows = []
    for pos in anchor_positions:
        a = max(0, pos - 180)
        b = min(len(text), pos + 320)
        piece = text[a:b].strip()
        if len(piece) < 90:
            continue
        windows.append(piece)
    # Also preserve strong numeric/code examples even without a known English anchor.
    for m in re.finditer(r'(?:(?:\b[A-Za-z_][A-Za-z0-9_]*\b\s*=)|//|\+|\*|/|\bTrue\b|\bFalse\b)', text):
        a=max(0,m.start()-180); b=min(len(text),m.start()+320); piece=text[a:b].strip()
        if len(piece)>=90: windows.append(piece)
    scored=[]
    seen=set()
    for piece in windows:
        norm=re.sub(r'[^a-z0-9\d]+',' ',piece.casefold()).strip()
        if not norm or norm in seen: continue
        seen.add(norm)
        score=len(_anchor_hits(piece))*6
        if re.search(r'\d',piece): score += 4
        if re.search(r'=|//|\+|\*|/|True|False',piece): score += 4
        if _is_filler(piece): score -= 20
        if re.search(r'welcome|congrat|comment|attendance|ahead|people|students|file|video',piece.casefold()): score -= 16
        scored.append((score,piece))
    scored.sort(key=lambda x:(-x[0],len(x[1])))
    out=[]
    for score,piece in scored[:max_units]:
        out.append({
            'evidence_id': f'r{region_no}{field_name[0]}{len(out)+1}',
            'region': region_no,
            'evidence': piece[:520],
            'topics': sorted(_anchor_hits(piece)),
            'score': score,
        })
    return out


def _evidence_units(region: dict, region_no: int, max_units: int = 6) -> list[dict]:
    candidates=[]
    for field in ('mcq_context','short_context','long_context','context'):
        candidates.extend(_candidate_units_for_text(region.get(field), region_no, field, max_units=3))
    # Prefer the most teachable and least filler-heavy units.
    candidates.sort(key=lambda x:(-x['score'], x['evidence_id']))
    chosen=[]; seen=set()
    for x in candidates:
        # Deduplicate near-identical evidence windows.
        key=re.sub(r'[^a-z0-9\d]+',' ',x['evidence'].casefold())[:240]
        if key in seen: continue
        seen.add(key); chosen.append(x)
        if len(chosen)>=max_units: break
    return chosen

def _build_evidence_pool(regions: list[dict]) -> list[dict]:
    pool = []
    for i, region in enumerate(regions, 1):
        pool.extend(_evidence_units(region, i, 4))
    pool.sort(key=lambda x: (-x["score"], x["region"], x["evidence_id"]))
    return pool[:12]


def _global_pool(pool: list[dict]) -> str:
    return "\n".join(
        f'{x["evidence_id"]} [R{x["region"]}; {", ".join(x["topics"]) or "educational content"}]: {x["evidence"]}'
        for x in pool
    )


def _prompt(kind: str, pool: list[dict], regions_needed: list[int] | None = None) -> str:
    evidence = _global_pool(pool)
    if kind == "mcq":
        rules = """- Exactly 4 distinct options.\n- `answer` MUST be the complete correct option text, never A/B/C/D.\n- Use concrete definitions, rules, code behavior, conversions, calculations, or examples explicitly shown.\n- Distractors must be plausible but wrong based on the same evidence."""
    elif kind == "short":
        rules = """- Answer in 3-22 words.\n- Ask one specific teachable fact, rule, process, or result."""
    else:
        rules = """- Answer in 18-55 words.\n- Ask for explanation, procedure, comparison, or worked reasoning explicitly supported by evidence."""
    return f"""You are an exam-quality educational question writer.\n\nCreate exactly 5 {kind.upper()} questions from the strongest educational evidence units below. You may use multiple questions from the same topic when the evidence supports different angles. Do NOT force one question per raw transcript region.\n\nCRITICAL RULES:\n- Ignore greetings, motivation, audience statistics, congratulations, file names, editor/navigation instructions, platform chatter, homework logistics, and teacher logistics.\n- Never ask how far ahead viewers/students are or other audience questions.\n- Never invent concepts, values, variables, operations, or conditions not explicitly supported.\n- Preserve exact numerical/code conditions.\n- English student-facing text only.\n- No generic main-idea questions.\n- No reasoning, no explanations, no markdown.\n{rules}\n\nFor each question, include the `evidence_id` you used.\n\nOUTPUT JSON ONLY:\n{{"questions":[{{"evidence_id":"r1e1","region":1,"type":"{kind}","question":"...","options":["...","...","...","..."],"answer":"..."}}]}}\n\nEVIDENCE UNITS:\n{evidence}\n"""


def _repair_prompt(kind: str, bad: list[dict], pool: list[dict]) -> str:
    bad_ids = [x.get("evidence_id") or x.get("region") for x in bad]
    evidence = _global_pool(pool)
    extra = "Use four distinct options; answer must equal the full correct option text." if kind == "mcq" else "Keep the answer concise and strictly supported by the evidence."
    return f"""Repair only these invalid {kind.upper()} questions. Return exactly {len(bad)} question objects in one JSON object.\n\nInvalid IDs/targets: {bad_ids}\nRules: {extra} No audience/motivation/file questions. No invented concepts or changed numbers. English only. No reasoning.\n\nEVIDENCE UNITS:\n{evidence}\n"""


def _call_llm(prompt: str, max_tokens: int, label: str) -> tuple[dict | None, float]:
    model = _server_model()
    if not model:
        return None, 0.0
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Generate high-quality educational questions. Output JSON only. Do not reveal reasoning."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.05,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": False, "thinking_budget": 0},
        "reasoning_effort": "none",
        "stream": False,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{LOCAL_SERVER_URL}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=LOCAL_TIMEOUT) as resp:
            response_data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"[LOCAL LLM] {label} failed:", repr(exc))
        return None, time.perf_counter() - started
    elapsed = time.perf_counter() - started
    print(f"[LOCAL LLM] {label} generation_seconds={elapsed:.2f}")
    choices = response_data.get("choices") or []
    if not choices:
        return None, elapsed
    message = choices[0].get("message") or {}
    text = str(message.get("content") or "").strip()
    print(f"[LOCAL LLM RAW {label}] {text[:4000]!r}")
    objs = _extract_json_objects(text)
    return _merge_question_objects(objs), elapsed


def _answer_normalize(answer: str, options: list[str]) -> str:
    ans = _clean_text(answer)
    if len(ans) == 1 and ans.upper() in {"A", "B", "C", "D"}:
        return options[ord(ans.upper()) - 65]
    # Allow exact option, case-insensitively.
    for opt in options:
        if ans.casefold() == opt.casefold():
            return opt
    return ans


def _question_support_score(question: str, answer: str, evidence: str) -> int:
    q_words = set(re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", question.casefold()))
    a_words = set(re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", answer.casefold()))
    e_words = set(re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", evidence.casefold()))
    overlap = len((q_words | a_words) & e_words)
    hits_q = len(_anchor_hits(question))
    hits_e = len(_anchor_hits(evidence))
    return overlap + min(hits_q, hits_e) * 2


def _literal_tokens(text: str) -> set[str]:
    return set(re.findall(r"(?:\b\d+(?:\.\d+)?\b|\b[a-zA-Z_][a-zA-Z0-9_]*\b|//|==|!=|<=|>=|[+*/%-])", _clean_text(text)))


def _literal_support_ok(question: str, answer: str, options: list[str] | None, evidence: str) -> bool:
    ev=_literal_tokens(evidence.casefold())
    texts=[question,answer] + (options or [])
    # Require every concrete literal/numeric/identifier token to occur in evidence, except common question words.
    ignored={'what','which','how','why','when','where','if','the','is','are','does','do','will','can','a','an','in','of','to','and','for','from','value','result','type','data','python','variable','variables','number','numbers'}
    for t in texts:
        for tok in _literal_tokens(t.casefold()):
            if tok in ignored or tok in {'true','false'} and tok in ev:
                continue
            if tok not in ev:
                return False
    return True

def _validate_item(item: dict, expected_kind: str, pool_by_id: dict[str, dict]) -> tuple[dict | None, str]:
    if not isinstance(item, dict):
        return None, "not_object"
    evidence_id = _clean_text(item.get("evidence_id"))
    evidence_item = pool_by_id.get(evidence_id)
    if not evidence_item:
        return None, "bad_evidence_id"
    kind = _clean_text(item.get("type")).casefold()
    if kind != expected_kind:
        return None, "bad_type"
    question, answer = _clean_text(item.get("question")), _clean_text(item.get("answer"))
    if not question or not answer:
        return None, "missing_text"
    if not _latin_ok(question):
        return None, "non_english_question"
    if not _latin_ok(answer, allow_numeric=True) and not re.search(r"[\d=+*/%.-]", answer):
        return None, "non_english_answer"
    if _generic_bad(question) or _generic_bad(answer) or _is_filler(question):
        return None, "filler_generic"
    options=None
    if kind == "mcq":
        options = item.get("options")
        if not isinstance(options, list) or len(options) != 4:
            return None, "bad_options"
        options = [_clean_text(x) for x in options]
        if any(not x or not _latin_ok(x, allow_numeric=True) for x in options):
            return None, "bad_option_text"
        if len({x.casefold() for x in options}) != 4:
            return None, "duplicate_options"
        answer = _answer_normalize(answer, options)
        if answer not in options:
            return None, "answer_not_in_options"
    if _question_support_score(question, answer, evidence_item["evidence"]) < 5:
        return None, "weak_evidence_support"
    if not _literal_support_ok(question, answer, options, evidence_item["evidence"]):
        return None, "invented_literal_or_condition"
    out = {"region": evidence_item["region"], "type": kind, "question": question, "answer": answer, "evidence": evidence_item["evidence"], "evidence_id": evidence_id}
    if kind == "mcq":
        out["options"], out["answer"] = options, answer
    return out, "ok"


def _generate_kind(kind: str, pool: list[dict]) -> tuple[list[dict], float]:
    pool_by_id = {x["evidence_id"]: x for x in pool}
    data, elapsed = _call_llm(_prompt(kind, pool), MAX_OUTPUT_TOKENS, kind)
    raw = (data or {}).get("questions") if isinstance(data, dict) else None
    valid, bad, seen_q = [], [], set()
    if isinstance(raw, list):
        for item in raw:
            v, reason = _validate_item(item, kind, pool_by_id)
            if v is None:
                bad.append(item if isinstance(item, dict) else {})
                print(f"[LOCAL QUALITY] {kind}: {reason}")
            else:
                nq = _normalize_question(v["question"])
                if nq and nq not in seen_q:
                    seen_q.add(nq); valid.append(v)
                else:
                    bad.append(item); print(f"[LOCAL QUALITY] {kind}: duplicate_question")
    if len(valid) < 5:
        needed = 5 - len(valid)
        repair_data, repair_elapsed = _call_llm(_repair_prompt(kind, bad[:max(needed, len(bad))], pool), REPAIR_MAX_TOKENS, f"repair-{kind}")
        elapsed += repair_elapsed
        repair_raw = (repair_data or {}).get("questions") if isinstance(repair_data, dict) else None
        if isinstance(repair_raw, list):
            for item in repair_raw:
                v, reason = _validate_item(item, kind, pool_by_id)
                if v is None:
                    print(f"[LOCAL QUALITY REJECT AFTER REPAIR] {kind}: {reason}")
                    continue
                nq = _normalize_question(v["question"])
                if nq and nq not in seen_q:
                    seen_q.add(nq); valid.append(v)
                if len(valid) >= 5:
                    break
    return valid[:5], elapsed


def _cache_key(regions: list[dict]) -> str:
    pool = _build_evidence_pool(regions)
    raw = json.dumps(pool, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_offline_quiz(regions: list[dict]) -> dict:
    global _CACHE_KEY, _CACHE_RESULT
    key = _cache_key(regions)
    if key == _CACHE_KEY and _CACHE_RESULT is not None:
        return json.loads(json.dumps(_CACHE_RESULT, ensure_ascii=False))

    pool = _build_evidence_pool(regions)
    all_questions: list[dict] = []
    total_elapsed = 0.0

    for kind in KINDS:
        items, elapsed = _generate_kind(kind, pool)
        total_elapsed += elapsed
        if len(items) != 5:
            failure = {
                "success": False,
                "questions": [],
                "count": 0,
                "counts": {"mcq": 0, "short": 0, "long": 0},
                "provider": "local-llama.cpp",
                "model": LOCAL_MODEL,
                "error": f"Local model failed quality gate for {kind}; {len(items)}/5 valid.",
                "generation_seconds": round(total_elapsed, 2),
            }
            _CACHE_KEY = key
            _CACHE_RESULT = failure
            return json.loads(json.dumps(failure, ensure_ascii=False))
        all_questions.extend(items)

    # Cross-batch duplicate protection.
    seen: set[str] = set()
    deduped: list[dict] = []
    for q in all_questions:
        nq = _normalize_question(q["question"])
        if nq and nq not in seen:
            seen.add(nq)
            deduped.append(q)

    if len(deduped) != TOTAL_COUNT:
        failure = {
            "success": False,
            "questions": [],
            "count": 0,
            "counts": {"mcq": 0, "short": 0, "long": 0},
            "provider": "local-llama.cpp",
            "model": LOCAL_MODEL,
            "error": "Local model produced duplicate-like questions across batches.",
            "generation_seconds": round(total_elapsed, 2),
        }
        _CACHE_KEY = key
        _CACHE_RESULT = failure
        return json.loads(json.dumps(failure, ensure_ascii=False))

    counts = {k: sum(q["type"] == k for q in deduped) for k in KINDS}
    result = {
        "success": counts == {"mcq": 5, "short": 5, "long": 5},
        "questions": deduped,
        "count": len(deduped),
        "counts": counts,
        "provider": "local-llama.cpp",
        "model": LOCAL_MODEL,
        "error": None if counts == {"mcq": 5, "short": 5, "long": 5} else "Local question count mismatch.",
        "generation_seconds": round(total_elapsed, 2),
    }
    _CACHE_KEY = key
    _CACHE_RESULT = result
    return json.loads(json.dumps(result, ensure_ascii=False))


def _batch_from_full(regions: list[dict], kind: str) -> dict:
    full = generate_offline_quiz(regions)
    if not full.get("success"):
        return {
            "success": False,
            "questions": [],
            "count": 0,
            "provider": full.get("provider", "local-llama.cpp"),
            "model": full.get("model", LOCAL_MODEL),
            "error": full.get("error"),
            "generation_seconds": full.get("generation_seconds", 0),
        }
    qs = [q for q in full["questions"] if q.get("type") == kind]
    return {
        "success": len(qs) == 5,
        "questions": qs,
        "count": len(qs),
        "provider": full.get("provider"),
        "model": full.get("model"),
        "error": None if len(qs) == 5 else f"Local model did not return 5 {kind} questions.",
        "generation_seconds": full.get("generation_seconds", 0),
    }


def generate_offline_mcq_batch(regions: list[dict]) -> dict:
    return _batch_from_full(regions, "mcq")


def generate_offline_short_batch(regions: list[dict]) -> dict:
    return _batch_from_full(regions, "short")


def generate_offline_long_batch(regions: list[dict]) -> dict:
    return _batch_from_full(regions, "long")