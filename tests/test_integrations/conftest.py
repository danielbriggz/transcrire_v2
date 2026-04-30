"""
Shared fixtures for Phase 3 integration and unit tests.
Unit tests: fast, no network, no API keys, always run.
Integration tests: marked @pytest.mark.integration, require real keys + FFmpeg.
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock


# ─── RSS Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def sample_rss_xml():
    """Minimal valid RSS feed with one fully-tagged episode."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
      <channel>
        <title>Test Podcast</title>
        <item>
          <title>Episode 1 - Pilot</title>
          <itunes:episode>1</itunes:episode>
          <itunes:season>1</itunes:season>
          <enclosure url="https://example.com/ep1.mp3" type="audio/mpeg" length="12345"/>
          <pubDate>Mon, 01 Jan 2024 10:00:00 +0000</pubDate>
          <itunes:image href="https://example.com/cover.jpg"/>
          <description>First episode description.</description>
        </item>
        <item>
          <title>Episode 2 - Follow Up</title>
          <itunes:episode>2</itunes:episode>
          <itunes:season>1</itunes:season>
          <enclosure url="https://example.com/ep2.mp3" type="audio/mpeg" length="23456"/>
          <pubDate>Mon, 08 Jan 2024 10:00:00 +0000</pubDate>
        </item>
      </channel>
    </rss>"""


@pytest.fixture
def sample_rss_xml_no_itunes():
    """RSS feed entries with no itunes tags — forces positional matching fallback."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Bare Podcast</title>
        <item>
          <title>First Episode</title>
          <enclosure url="https://example.com/bare1.mp3" type="audio/mpeg" length="9999"/>
          <pubDate>Mon, 01 Jan 2024 10:00:00 +0000</pubDate>
        </item>
      </channel>
    </rss>"""


@pytest.fixture
def sample_rss_xml_no_enclosure():
    """RSS entry missing the audio enclosure — match_episode should raise RSSError."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
      <channel>
        <title>Bad Feed</title>
        <item>
          <title>Episode With No Audio</title>
          <itunes:episode>1</itunes:episode>
        </item>
      </channel>
    </rss>"""


# ─── Groq Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def mock_groq_segment():
    seg = MagicMock()
    seg.start = 0.0
    seg.end = 2.5
    seg.text = "This is a test transcript."
    return seg


@pytest.fixture
def mock_groq_response(mock_groq_segment):
    mock = MagicMock()
    mock.text = "This is a test transcript."
    mock.segments = [mock_groq_segment]
    mock.language = "en"
    mock.duration = 2.5
    return mock


@pytest.fixture
def mock_groq_client(mock_groq_response):
    """Fully-mocked Groq client that returns mock_groq_response."""
    client = MagicMock()
    client.audio.transcriptions.create.return_value = mock_groq_response
    return client


# ─── Gemini Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def mock_gemini_response():
    mock = MagicMock()
    mock.text = "This is a generated caption."
    return mock


@pytest.fixture
def mock_gemini_model(mock_gemini_response):
    model = MagicMock()
    model.generate_content.return_value = mock_gemini_response
    return model


# ─── Audio Fixtures ───────────────────────────────────────────────────────────

FFPROBE_SAMPLE_OUTPUT = """{
    "streams": [
        {
            "index": 0,
            "codec_type": "audio",
            "duration": "123.456"
        }
    ]
}"""


@pytest.fixture
def mock_ffprobe_result():
    """Simulates a successful ffprobe subprocess result."""
    result = MagicMock()
    result.returncode = 0
    result.stdout = FFPROBE_SAMPLE_OUTPUT
    result.stderr = ""
    return result


@pytest.fixture
def mock_ffmpeg_result():
    """Simulates a successful ffmpeg subprocess result."""
    result = MagicMock()
    result.returncode = 0
    result.stdout = ""
    result.stderr = ""
    return result


@pytest.fixture
def small_mp3_file(tmp_path) -> Path:
    """Create a tiny fake MP3 file well under the 25 MB Groq limit."""
    f = tmp_path / "small.mp3"
    f.write_bytes(b"\xff\xfb" * 100)   # dummy MP3 header bytes
    return f


@pytest.fixture
def large_mp3_file(tmp_path) -> Path:
    """Create a fake file over the 25 MB Groq limit to trigger chunking."""
    f = tmp_path / "large.mp3"
    f.write_bytes(b"\x00" * (26 * 1024 * 1024))  # 26 MB
    return f


# ─── Whisper Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def mock_whisper_model():
    """Mock whisper model whose transcribe() returns a dict matching real output."""
    model = MagicMock()
    model.transcribe.return_value = {
        "text": "Local whisper transcript.",
        "language": "en",
        "segments": [
            {"start": 0.0, "end": 3.1, "text": "Local whisper transcript."},
        ],
    }
    return model


@pytest.fixture
def mock_whisper_module(mock_whisper_model):
    """Mock the whisper top-level module returned by the lazy import."""
    whisper = MagicMock()
    whisper.load_model.return_value = mock_whisper_model
    return whisper


# ─── General ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_transcript():
    return (
        "Welcome to the show. Today we discuss the future of AI and its "
        "impact on creative industries. Our guest shares their perspective "
        "on where things are heading in the next five years."
    )