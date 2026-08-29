"""
cache.py
---------

Generic cache utilities for the AI engine.
"""

import hashlib
import json
import os


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cache_file(cache_dir: str, key: str) -> str:
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, _hash(key) + ".json")


def exists(cache_dir: str, key: str) -> bool:
    return os.path.exists(cache_file(cache_dir, key))


def load(cache_dir: str, key: str):
    path = cache_file(cache_dir, key)

    if not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save(cache_dir: str, key: str, data):
    path = cache_file(cache_dir, key)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )