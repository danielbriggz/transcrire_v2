import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from services.groq import (
    transcribe_file, transcribe_chunks,
    GroqTranscriptResult, TranscriptSegment, _parse_response
)
from utils.retry import TransientError, PermanentError, TranscriptionError


def test_transcribe_file_returns_result(mock_groq_response, tmp_audio):
    with patch("services.groq._get_client") as mock_client:
        mock_client.return_value.audio.transcriptions.create.return_value = mock_groq_response
        result = transcribe_file(tmp_audio)

    assert isinstance(result, GroqTranscriptResult)
    assert result.full_text == "This is a test transcript from Groq."
    assert len(result.segments) == 2
    assert result.language == "en"
    assert result.duration_s == 5.0


def test_transcribe_file_raises_transient_on_429(tmp_audio):
    from groq import APIStatusError
    mock_err = MagicMock(spec=APIStatusError)
    mock_err.status_code = 429

    with patch("services.groq._get_client") as mock_client:
        mock_client.return_value.audio.transcriptions.create.side_effect = mock_err
        with pytest.raises(TransientError):
            transcribe_file.__wrapped__(tmp_audio)  # bypass retry decorator


def test_transcribe_file_raises_permanent_on_401(tmp_audio):
    from groq import APIStatusError
    mock_err = MagicMock(spec=APIStatusError)
    mock_err.status_code = 401

    with patch("services.groq._get_client") as mock_client:
        mock_client.return_value.audio.transcriptions.create.side_effect = mock_err
        with pytest.raises(PermanentError):
            transcribe_file.__wrapped__(tmp_audio)


def test_get_client_raises_permanent_when_no_api_key():
    with patch("services.groq.config") as mock_config:
        mock_config.groq_api_key = ""
        import services.groq as groq_module
        groq_module._client = None  # reset lazy client
        with pytest.raises(PermanentError, match="GROQ_API_KEY"):
            groq_module._get_client()


def test_transcribe_chunks_stitches_segments(mock_groq_response, tmp_path):
    chunk1 = tmp_path / "chunk_000.mp3"
    chunk2 = tmp_path / "chunk_001.mp3"
    chunk1.write_bytes(b"\x00")
    chunk2.write_bytes(b"\x00")

    with patch("services.groq.transcribe_file", return_value=GroqTranscriptResult(
        full_text="Hello world.",
        segments=[TranscriptSegment(start=0.0, end=2.0, text="Hello world.")],
        language="en",
        duration_s=10.0,
    )):
        result = transcribe_chunks([chunk1, chunk2])

    assert len(result.segments) == 2
    # Second chunk segments should be offset by 10.0s
    assert result.segments[1].start == pytest.approx(10.0)


def test_transcribe_chunks_resumes_from_checkpoint(tmp_path):
    chunk1 = tmp_path / "chunk_000.mp3"
    chunk2 = tmp_path / "chunk_001.mp3"
    chunk1.write_bytes(b"\x00")
    chunk2.write_bytes(b"\x00")

    saved_checkpoint = {
        "last_chunk_index": 0,
        "segments": [{"start": 0.0, "end": 2.0, "text": "Already done."}],
        "time_offset": 10.0,
    }

    call_count = {"n": 0}

    def fake_transcribe(path, **kwargs):
        call_count["n"] += 1
        return GroqTranscriptResult(
            full_text="Second chunk.",
            segments=[TranscriptSegment(0.0, 2.0, "Second chunk.")],
            duration_s=10.0,
        )

    with patch("services.groq.transcribe_file", side_effect=fake_transcribe):
        result = transcribe_chunks(
            [chunk1, chunk2],
            checkpoint_load_fn=lambda: saved_checkpoint,
        )

    # Only chunk2 should be transcribed (chunk1 already checkpointed)
    assert call_count["n"] == 1
    assert len(result.segments) == 2