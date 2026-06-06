import re
from typing import Any


def _word_count(text: str) -> int:
    return len(text.split())


def _split_into_units(text: str) -> list[str]:
    """Split on double newlines first, then sentences."""
    units: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
            sentence = sentence.strip()
            if sentence:
                units.append(sentence)
    return units


def chunk_text(
    text: str, chunk_size: int = 400, overlap: int = 50
) -> list[dict[str, Any]]:
    """Split text into overlapping chunks sized by word count."""
    units = _split_into_units(text)
    if not units:
        return []

    chunks: list[dict[str, Any]] = []
    chunk_index = 0
    start = 0

    while start < len(units):
        end = start
        words = 0
        while end < len(units):
            unit_words = _word_count(units[end])
            if words + unit_words > chunk_size and end > start:
                break
            words += unit_words
            end += 1

        segment = units[start:end]
        if not segment:
            break

        chunks.append(
            {
                "text": " ".join(segment),
                "chunk_index": chunk_index,
            }
        )
        chunk_index += 1

        if end >= len(units):
            break

        overlap_words = 0
        overlap_start = end
        while overlap_start > start and overlap_words < overlap:
            overlap_start -= 1
            overlap_words += _word_count(units[overlap_start])

        start = overlap_start if overlap_start > start else end

    return chunks


def chunk_pages(
    page_texts: list[tuple[int, str]],
    source_type: str = "pdf",
    chunk_size: int = 400,
    overlap: int = 50,
) -> list[dict[str, Any]]:
    """Chunk multi-page text, assigning page numbers and a global chunk index."""
    all_chunks: list[dict[str, Any]] = []
    global_index = 0

    for page_number, text in page_texts:
        page_chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        for chunk in page_chunks:
            all_chunks.append(
                {
                    "text": chunk["text"],
                    "chunk_index": global_index,
                    "page_number": page_number,
                    "source_type": source_type,
                }
            )
            global_index += 1

    return all_chunks