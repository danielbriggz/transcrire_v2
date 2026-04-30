"""
Tests for services/whisper.py
#33 — unit tests (always run, whisper module mocked)
#34 — integration tests (require openai-whisper installed + a real audio file)
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from services.groq import GroqTranscriptResult, TranscriptSegment
from utils.retry import PermanentError, TranscriptionError


class TestGetWhisper:
    """Lazy import logic — no real whisper needed."""

    def test_raises_permanent_error_when_not_installed(self):
        """If openai-whisper is absent, PermanentError should be raised on first use."""
        import services.whisper as whisper_service
        # Reset cached module
        original = whisper_service._whisper
        whisper_service._whisper = None

        with patch("builtins.__import__", side_effect=ImportError("No module named 'whisper'")):
            with pytest.raises(PermanentError, match="openai-whisper is not installed"):
                from services.whisper import _get_whisper
                _get_whisper()

        whisper_service._whisper = original  # restore

    def test_caches_whisper_module_on_second_call(self, mock_whisper_module):
        import services.whisper as whisper_service
        whisper_service._whisper = None

        with patch("services.whisper._whisper", None):
            with patch.dict("sys.modules", {"whisper": mock_whisper_module}):
                from services.whisper import _get_whisper
                result1 = _get_whisper()
                result2 = _get_whisper()

        assert result1 is result2


class TestTranscribeFile:
    """All tests mock the whisper module — no GPU or model download required."""

    def test_returns_groq_transcript_result_type(self, tmp_path, mock_whisper_module):
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"\xff\xfb" * 50)

        import services.whisper as whisper_service
        whisper_service._whisper = mock_whisper_module

        from services.whisper import transcribe_file
        result = transcribe_file(audio)

        assert isinstance(result, GroqTranscriptResult)

    def test_full_text_extracted_from_result(self, tmp_path, mock_whisper_module):
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"\xff\xfb" * 50)

        import services.whisper as whisper_service
        whisper_service._whisper = mock_whisper_module

        from services.whisper import transcribe_file
        result = transcribe_file(audio)

        assert result.full_text == "Local whisper transcript."

    def test_segments_parsed_correctly(self, tmp_path, mock_whisper_module):
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"\xff\xfb" * 50)

        import services.whisper as whisper_service
        whisper_service._whisper = mock_whisper_module

        from services.whisper import transcribe_file
        result = transcribe_file(audio)

        assert len(result.segments) == 1
        seg = result.segments[0]
        assert isinstance(seg, TranscriptSegment)
        assert seg.start == 0.0
        assert seg.end == 3.1
        assert seg.text == "Local whisper transcript."

    def test_language_populated_from_result(self, tmp_path, mock_whisper_module):
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"\xff\xfb" * 50)

        import services.whisper as whisper_service
        whisper_service._whisper = mock_whisper_module

        from services.whisper import transcribe_file
        result = transcribe_file(audio)

        assert result.language == "en"

    def test_correct_model_size_passed_to_load_model(self, tmp_path, mock_whisper_module):
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"\xff\xfb" * 50)

        import services.whisper as whisper_service
        whisper_service._whisper = mock_whisper_module

        from services.whisper import transcribe_file
        transcribe_file(audio, model_size="small")

        mock_whisper_module.load_model.assert_called_once_with("small")

    def test_language_passed_to_transcribe(self, tmp_path, mock_whisper_module):
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"\xff\xfb" * 50)

        import services.whisper as whisper_service
        whisper_service._whisper = mock_whisper_module

        from services.whisper import transcribe_file
        transcribe_file(audio, language="fr")

        model = mock_whisper_module.load_model.return_value
        _, kwargs = model.transcribe.call_args
        assert kwargs.get("language") == "fr"

    def test_transcription_exception_raises_transcription_error(self, tmp_path, mock_whisper_module):
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"\xff\xfb" * 50)
        mock_whisper_module.load_model.return_value.transcribe.side_effect = RuntimeError("CUDA OOM")

        import services.whisper as whisper_service
        whisper_service._whisper = mock_whisper_module

        from services.whisper import transcribe_file
        with pytest.raises(TranscriptionError, match="Whisper transcription failed"):
            transcribe_file(audio)

    def test_result_type_is_compatible_with_groq_result(self, tmp_path, mock_whisper_module):
        """
        Whisper and Groq must return the same type so pipeline.py
        has no conditional branching between cloud and local paths.
        """
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"\xff\xfb" * 50)

        import services.whisper as whisper_service
        whisper_service._whisper = mock_whisper_module

        from services.whisper import transcribe_file as whisper_transcribe
        result = whisper_transcribe(audio)

        # Validate all GroqTranscriptResult fields are present
        assert hasattr(result, "full_text")
        assert hasattr(result, "segments")
        assert hasattr(result, "language")
        assert hasattr(result, "duration_s")

    def test_empty_segments_list_when_not_present(self, tmp_path, mock_whisper_module):
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"\xff\xfb" * 50)
        mock_whisper_module.load_model.return_value.transcribe.return_value = {
            "text": "No segments here.",
            "language": "en",
            # no "segments" key
        }

        import services.whisper as whisper_service
        whisper_service._whisper = mock_whisper_module

        from services.whisper import transcribe_file
        result = transcribe_file(audio)

        assert result.full_text == "No segments here."
        assert result.segments == []


# ══════════════════════════════════════════════════════════════════════════════
# Integration Tests — require openai-whisper installed
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
def test_whisper_real_transcription():
    """
    Requires openai-whisper installed (`uv add openai-whisper`) and
    a real audio fixture at tests/fixtures/sample.mp3.
    Downloads the 'base' model on first run (~145MB).
    """
    from services.whisper import transcribe_file
    audio = Path("tests/fixtures/sample.mp3")
    result = transcribe_file(audio, model_size="base")

    assert isinstance(result, GroqTranscriptResult)
    assert result.full_text
    assert result.language is not None


@pytest.mark.integration
def test_whisper_result_shape_matches_groq_shape():
    """Ensure field names are identical to GroqTranscriptResult so the pipeline is interchangeable."""
    from services.whisper import transcribe_file
    audio = Path("tests/fixtures/sample.mp3")
    result = transcribe_file(audio, model_size="tiny")  # fastest model for CI

    for seg in result.segments:
        assert isinstance(seg, TranscriptSegment)
        assert isinstance(seg.start, float)
        assert isinstance(seg.end, float)
        assert isinstance(seg.text, str)