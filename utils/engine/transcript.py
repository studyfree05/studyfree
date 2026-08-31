"""
transcript.py
-------------

Reliable YouTube transcript fetcher for StudyFree.

Responsibilities:
- Validate YouTube URL
- Extract YouTube video ID
- Discover available transcripts
- Prefer English when available
- Fall back to other available languages
- Prefer manually-created transcripts
- Support automatically-generated transcripts
- Return standardized result
- No AI
- No cleaning
- No chunking
"""

from __future__ import annotations

import os
import requests
import re
import time
from urllib.parse import urlparse, parse_qs

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import WebshareProxyConfig

from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
)


# ==========================================================
# SETTINGS
# ==========================================================

# Preferred order only.
#
# IMPORTANT:
# We do NOT force the transcript to be English.
# The transcript should remain in its original language.
#
# The quiz generator can later use the transcript as evidence.
PREFERRED_LANGUAGES = (
    "en",
    "en-US",
    "en-GB",
    "te",
    "hi",
    "ta",
    "kn",
    "ml",
)

MAX_ATTEMPTS = 3

RETRY_DELAY = 1.0


# ==========================================================
# VIDEO ID
# ==========================================================

def extract_video_id(
    url: str,
) -> str | None:

    if not isinstance(
        url,
        str,
    ):
        return None

    url = url.strip()

    if not url:
        return None

    # ------------------------------------------------------
    # Direct video ID
    # ------------------------------------------------------

    if re.fullmatch(
        r"[A-Za-z0-9_-]{11}",
        url,
    ):
        return url

    # ------------------------------------------------------
    # Standard YouTube URLs
    # ------------------------------------------------------

    try:

        parsed = urlparse(
            url
        )

        hostname = (
            parsed.hostname
            or ""
        ).lower()

        # youtu.be/<ID>
        if hostname in {
            "youtu.be",
            "www.youtu.be",
        }:

            video_id = (
                parsed.path
                .lstrip("/")
                .split("/")[0]
            )

            if re.fullmatch(
                r"[A-Za-z0-9_-]{11}",
                video_id,
            ):
                return video_id

        # youtube.com/watch?v=<ID>
        if hostname in {
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
        }:

            query = parse_qs(
                parsed.query
            )

            video_id = (
                query.get(
                    "v",
                    [None],
                )[0]
            )

            if video_id and re.fullmatch(
                r"[A-Za-z0-9_-]{11}",
                video_id,
            ):
                return video_id

        # youtube.com/embed/<ID>
        # youtube.com/shorts/<ID>
        # youtube.com/live/<ID>

        parts = [
            part
            for part in
            parsed.path.split("/")
            if part
        ]

        if len(parts) >= 2:

            if parts[0].lower() in {
                "embed",
                "shorts",
                "live",
            }:

                video_id = parts[1]

                if re.fullmatch(
                    r"[A-Za-z0-9_-]{11}",
                    video_id,
                ):
                    return video_id

    except Exception:

        pass

    # ------------------------------------------------------
    # Regex fallback
    # ------------------------------------------------------

    patterns = (
        r"(?:youtube\.com/watch\?v=)"
        r"([A-Za-z0-9_-]{11})",

        r"(?:youtu\.be/)"
        r"([A-Za-z0-9_-]{11})",

        r"(?:youtube\.com/embed/)"
        r"([A-Za-z0-9_-]{11})",

        r"(?:youtube\.com/shorts/)"
        r"([A-Za-z0-9_-]{11})",

        r"(?:youtube\.com/live/)"
        r"([A-Za-z0-9_-]{11})",
    )

    for pattern in patterns:

        match = re.search(
            pattern,
            url,
        )

        if match:

            return match.group(1)

    return None


# ==========================================================
# TRANSCRIPT SELECTION HELPERS
# ==========================================================

def _language_score(
    transcript,
) -> int:

    language_code = str(
        getattr(
            transcript,
            "language_code",
            "",
        )
        or ""
    ).lower()

    # Exact preferred language gets the highest score.
    for index, language in enumerate(
        PREFERRED_LANGUAGES
    ):

        language = (
            language.lower()
        )

        if language_code == language:

            return (
                1000
                -
                index
            )

    # English variants.
    if language_code.startswith(
        "en"
    ):
        return 900

    # Telugu.
    if language_code.startswith(
        "te"
    ):
        return 800

    # Hindi.
    if language_code.startswith(
        "hi"
    ):
        return 700

    return 0


def _is_generated(
    transcript,
) -> bool:

    value = getattr(
        transcript,
        "is_generated",
        False,
    )

    return bool(
        value
    )


def _select_transcript(
    transcript_list,
):
    """
    Select the best available transcript.

    Priority:

    1. Manual English
    2. Generated English
    3. Manual preferred language
    4. Generated preferred language
    5. Any manual transcript
    6. Any available transcript
    """

    try:

        transcripts = list(
            transcript_list
        )

    except Exception:

        return None

    if not transcripts:

        return None

    # ------------------------------------------------------
    # Manual preferred-language transcript
    # ------------------------------------------------------

    manual_preferred = [
        transcript
        for transcript in transcripts
        if not _is_generated(
            transcript
        )
        and _language_score(
            transcript
        ) > 0
    ]

    if manual_preferred:

        manual_preferred.sort(
            key=_language_score,
            reverse=True,
        )

        return manual_preferred[0]

    # ------------------------------------------------------
    # Generated preferred-language transcript
    # ------------------------------------------------------

    generated_preferred = [
        transcript
        for transcript in transcripts
        if _is_generated(
            transcript
        )
        and _language_score(
            transcript
        ) > 0
    ]

    if generated_preferred:

        generated_preferred.sort(
            key=_language_score,
            reverse=True,
        )

        return generated_preferred[0]

    # ------------------------------------------------------
    # Any manual transcript
    # ------------------------------------------------------

    manual = [
        transcript
        for transcript in transcripts
        if not _is_generated(
            transcript
        )
    ]

    if manual:

        manual.sort(
            key=_language_score,
            reverse=True,
        )

        return manual[0]

    # ------------------------------------------------------
    # Any available transcript
    # ------------------------------------------------------

    transcripts.sort(
        key=_language_score,
        reverse=True,
    )

    return transcripts[0]


# ==========================================================
# TRANSCRIPT TEXT
# ==========================================================

def _transcript_to_text(
    fetched_transcript,
) -> str:

    if fetched_transcript is None:

        return ""

    parts = []

    try:

        for chunk in fetched_transcript:

            # Newer youtube-transcript-api versions
            # expose snippets as objects.

            text = getattr(
                chunk,
                "text",
                None,
            )

            if isinstance(
                text,
                str,
            ):

                text = text.strip()

                if text:

                    parts.append(
                        text
                    )

                continue

            # Compatibility with dictionary-style
            # transcript chunks.

            if isinstance(
                chunk,
                dict,
            ):

                text = chunk.get(
                    "text",
                    "",
                )

                if isinstance(
                    text,
                    str,
                ):

                    text = text.strip()

                    if text:

                        parts.append(
                            text
                        )

    except TypeError:

        return ""

    return " ".join(
        parts
    ).strip()


# ==========================================================
# PUBLIC FETCHER
# ==========================================================

def fetch_transcript(
    url: str,
) -> dict:
    """
    Download a YouTube transcript using FreeTranscriptAPI.
    """

    video_id = extract_video_id(url)

    if not video_id:
        return {
            "success": False,
            "video_id": None,
            "language": None,
            "text": None,
            "error": "Invalid YouTube URL.",
        }

    last_error = None

    for attempt in range(MAX_ATTEMPTS):

        try:
            response = requests.get(
                "https://api.freetranscriptapi.com/v1/transcript",
                params={
                    "video_url": url,
                },
                timeout=30,
            )

            if not response.ok:
                try:
                    error_data = response.json()
                    error_message = (
                        error_data.get("error", {}).get(
                            "message",
                            "Transcript API request failed.",
                        )
                    )
                except Exception:
                    error_message = (
                        f"Transcript API returned HTTP "
                        f"{response.status_code}."
                    )

                raise RuntimeError(error_message)

            data = response.json()

            transcript_chunks = data.get(
                "transcript",
                [],
            )

            if not transcript_chunks:
                return {
                    "success": False,
                    "video_id": video_id,
                    "language": data.get("language"),
                    "text": None,
                    "error": (
                        "No transcript is available "
                        "for this video."
                    ),
                }

            text = _transcript_to_text(
                transcript_chunks
            )

            if not text:
                return {
                    "success": False,
                    "video_id": video_id,
                    "language": data.get("language"),
                    "text": None,
                    "error": (
                        "The video transcript was empty."
                    ),
                }

            language = data.get("language")

            print(
                "Transcript fetched:",
                video_id,
                "| language =",
                language,
                "| characters =",
                len(text),
            )

            return {
                "success": True,
                "video_id": video_id,
                "language": language,
                "text": text,
                "error": None,
            }

        except Exception as exc:

            last_error = exc

            print(
                "Transcript attempt",
                attempt + 1,
                "failed:",
                exc,
            )

            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(
                    RETRY_DELAY * (attempt + 1)
                )

    return {
        "success": False,
        "video_id": video_id,
        "language": None,
        "text": None,
        "error": (
            "Transcript retrieval failed "
            f"after {MAX_ATTEMPTS} attempts: "
            f"{last_error}"
        ),
    }