"""
chunker.py
----------

Splits long educational transcripts into manageable chunks
for local AI processing.
"""

from __future__ import annotations


DEFAULT_CHUNK_SIZE = 3500
DEFAULT_OVERLAP = 300


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[str]:
    """
    Split transcript into overlapping chunks.

    Attempts to break at natural spaces so words
    are not cut in the middle.
    """

    if not text:
        return []

    text = text.strip()

    if not text:
        return []

    # Short transcript
    if len(text) <= chunk_size:
        return [text]

    chunks = []

    start = 0
    text_length = len(text)

    while start < text_length:

        end = min(start + chunk_size, text_length)

        # Try to end at a natural word boundary
        if end < text_length:

            boundary = text.rfind(" ", start, end)

            # Only use boundary if it is reasonably close
            # to the desired chunk ending.
            if boundary > start + (chunk_size // 2):
                end = boundary

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break

        # Overlap helps preserve context between chunks.
        next_start = end - overlap

        # Avoid getting stuck.
        if next_start <= start:
            next_start = end

        start = next_start

    return chunks

def select_chunks(
    chunks: list[str],
    max_chunks: int = 6,
) -> list[str]:
    """
    Select chunks evenly across the entire transcript.

    This prevents very long videos from requiring
    an Ollama call for every single chunk.
    """

    if not chunks:
        return []

    if len(chunks) <= max_chunks:
        return chunks

    if max_chunks <= 1:
        return [chunks[0]]

    indexes = []

    for i in range(max_chunks):
        index = round(
            i * (len(chunks) - 1) / (max_chunks - 1)
        )

        if index not in indexes:
            indexes.append(index)

    return [chunks[i] for i in indexes]

def build_balanced_context(
    text: str,
    max_chunks: int = 9,
    chars_per_chunk: int = 900,
) -> str:
    """
    Build context covering the full video.

    Samples from the beginning, middle, and end of each
    selected transcript chunk instead of only its beginning.
    """

    chunks = chunk_text(text)

    selected = select_chunks(
        chunks,
        max_chunks=max_chunks,
    )

    sections = []

    for index, chunk in enumerate(selected, start=1):

        if not chunk:
            continue

        # Short chunks can be used completely.
        if len(chunk) <= chars_per_chunk:
            sample = chunk.strip()

        else:
            # Take information from three positions
            # inside this chunk.
            part_size = chars_per_chunk // 3

            beginning = chunk[:part_size]

            middle_start = max(
                0,
                (len(chunk) // 2) - (part_size // 2),
            )

            middle = chunk[
                middle_start:
                middle_start + part_size
            ]

            ending = chunk[
                -part_size:
            ]

            sample = (
                beginning.strip()
                + " "
                + middle.strip()
                + " "
                + ending.strip()
            )

        if sample:

            sections.append(
                f"[VIDEO SECTION {index}]\n{sample}"
            )

    return "\n\n".join(sections)