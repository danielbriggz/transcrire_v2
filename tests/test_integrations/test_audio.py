"""
Tests for services/audio.py
#33 — unit tests (always run, subprocess mocked)
#34 — integration tests (require FFmpeg on PATH)
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock # pyright: ignore[reportUnusedImport]

from services.audio import (
    get_duration,
    compress_audio,
    needs_chunking,
    split_into_chunks,
    GROQ_MAX_BYTES,
    CHUNK_DURATION_SECONDS, # type: ignore
)
from utils.retry import AudioProcessingError


# ══════════════════════════════════════════════════════════════════════════════
# Unit Tests — subprocess fully mocked
# ══════════════════════════════════════════════════════════════════════════════

VALID_froe_JSON = json.dumps({
    "streams": [{"codec_type": "audio", "duration": "123.456"}]
})


class TestGetDuration:

    def test_returns_float_duration(self, mock_ffprobe_result): # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
        mock_ffprobe_result.stdout = VALID_FFPROBE_JSON # pyright: ignore[reportUndefinedVariable]
        with patch("services.audio.subprocess.run", return_value=mock_ffprobe_result):
            duration = get_duration(Path("fake.mp3"))
        assert duration == pytest.approx(123.456) # pyright: ignore[reportUnknownMemberType]

    def test_ffprobe_not_found_raises_audio_error(self):
        with patch("services.audio.subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(AudioProcessingError, match="not found"):
                get_duration(Path("fake.mp3"))

    def test_nonzero_exit_raises_audio_error(self, mock_ffprobe_result): # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
        mock_ffprobe_result.returncode = 1
        mock_ffprobe_result.stderr = "Invalid data"
        with patch("services.audio.subprocess.run", return_value=mock_ffprobe_result):
            with pytest.raises(AudioProcessingError, match="Command failed"):
                get_duration(Path("fake.mp3"))

    def test_malformed_json_raises_audio_error(self, mock_ffprobe_result): # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
        mock_ffprobe_result.stdout = "not json at all"
        with patch("services.audio.subprocess.run", return_value=mock_ffprobe_result):
            with pytest.raises(AudioProcessingError, match="Could not parse"):
                get_duration(Path("fake.mp3"))

    def test_missing_duration_key_raises_audio_error(self, mock_ffprobe_result): # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
        mock_ffprobe_result.stdout = json.dumps({"streams": [{}]})
        with patch("services.audio.subprocess.run", return_value=mock_ffprobe_result):
            with pytest.raises(AudioProcessingError, match="Could not parse"):
                get_duration(Path("fake.mp3"))

    def test_empty_streams_raises_audio_error(self, mock_ffprobe_result): # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
        mock_ffprobe_result.stdout = json.dumps({"streams": []})
        with patch("services.audio.subprocess.run", return_value=mock_ffprobe_result):
            with pytest.raises(AudioProcessingError):
                get_duration(Path("fake.mp3"))


class TestCompressAudio:

    def test_returns_output_path(self, tmp_path, mock_ffmpeg_result): # pyright: ignore[reportUnknownParameterType, reportMissingParameterType]
        input_path = tmp_path / "input.mp3" # pyright: ignore[reportUnknownVariableType]
        input_path.touch() # pyright: ignore[reportUnknownMemberType]
        output_path = tmp_path / "output.mp3" # pyright: ignore[reportUnknownVariableType]

        with patch("services.audio.subprocess.run", return_value=mock_ffmpeg_result):
            result = compress_audio(input_path, output_path) # pyright: ignore[reportUnknownArgumentType]

        assert result == output_path

    def test_creates_parent_directory(self, tmp_path, mock_ffmpeg_result): # pyright: ignore[reportUnknownParameterType, reportMissingParameterType]
        input_path = tmp_path / "input.mp3" # pyright: ignore[reportUnknownVariableType]
        input_path.touch() # pyright: ignore[reportUnknownMemberType]
        output_path = tmp_path / "nested" / "dir" / "output.mp3" # pyright: ignore[reportUnknownVariableType]

        with patch("services.audio.subprocess.run", return_value=mock_ffmpeg_result):
            compress_audio(input_path, output_path) # pyright: ignore[reportUnknownArgumentType]

        assert output_path.parent.exists() # pyright: ignore[reportUnknownMemberType]

    def test_ffmpeg_failure_raises_audio_error(self, tmp_path, mock_ffmpeg_result): # pyright: ignore[reportUnknownParameterType, reportMissingParameterType]
        input_path = tmp_path / "input.mp3" # pyright: ignore[reportUnknownVariableType]
        input_path.touch() # pyright: ignore[reportUnknownMemberType]
        output_path = tmp_path / "output.mp3" # type: ignore
        mock_ffmpeg_result.returncode = 1
        mock_ffmpeg_result.stderr = "No such file"

        with patch("services.audio.subprocess.run", return_value=mock_ffmpeg_result):
            with pytest.raises(AudioProcessingError):
                compress_audio(input_path, output_path) # type: ignore

    def test_command_includes_mono_and_16khz(self, tmp_path, mock_ffmpeg_result): # type: ignore
        """Compression must use -ac 1 (mono) and -ar 16000 (16kHz)."""
        input_path = tmp_path / "input.mp3" # type: ignore
        input_path.touch() # type: ignore
        output_path = tmp_path / "output.mp3" # pyright: ignore[reportUnknownVariableType]
        captured_cmd = []

        def capture(cmd, **kwargs): # type: ignore
            captured_cmd.extend(cmd) # type: ignore
            return mock_ffmpeg_result # pyright: ignore[reportUnknownVariableType]

        with patch("services.audio.subprocess.run", side_effect=capture):
            compress_audio(input_path, output_path) # type: ignore

        assert "-ac" in captured_cmd
        assert "1" in captured_cmd
        assert "-ar" in captured_cmd
        assert "16000" in captured_cmd


class TestNeedsChunking:

    def test_small_file_does_not_need_chunking(self, small_mp3_file): # type: ignore
        assert needs_chunking(small_mp3_file) is False # type: ignore

    def test_large_file_needs_chunking(self, large_mp3_file): # type: ignore
        assert needs_chunking(large_mp3_file) is True # type: ignore

    def test_exactly_at_limit_does_not_need_chunking(self, tmp_path): # type: ignore
        f = tmp_path / "exact.mp3" # type: ignore
        f.write_bytes(b"\x00" * GROQ_MAX_BYTES) # type: ignore
        assert needs_chunking(f) is False

    def test_one_byte_over_limit_needs_chunking(self, tmp_path):
        f = tmp_path / "over.mp3"
        f.write_bytes(b"\x00" * (GROQ_MAX_BYTES + 1))
        assert needs_chunking(f) is True


class TestSplitIntoChunks:

    def test_returns_sorted_chunk_paths(self, tmp_path, mock_ffmpeg_result):
        input_path = tmp_path / "input.mp3"
        input_path.touch()
        output_dir = tmp_path / "chunks"

        # Simulate ffmpeg creating chunk files
        def fake_run(cmd, **kwargs):
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "chunk_000.mp3").touch()
            (output_dir / "chunk_001.mp3").touch()
            (output_dir / "chunk_002.mp3").touch()
            return mock_ffmpeg_result

        with patch("services.audio.subprocess.run", side_effect=fake_run):
            chunks = split_into_chunks(input_path, output_dir)

        assert len(chunks) == 3
        names = [c.name for c in chunks]
        assert names == sorted(names)

    def test_creates_output_directory(self, tmp_path, mock_ffmpeg_result):
        input_path = tmp_path / "input.mp3"
        input_path.touch()
        output_dir = tmp_path / "does_not_exist_yet"

        with patch("services.audio.subprocess.run", return_value=mock_ffmpeg_result):
            split_into_chunks(input_path, output_dir)

        assert output_dir.exists()

    def test_command_uses_segment_muxer(self, tmp_path, mock_ffmpeg_result):
        input_path = tmp_path / "input.mp3"
        input_path.touch()
        output_dir = tmp_path / "chunks"
        captured = []

        def capture(cmd, **kwargs):
            captured.extend(cmd)
            return mock_ffmpeg_result

        with patch("services.audio.subprocess.run", side_effect=capture):
            split_into_chunks(input_path, output_dir)

        assert "-f" in captured
        assert "segment" in captured
        assert "-segment_time" in captured

    def test_ffmpeg_not_found_raises_audio_error(self, tmp_path):
        input_path = tmp_path / "input.mp3"
        input_path.touch()
        with patch("services.audio.subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(AudioProcessingError, match="not found"):
                split_into_chunks(input_path, tmp_path / "chunks")


# ══════════════════════════════════════════════════════════════════════════════
# Integration Tests — require FFmpeg on PATH
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
def test_get_duration_real_file():
    """Requires a real MP3 fixture and FFprobe on PATH."""
    audio = Path("tests/fixtures/sample.mp3")
    duration = get_duration(audio)
    assert isinstance(duration, float)
    assert duration > 0


@pytest.mark.integration
def test_compress_audio_real_file(tmp_path):
    """Requires FFmpeg on PATH."""
    audio = Path("tests/fixtures/sample.mp3")
    output = tmp_path / "compressed.mp3"
    result = compress_audio(audio, output)
    assert result.exists()
    assert result.stat().st_size > 0


@pytest.mark.integration
def test_split_into_chunks_real_file(tmp_path):
    """Requires a long-enough MP3 and FFmpeg on PATH."""
    audio = Path("tests/fixtures/sample_long.mp3")
    output_dir = tmp_path / "chunks"
    chunks = split_into_chunks(audio, output_dir, chunk_duration=10)
    assert len(chunks) >= 1
    for chunk in chunks:
        assert chunk.exists()