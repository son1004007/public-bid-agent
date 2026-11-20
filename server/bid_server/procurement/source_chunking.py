"""P0-03: deterministic, lossless UTF-8 source span splitting.

Trust boundary: input text is already parser-extracted, not a claimed byte
offset in the original HWPX archive. Locators are offsets within the exact
extracted paragraph, table cell, or footnote text; original archive bytes
remain attached to DocumentVersion SHA-256 and ExtractionRun FK.
No source text is truncated, silently filtered, normalized or discarded.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass


MAX_CHUNK_UTF8_BYTES = 1800
MAX_CHUNKS_PER_BLOCK = 2048


class SourceChunkError(ValueError):
    pass


@dataclass(frozen=True)
class SourceSpan:
    text: str
    char_start: int
    char_end: int
    utf8_start: int
    utf8_end: int
    source_text_sha256: str
    span_sha256: str

    @property
    def locator(self) -> dict:
        return {
            "char_start": self.char_start,
            "char_end": self.char_end,
            "utf8_start": self.utf8_start,
            "utf8_end": self.utf8_end,
            "source_text_sha256": self.source_text_sha256,
            "span_sha256": self.span_sha256,
            "offset_origin": "EXTRACTED_BLOCK_TEXT",
        }


def split_source_text(text: str, *, limit: int = MAX_CHUNK_UTF8_BYTES) -> tuple[SourceSpan, ...]:
    """Return 1..N exact contiguous slices with stable codepoint and byte offsets.

    Whitespace, Unicode combining marks and newlines are preserved. Codepoints
    are never cut across UTF-8 byte sequences. A caller must preserve all
    spans and never interpret these offsets as archive XML byte offsets.
    """
    if (type(text) is not str or not text or "\x00" in text
            or type(limit) is not int or not 1 <= limit <= MAX_CHUNK_UTF8_BYTES):
        raise SourceChunkError("INVALID_SOURCE_TEXT_OR_LIMIT")
    try:
        encoded = text.encode("utf-8", errors="strict")
    except UnicodeError:
        raise SourceChunkError("INVALID_SOURCE_UNICODE") from None
    source_sha = hashlib.sha256(encoded).hexdigest()
    spans = []
    char_start = byte_start = char_end = byte_end = 0
    for character in text:
        try:
            char_bytes = character.encode("utf-8", errors="strict")
        except UnicodeError:
            raise SourceChunkError("INVALID_SOURCE_UNICODE") from None
        size = len(char_bytes)
        if size > limit:
            raise SourceChunkError("CHUNK_LIMIT_BELOW_UTF8_CODEPOINT")
        if byte_end > byte_start and byte_end - byte_start + size > limit:
            fragment = text[char_start:char_end]
            data = fragment.encode("utf-8")
            spans.append(SourceSpan(
                fragment, char_start, char_end, byte_start, byte_end,
                source_sha, hashlib.sha256(data).hexdigest(),
            ))
            if len(spans) >= MAX_CHUNKS_PER_BLOCK:
                raise SourceChunkError("CHUNK_BLOCK_LIMIT_EXCEEDED")
            char_start, byte_start = char_end, byte_end
        char_end += 1
        byte_end += size
    if byte_end > byte_start:
        fragment = text[char_start:char_end]
        spans.append(SourceSpan(
            fragment, char_start, char_end, byte_start, byte_end,
            source_sha, hashlib.sha256(fragment.encode("utf-8")).hexdigest(),
        ))
    if not spans or len(spans) > MAX_CHUNKS_PER_BLOCK:
        raise SourceChunkError("CHUNK_BLOCK_LIMIT_EXCEEDED")
    if ("".join(span.text for span in spans) != text
            or b"".join(span.text.encode("utf-8") for span in spans) != encoded):
        raise SourceChunkError("CHUNK_LOSS_DETECTED")
    return tuple(spans)
