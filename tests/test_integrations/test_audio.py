import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from services.audio import (
    get_duration, compress_audio, needs_chunking,
    split_into_chunks, GROQ_MAX_BYTES
)
from utils.retry import AudioProcessingError


@pytest.fixture
def mock_ffprobe_output():
    return '{"streams": [{"duration": "123.456"}]}'


def test_get_duration_parses_ffprobe_output(mock_ffprobe_output, tmp_path): # type: ignore
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = mock_ffprobe_output

    with patch("subprocess.run", return_value=mock_result):
        duration = get_duration(tmp_path / "audio.mp3") # type: ignore

    assert duration == pytest.approx(123.456) # type: ignore


def test_get_duration_raises_on_bad_output(tmp_path): # type: ignore
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = '{"streams": []}'

    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(AudioProcessingError, match="FFprobe"):
            get_duration(tmp_path / "audio.mp3") # type: ignore


def test_get_duration_raises_when_ffprobe_missing(tmp_path): # type: ignore
    with patch("subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(AudioProcessingError, match="not found"):
            get_duration(tmp_path / "audio.mp3") # type: ignore


def test_compress_audio_calls_ffmpeg(tmp_audio, tmp_path): # type: ignore
    output = tmp_path / "compressed.mp3" # type: ignore
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        compress_audio(tmp_audio, output) # type: ignore
        args = mock_run.call_args[0][0]
        assert "ffmpeg" in args
        assert "-ac" in args
        assert "1" in args


def test_needs_chunking_true_for_large_file(tmp_path): # type: ignore
    large = tmp_path / "large.mp3" # type: ignore
    large.write_bytes(b"\x00" * (GROQ_MAX_BYTES + 1)) # type: ignore
    assert needs_chunking(large) is True # type: ignore


def test_needs_chunking_false_for_small_file(tmp_audio):
    assert needs_chunking(tmp_audio) is False


def test_split_into_chunks_calls_ffmpeg(tmp_audio, tmp_path):
    mock_result = MagicMock()
    mock_result.returncode = 0

    # Simulate chunk files being created
    (tmp_path / "chunk_000.mp3").write_bytes(b"\x00")
    (tmp_path / "chunk_001.mp3").write_bytes(b"\x00")

    with patch("subprocess.run", return_value=mock_result):
        chunks = split_into_chunks(tmp_audio, tmp_path)

    assert len(chunks) == 2
    assert all(c.name.startswith("chunk_") for c in chunks)