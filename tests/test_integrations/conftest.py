import pytest
from pathlib import Path
from unittest.mock import MagicMock


@pytest.fixture
def sample_rss_xml():
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
def mock_groq_response():
    mock = MagicMock()
    mock.text = "This is a test transcript from Groq."
    mock.language = "en"
    mock.duration = 5.0
    mock.segments = [
        MagicMock(start=0.0, end=2.5, text="This is a test transcript"),
        MagicMock(start=2.5, end=5.0, text="from Groq."),
    ]
    return mock


@pytest.fixture
def mock_gemini_response():
    mock = MagicMock()
    mock.text = "This is a generated caption for the episode."
    return mock


@pytest.fixture
def tmp_audio(tmp_path): # type: ignore
    """Create a minimal valid-looking audio file for path-based tests."""
    audio = tmp_path / "sample.mp3" # type: ignore
    audio.write_bytes(b"\xff\xfb" + b"\x00" * 1024)  # type: ignore # fake MP3 header
    return audio # type: ignore