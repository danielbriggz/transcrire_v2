from dataclasses import dataclass
from typing import Optional

from services.groq import TranscriptSegment


@dataclass
class FormattedTranscript:
    """Multiple representations of the same transcript content."""
    plain_text: str
    segment_text: str        # Text with [MM:SS] timestamps per segment
    word_count: int
    duration_s: Optional[float]
    segment_count: int


def format_plain(segments: list[TranscriptSegment]) -> str:
    """Join all segment text into a single continuous string."""
    return " ".join(seg.text.strip() for seg in segments if seg.text.strip())


def format_with_timestamps(segments: list[TranscriptSegment]) -> str:
    """
    Format segments with human-readable timestamps.

    Output example:
        [00:00] Welcome to the show. Today we're talking about...
        [01:23] The first thing to understand is...
    """
    lines = []
    for seg in segments:
        minutes = int(seg.start // 60)
        seconds = int(seg.start % 60)
        lines.append(f"[{minutes:02d}:{seconds:02d}] {seg.text.strip()}")
    return "\n".join(lines)


def stitch_chunks(
    chunk_results: list[list[TranscriptSegment]],
    chunk_duration_s: float,
) -> list[TranscriptSegment]:
    """
    Merge segments from multiple audio chunks into a single ordered list.
    Offsets timestamps so they reflect position in the full episode.
    """
    stitched = []
    for chunk_index, segments in enumerate(chunk_results):
        offset = chunk_index * chunk_duration_s
        for seg in segments:
            stitched.append(TranscriptSegment(
                start=seg.start + offset,
                end=seg.end + offset,
                text=seg.text,
            ))
    return stitched


def build_formatted_transcript(
    segments: list[TranscriptSegment],
    duration_s: Optional[float] = None,
) -> FormattedTranscript:
    """Primary entry point. Build a FormattedTranscript from a list of segments."""
    plain = format_plain(segments)
    return FormattedTranscript(
        plain_text=plain,
        segment_text=format_with_timestamps(segments),
        word_count=len(plain.split()),
        duration_s=duration_s,
        segment_count=len(segments),
    )


def truncate_for_prompt(text: str, max_chars: int = 3000) -> str:
    """
    Truncate transcript text for use in API prompts.
    Cuts at the last sentence boundary within the limit where possible.
    """
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_period = truncated.rfind(".")
    if last_period > max_chars * 0.8:
        return truncated[:last_period + 1]
    return truncated