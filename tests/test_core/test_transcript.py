import pytest
from services.groq import TranscriptSegment
from core.transcript import (
    format_plain,
    format_with_timestamps,
    stitch_chunks,
    build_formatted_transcript,
    truncate_for_prompt,
)


@pytest.fixture
def sample_segments():
    return [
        TranscriptSegment(start=0.0,   end=2.5,  text="Welcome to the show."),
        TranscriptSegment(start=2.5,   end=5.0,  text="Today we talk about habits."),
        TranscriptSegment(start=65.0,  end=68.0, text="The first tip is consistency."),
    ]


# ── format_plain ──────────────────────────────────────────────────────────────

def test_format_plain_joins_segments(sample_segments):
    result = format_plain(sample_segments)
    assert result == "Welcome to the show. Today we talk about habits. The first tip is consistency."


def test_format_plain_skips_empty_segments():
    segments = [
        TranscriptSegment(0.0, 1.0, "Hello"),
        TranscriptSegment(1.0, 2.0, "   "),   # whitespace only
        TranscriptSegment(2.0, 3.0, "World"),
    ]
    result = format_plain(segments)
    assert result == "Hello World"


def test_format_plain_empty_list():
    assert format_plain([]) == ""


# ── format_with_timestamps ────────────────────────────────────────────────────

def test_format_with_timestamps_correct_format(sample_segments):
    result = format_with_timestamps(sample_segments)
    lines = result.split("\n")
    assert lines[0] == "[00:00] Welcome to the show."
    assert lines[1] == "[00:02] Today we talk about habits."
    assert lines[2] == "[01:05] The first tip is consistency."


def test_format_with_timestamps_pads_minutes_and_seconds():
    segments = [TranscriptSegment(start=3661.0, end=3663.0, text="Late segment.")]
    result = format_with_timestamps(segments)
    assert "[61:01]" in result


def test_format_with_timestamps_empty_list():
    assert format_with_timestamps([]) == ""


# ── stitch_chunks ─────────────────────────────────────────────────────────────

def test_stitch_chunks_offsets_correctly():
    chunk1 = [TranscriptSegment(0.0, 5.0, "First chunk.")]
    chunk2 = [TranscriptSegment(0.0, 5.0, "Second chunk.")]
    result = stitch_chunks([chunk1, chunk2], chunk_duration_s=600.0)

    assert result[0].start == pytest.approx(0.0)
    assert result[1].start == pytest.approx(600.0)
    assert result[1].end == pytest.approx(605.0)


def test_stitch_chunks_preserves_text():
    chunk1 = [TranscriptSegment(0.0, 2.0, "Hello.")]
    chunk2 = [TranscriptSegment(0.0, 2.0, "World.")]
    result = stitch_chunks([chunk1, chunk2], chunk_duration_s=10.0)
    assert result[0].text == "Hello."
    assert result[1].text == "World."


def test_stitch_chunks_single_chunk_no_offset():
    chunk = [TranscriptSegment(1.0, 3.0, "Only chunk.")]
    result = stitch_chunks([chunk], chunk_duration_s=600.0)
    assert result[0].start == pytest.approx(1.0)


def test_stitch_chunks_empty_returns_empty():
    assert stitch_chunks([], chunk_duration_s=600.0) == []


# ── build_formatted_transcript ────────────────────────────────────────────────

def test_build_formatted_transcript_word_count(sample_segments):
    result = build_formatted_transcript(sample_segments)
    assert result.word_count == 14


def test_build_formatted_transcript_segment_count(sample_segments):
    result = build_formatted_transcript(sample_segments)
    assert result.segment_count == 3


def test_build_formatted_transcript_duration(sample_segments):
    result = build_formatted_transcript(sample_segments, duration_s=120.0)
    assert result.duration_s == 120.0


def test_build_formatted_transcript_duration_none_by_default(sample_segments):
    result = build_formatted_transcript(sample_segments)
    assert result.duration_s is None


def test_build_formatted_transcript_plain_and_segment_text_both_present(sample_segments):
    result = build_formatted_transcript(sample_segments)
    assert len(result.plain_text) > 0
    assert "[00:00]" in result.segment_text


# ── truncate_for_prompt ───────────────────────────────────────────────────────

def test_truncate_short_text_unchanged():
    text = "Short text."
    assert truncate_for_prompt(text, max_chars=100) == text


def test_truncate_cuts_at_sentence_boundary():
    # Sentence ends at position 15 — use max_chars=18 so 80% threshold (14.4) is met
    text = "First sentence. " + "x" * 3000
    result = truncate_for_prompt(text, max_chars=15)
    assert result.endswith(".")
    assert len(result) <= 18


def test_truncate_falls_back_to_hard_cut_when_no_period():
    text = "a" * 5000
    result = truncate_for_prompt(text, max_chars=100)
    assert len(result) == 100


def test_truncate_exact_length_not_truncated():
    text = "x" * 3000
    result = truncate_for_prompt(text, max_chars=3000)
    assert result == text