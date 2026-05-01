import pytest
from unittest.mock import patch, MagicMock
from utils.retry import PermanentError, TranscriptionError


def test_whisper_raises_permanent_when_not_installed(tmp_path):
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"\x00")

    import services.whisper as whisper_module
    whisper_module._whisper = None  # reset lazy import

    with patch("builtins.__import__", side_effect=ImportError("No module named 'whisper'")):
        with pytest.raises(PermanentError, match="not installed"):
            whisper_module._get_whisper()


def test_whisper_result_matches_groq_type(tmp_path):
    from services.whisper import transcribe_file
    from services.groq import GroqTranscriptResult
    import services.whisper as whisper_module

    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"\x00")

    mock_whisper = MagicMock()
    mock_whisper.load_model.return_value.transcribe.return_value = {
        "text": "Local transcription result.",
        "language": "en",
        "segments": [
            {"start": 0.0, "end": 3.0, "text": "Local transcription result."}
        ],
    }
    whisper_module._whisper = mock_whisper

    result = transcribe_file(audio)

    assert isinstance(result, GroqTranscriptResult)
    assert result.full_text == "Local transcription result."
    assert result.language == "en"
    assert len(result.segments) == 1
    assert result.segments[0].start == 0.0


def test_whisper_raises_transcription_error_on_failure(tmp_path):
    from services.whisper import transcribe_file
    import services.whisper as whisper_module

    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"\x00")

    mock_whisper = MagicMock()
    mock_whisper.load_model.return_value.transcribe.side_effect = RuntimeError("model failed")
    whisper_module._whisper = mock_whisper

    with pytest.raises(TranscriptionError, match="failed"):
        transcribe_file(audio)