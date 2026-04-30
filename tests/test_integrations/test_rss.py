"""
Tests for services/rss.py
#33 — unit tests (always run, no network)
#34 — integration tests (require network, marked @pytest.mark.integration)
"""
import pytest
import feedparser
from unittest.mock import patch, MagicMock

from services.rss import fetch_feed, match_episode, download_audio, RSSEpisodeResult
from utils.retry import TransientError, RSSError


# ══════════════════════════════════════════════════════════════════════════════
# Unit Tests — no network, no API keys
# ══════════════════════════════════════════════════════════════════════════════

class TestMatchEpisode:
    """match_episode works entirely on in-memory parsed feeds — always fast."""

    def _parse(self, xml: str) -> feedparser.FeedParserDict:
        return feedparser.parse(xml)

    def test_match_by_episode_number(self, sample_rss_xml):
        feed = self._parse(sample_rss_xml)
        result = match_episode(feed, episode_number=1)
        assert isinstance(result, RSSEpisodeResult)
        assert result.episode_number == 1
        assert result.audio_url == "https://example.com/ep1.mp3"

    def test_match_by_episode_and_season(self, sample_rss_xml):
        feed = self._parse(sample_rss_xml)
        result = match_episode(feed, episode_number=2, season=1)
        assert result.episode_number == 2
        assert result.title == "Episode 2 - Follow Up"

    def test_match_wrong_season_raises(self, sample_rss_xml):
        feed = self._parse(sample_rss_xml)
        with pytest.raises(RSSError, match="No episode found"):
            match_episode(feed, episode_number=1, season=99)

    def test_match_out_of_range_raises(self, sample_rss_xml):
        feed = self._parse(sample_rss_xml)
        with pytest.raises(RSSError):
            match_episode(feed, episode_number=999)

    def test_positional_fallback_when_no_itunes_tags(self, sample_rss_xml_no_itunes):
        """If itunes:episode is absent, fall back to 1-based positional index."""
        feed = self._parse(sample_rss_xml_no_itunes)
        result = match_episode(feed, episode_number=1)
        assert result.audio_url == "https://example.com/bare1.mp3"

    def test_missing_audio_enclosure_raises(self, sample_rss_xml_no_enclosure):
        feed = self._parse(sample_rss_xml_no_enclosure)
        with pytest.raises(RSSError, match="No audio enclosure"):
            match_episode(feed, episode_number=1)

    def test_result_fields_populated(self, sample_rss_xml):
        feed = self._parse(sample_rss_xml)
        result = match_episode(feed, episode_number=1)
        assert result.title == "Episode 1 - Pilot"
        assert result.season == 1
        assert result.published_date != ""
        assert result.cover_art_url == "https://example.com/cover.jpg"

    def test_result_optional_fields_default_to_none(self, sample_rss_xml):
        """Episode 2 has no cover art — cover_art_url should be None."""
        feed = self._parse(sample_rss_xml)
        result = match_episode(feed, episode_number=2)
        assert result.cover_art_url is None
        assert result.spotify_link is None


class TestFetchFeed:
    """fetch_feed makes network calls — all paths mocked for unit tests."""

    def test_successful_fetch_returns_parsed_feed(self, sample_rss_xml):
        mock_response = MagicMock()
        mock_response.text = sample_rss_xml
        mock_response.raise_for_status = MagicMock()

        with patch("services.rss.httpx.get", return_value=mock_response):
            feed = fetch_feed("https://example.com/feed.rss")

        assert len(feed.entries) == 2

    def test_timeout_raises_transient_error(self):
        import httpx
        with patch("services.rss.httpx.get", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(TransientError, match="timed out"):
                fetch_feed("https://example.com/feed.rss")

    def test_5xx_status_raises_transient_error(self):
        import httpx
        mock_response = MagicMock()
        mock_response.status_code = 503
        error = httpx.HTTPStatusError("503", request=MagicMock(), response=mock_response)
        with patch("services.rss.httpx.get", side_effect=error):
            with pytest.raises(TransientError):
                fetch_feed("https://example.com/feed.rss")

    def test_4xx_status_raises_rss_error(self):
        import httpx
        mock_response = MagicMock()
        mock_response.status_code = 404
        error = httpx.HTTPStatusError("404", request=MagicMock(), response=mock_response)
        with patch("services.rss.httpx.get", side_effect=error):
            with pytest.raises(RSSError, match="404"):
                fetch_feed("https://example.com/feed.rss")

    def test_network_error_raises_transient_error(self):
        import httpx
        with patch("services.rss.httpx.get", side_effect=httpx.RequestError("network")):
            with pytest.raises(TransientError, match="network error"):
                fetch_feed("https://example.com/feed.rss")


class TestDownloadAudio:
    """download_audio uses streaming HTTP — fully mocked."""

    def test_successful_download_writes_file(self, tmp_path):
        dest = tmp_path / "episode.mp3"
        mock_stream_ctx = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_bytes.return_value = [b"fake", b"audio", b"data"]
        mock_stream_ctx.__enter__ = MagicMock(return_value=mock_response)
        mock_stream_ctx.__exit__ = MagicMock(return_value=False)

        with patch("services.rss.httpx.stream", return_value=mock_stream_ctx):
            download_audio("https://example.com/ep.mp3", dest)

        assert dest.exists()
        assert dest.read_bytes() == b"fakeaudiodata"

    def test_timeout_raises_transient_error(self, tmp_path):
        import httpx
        dest = tmp_path / "episode.mp3"
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(side_effect=httpx.TimeoutException("timeout"))
        mock_ctx.__exit__ = MagicMock(return_value=False)
        with patch("services.rss.httpx.stream", return_value=mock_ctx):
            with pytest.raises(TransientError, match="timed out"):
                download_audio("https://example.com/ep.mp3", dest)


# ══════════════════════════════════════════════════════════════════════════════
# Integration Tests — require real network access
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
def test_fetch_real_feed():
    """Fetch a real podcast RSS feed and verify it has entries."""
    feed = fetch_feed("https://feeds.simplecast.com/54nAGcIl")  # Acquired podcast
    assert len(feed.entries) > 0
    assert feed.feed.title


@pytest.mark.integration
def test_fetch_and_match_real_episode():
    """Fetch a real feed and match episode 1."""
    feed = fetch_feed("https://feeds.simplecast.com/54nAGcIl")
    result = match_episode(feed, episode_number=1)
    assert result.audio_url.startswith("http")
    assert result.title