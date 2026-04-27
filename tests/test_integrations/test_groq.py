import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from services.groq import transcribe_file, GroqTranscriptResult

# ── Fast unit test — no API key needed, runs always ──────────────────
def test_groq_returns_transcript_result(mock_groq_response):
    with patch("services.groq._get_client") as mock_client:
        mock_client.return_value.audio.transcriptions.create.return_value = mock_groq_response
        result = transcribe_file(Path("fake_audio.mp3"))
        assert isinstance(result, GroqTranscriptResult)
        assert result.full_text == "This is a test transcript."


# ── Slow integration test — needs real GROQ_API_KEY in .env ──────────
@pytest.mark.integration
def test_groq_real_transcription():
    real_audio = Path("tests/fixtures/sample.mp3")
    result = transcribe_file(real_audio)
    assert result.full_text
    assert len(result.segments) > 0