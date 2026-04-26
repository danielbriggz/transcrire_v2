# tests/test_integrations/conftest.py
import pytest
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
        </item>
      </channel>
    </rss>"""

@pytest.fixture
def mock_groq_response():
    mock = MagicMock()
    mock.text = "This is a test transcript."
    mock.segments = [MagicMock(start=0.0, end=2.5, text="This is a test transcript.")]
    mock.language = "en"
    mock.duration = 2.5
    return mock

@pytest.fixture
def mock_gemini_response():
    mock = MagicMock()
    mock.text = "This is a generated caption."
    return mock