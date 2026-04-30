"""
Tests for services/groq.py
#33 — unit tests (always run, Groq client mocked)
#34 — integration tests (require real GROQ_API_KEY in .env)
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from services.groq import (
    transcribe_file,
    transcribe_chunks,
    GroqTranscriptResult,
    TranscriptSegment,
    _parse_response,
)
from utils.retry import TransientError, PermanentError, TranscriptionError


# ══════════════════════════════════════════════════════════════════════════════
# Unit Tests — Groq client fully mocked
# ══════════════════════════════════════════════════════════════════════════════

class TestTranscribeFile:

    def test_returns_groq_transcript_result(self, tmp_path, mock_groq_client, mock_groq_response):
        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"\xff\xfb" * 50)

        with patch("services.groq._get_client", return_value=mock_groq_client):
            result = transcribe_file(audio)

        assert isinstance(result, GroqTranscriptResult)

    def test_full_text_matches_response(self, tmp_path, mock_groq_client, mock_groq_response):
        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"\xff\xfb" * 50)

        with patch("services.groq._get_client", return_value=mock_groq_client):
            result = transcribe_file(audio)

        assert result.full_text == "This is a test transcript."

    def test_segments_parsed_correctly(self, tmp_path, mock_groq_client):
        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"\xff\xfb" * 50)

        with patch("services.groq._get_client", return_value=mock_groq_client):
            result = transcribe_file(audio)

        assert len(result.segments) == 1
        assert result.segments[0].start == 0.0
        assert result.segments[0].end == 2.5
        assert result.segments[0].text == "This is a test transcript."

    def test_language_and_duration_populated(self, tmp_path, mock_groq_client):
        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"\xff\xfb" * 50)

        with patch("services.groq._get_client", return_value=mock_groq_client):
            result = transcribe_file(audio)

        assert result.language == "en"
        assert result.duration_s == 2.5

    def test_timeout_raises_transient_error(self, tmp_path, mock_groq_client):
        from groq import APITimeoutError
        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"\xff\xfb" * 50)
        mock_groq_client.audio.transcriptions.create.side_effect = APITimeoutError.__new__(APITimeoutError)

        with patch("services.groq._get_client", return_value=mock_groq_client):
            with pytest.raises(TransientError, match="timed out"):
                transcribe_file(audio)

    def test_connection_error_raises_transient_error(self, tmp_path, mock_groq_client):
        from groq import APIConnectionError
        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"\xff\xfb" * 50)
        mock_groq_client.audio.transcriptions.create.side_effect = APIConnectionError.__new__(APIConnectionError)

        with patch("services.groq._get_client", return_value=mock_groq_client):
            with pytest.raises(TransientError, match="connection error"):
                transcribe_file(audio)

    def test_rate_limit_429_raises_transient_error(self, tmp_path, mock_groq_client):
        from groq import APIStatusError
        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"\xff\xfb" * 50)
        err = MagicMock(spec=APIStatusError)
        err.status_code = 429
        mock_groq_client.audio.transcriptions.create.side_effect = err

        with patch("services.groq._get_client", return_value=mock_groq_client):
            with pytest.raises(TransientError, match="rate limit"):
                transcribe_file(audio)

    def test_401_raises_permanent_error(self, tmp_path, mock_groq_client):
        from groq import APIStatusError
        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"\xff\xfb" * 50)
        err = MagicMock(spec=APIStatusError)
        err.status_code = 401
        mock_groq_client.audio.transcriptions.create.side_effect = err

        with patch("services.groq._get_client", return_value=mock_groq_client):
            with pytest.raises(PermanentError, match="authentication"):
                transcribe_file(audio)

    def test_missing_api_key_raises_permanent_error(self, tmp_path):
        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"\xff\xfb" * 50)

        with patch("services.groq.config") as mock_config:
            mock_config.groq_api_key = None
            # Reset global client so it re-initialises
            with patch("services.groq._client", None):
                with pytest.raises(PermanentError, match="GROQ_API_KEY"):
                    transcribe_file(audio)


class TestTranscribeChunks:

    def _make_chunks(self, tmp_path, n: int) -> list[Path]:
        chunks = []
        for i in range(n):
            p = tmp_path / f"chunk_{i:03d}.mp3"
            p.write_bytes(b"\xff\xfb" * 50)
            chunks.append(p)
        return chunks

    def test_merges_all_chunks(self, tmp_path, mock_groq_client):
        chunks = self._make_chunks(tmp_path, 3)

        with patch("services.groq._get_client", return_value=mock_groq_client):
            result = transcribe_chunks(chunks)

        assert isinstance(result, GroqTranscriptResult)
        # 3 chunks × 1 segment each = 3 segments total
        assert len(result.segments) == 3

    def test_time_offset_applied_to_segments(self, tmp_path, mock_groq_client, mock_groq_response):
        """Each chunk's segments should be offset by the previous chunk's duration."""
        chunks = self._make_chunks(tmp_path, 2)

        with patch("services.groq._get_client", return_value=mock_groq_client):
            result = transcribe_chunks(chunks)

        # First chunk: offset 0.0 → seg starts at 0.0
        # Second chunk: offset 2.5 (duration of first) → seg starts at 2.5
        assert result.segments[0].start == pytest.approx(0.0)
        assert result.segments[1].start == pytest.approx(2.5)

    def test_checkpoint_save_called_after_each_chunk(self, tmp_path, mock_groq_client):
        chunks = self._make_chunks(tmp_path, 2)
        save_calls = []

        def save_fn(index, segments, time_offset):
            save_calls.append((index, time_offset))

        with patch("services.groq._get_client", return_value=mock_groq_client):
            transcribe_chunks(chunks, checkpoint_save_fn=save_fn)

        assert len(save_calls) == 2
        assert save_calls[0][0] == 0
        assert save_calls[1][0] == 1

    def test_checkpoint_resume_skips_completed_chunks(self, tmp_path, mock_groq_client):
        chunks = self._make_chunks(tmp_path, 3)
        transcribe_calls = []

        def counting_transcribe(path, **kwargs):
            transcribe_calls.append(path)
            return GroqTranscriptResult(
                full_text="chunk text",
                segments=[TranscriptSegment(start=0.0, end=2.5, text="chunk text")],
                language="en",
                duration_s=2.5,
            )

        saved_checkpoint = {
            "last_chunk_index": 1,   # chunks 0 and 1 already done
            "segments": [
                {"start": 0.0, "end": 2.5, "text": "chunk 0"},
                {"start": 2.5, "end": 5.0, "text": "chunk 1"},
            ],
            "time_offset": 5.0,
        }

        with patch("services.groq.transcribe_file", side_effect=counting_transcribe):
            transcribe_chunks(
                chunks,
                checkpoint_load_fn=lambda: saved_checkpoint,
            )

        # Only chunk 2 should be transcribed
        assert len(transcribe_calls) == 1
        assert transcribe_calls[0] == chunks[2]

    def test_full_text_joins_all_segment_texts(self, tmp_path, mock_groq_client):
        chunks = self._make_chunks(tmp_path, 2)

        with patch("services.groq._get_client", return_value=mock_groq_client):
            result = transcribe_chunks(chunks)

        # Each mocked chunk returns "This is a test transcript."
        assert "This is a test transcript." in result.full_text

    def test_empty_chunk_list_returns_empty_result(self):
        result = transcribe_chunks([])
        assert result.full_text == ""
        assert result.segments == []


class TestParseResponse:

    def test_verbose_json_parses_segments(self):
        seg = MagicMock()
        seg.start = 1.0
        seg.end = 3.5
        seg.text = "Hello world."

        response = MagicMock()
        response.text = "Hello world."
        response.segments = [seg]
        response.language = "en"
        response.duration = 3.5

        result = _parse_response(response, "verbose_json")

        assert result.full_text == "Hello world."
        assert len(result.segments) == 1
        assert result.segments[0].start == 1.0
        assert result.language == "en"
        assert result.duration_s == 3.5

    def test_text_format_returns_plain_string(self):
        response = "Plain transcript text."
        result = _parse_response(response, "text")
        assert result.full_text == "Plain transcript text."
        assert result.segments == []


# ══════════════════════════════════════════════════════════════════════════════
# Integration Tests — require GROQ_API_KEY in .env
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
def test_groq_real_transcription():
    """Requires a real MP3 fixture and GROQ_API_KEY in .env."""
    audio = Path("tests/fixtures/sample.mp3")
    result = transcribe_file(audio)
    assert isinstance(result, GroqTranscriptResult)
    assert result.full_text
    assert len(result.segments) > 0


@pytest.mark.integration
def test_groq_real_chunk_transcription(tmp_path):
    """Requires multiple small MP3 chunks and GROQ_API_KEY in .env."""
    chunks = [
        Path("tests/fixtures/chunk_000.mp3"),
        Path("tests/fixtures/chunk_001.mp3"),
    ]
    result = transcribe_chunks(chunks)
    assert result.full_text
    assert result.segments[1].start >= result.segments[0].end