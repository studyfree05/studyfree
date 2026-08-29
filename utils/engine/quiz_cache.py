"""
quiz_cache.py
-------------

Persistent quiz cache.

Goals:
- avoid regenerating the same video quiz
- save free API quota
- make repeated requests very fast
- automatically separate different quiz versions
"""

from __future__ import annotations

import hashlib
import json
import os
from .transcript import extract_video_id
from pathlib import Path


# ==========================================================
# SETTINGS
# ==========================================================

CACHE_DIR = Path(
    "utils/engine/cache/quizzes"
)

# Change this whenever the quiz-generation format or
# prompting logic changes significantly.
CACHE_VERSION = "quiz_v2"


# ==========================================================
# VIDEO ID
# ==========================================================




# ==========================================================
# CACHE KEY
# ==========================================================

def build_cache_key(
    youtube_url: str,
) -> str | None:

    video_id = extract_video_id(
        youtube_url
    )

    if not video_id:
        return None

    raw = (
        f"{CACHE_VERSION}:{video_id}"
    )

    digest = hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()[:12]

    return (
        f"{video_id}_{digest}"
    )


# ==========================================================
# CACHE PATH
# ==========================================================

def get_cache_path(
    youtube_url: str,
) -> Path | None:

    key = build_cache_key(
        youtube_url
    )

    if not key:
        return None

    return (
        CACHE_DIR
        / f"{key}.json"
    )

# ==========================================================
# LOAD
# ==========================================================

def load_quiz_cache(
    youtube_url: str,
) -> dict | None:
    """
    Return cached quiz or None.
    """

    path = get_cache_path(
        youtube_url
    )
    
    if path is None:       
        return None

    if not path.exists():
        return None

    try:

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(file)

        if (
            not isinstance(data, dict)
            or data.get("cache_version")
            != CACHE_VERSION
        ):
            return None

        quiz = data.get(
            "quiz"
        )

        if not isinstance(
            quiz,
            dict,
        ):
            return None

        return quiz

    except Exception:

        # Broken cache should never break the website.
        return None


# ==========================================================
# SAVE
# ==========================================================

def save_quiz_cache(
    youtube_url: str,
    quiz: dict,
) -> bool:
    """
    Save a successful quiz atomically.
    """

    if not isinstance(
        quiz,
        dict,
    ):
        return False

    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = get_cache_path(
        youtube_url
    )
    
    
    if path is None:
        return False

    temp_path = path.with_suffix(
        ".tmp"
    )

    payload = {
        "cache_version": CACHE_VERSION,
        "video_id": extract_video_id(
            youtube_url
        ),
        "quiz": quiz,
    }

    try:

        with temp_path.open(
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                payload,
                file,
                ensure_ascii=False,
                indent=2,
            )

        os.replace(
            temp_path,
            path,
        )

        return True

    except Exception:

        try:

            if temp_path.exists():
                temp_path.unlink()

        except Exception:
            pass

        return False


# ==========================================================
# DELETE
# ==========================================================

def delete_quiz_cache(
    youtube_url: str,
) -> bool:

    path = get_cache_path(
        youtube_url
    )

    # Invalid/unsupported YouTube URL.
    if path is None:
        return False

    try:

        if path.exists():
            path.unlink()

        return True

    except Exception:

        return False