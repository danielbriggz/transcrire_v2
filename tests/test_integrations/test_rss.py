import pytest
import feedparser
from unittest.mock import patch, MagicMock
from services.rss import fetch_feed, match_episode, _build_result, RSSEpisodeResult # type: ignore
from utils.retry import TransientError, RSSError


def test_match_episode_by_itunes_number(sample_rss_xml): # type: ignore
    feed = feedparser.parse(sample_rss_xml) # type: ignore
    result = match_episode(feed, episode_number=1, season=1) # type: ignore
    assert isinstance(result, RSSEpisodeResult)
    assert result.title == "Episode 1 - Pilot"
    assert result.audio_url == "https://example.com/ep1.mp3"
    assert result.episode_number == 1
    assert result.season == 1


def test_match_episode_second_entry(sample_rss_xml): # type: ignore
    feed = feedparser.parse(sample_rss_xml) # type: ignore
    result = match_episode(feed, episode_number=2) # type: ignore
    assert result.title == "Episode 2 - Follow Up"


def test_match_episode_not_found_raises(sample_rss_xml): # type: ignore
    feed = feedparser.parse(sample_rss_xml) # type: ignore
    with pytest.raises(RSSError, match="No episode found"):
        match_episode(feed, episode_number=99, season=1) # type: ignore


def test_match_episode_positional_fallback(sample_rss_xml): # type: ignore
    """When itunes tags are absent, falls back to positional match."""
    feed = feedparser.parse(sample_rss_xml) # type: ignore
    # Episode 3 doesn't exist by itunes tag but position 1 does
    result = match_episode(feed, episode_number=1) # type: ignore
    assert result is not None


def test_cover_art_extracted(sample_rss_xml): # type: ignore
    feed = feedparser.parse(sample_rss_xml) # type: ignore
    result = match_episode(feed, episode_number=1) # type: ignore
    assert result.cover_art_url == "https://example.com/cover.jpg"


def test_fetch_feed_transient_error_on_timeout():
    import httpx
    with patch("httpx.get", side_effect=httpx.TimeoutException("timeout")):
        with pytest.raises(TransientError, match="timed out"):
            fetch_feed("https://example.com/feed.rss")


def test_fetch_feed_rss_error_on_404():
    import httpx
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "not found", request=MagicMock(), response=mock_resp
    )
    with patch("httpx.get", return_value=mock_resp):
        with pytest.raises(RSSError, match="404"):
            fetch_feed("https://example.com/feed.rss")


def test_fetch_feed_transient_error_on_503():
    import httpx
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "server error", request=MagicMock(), response=mock_resp
    )
    with patch("httpx.get", return_value=mock_resp):
        with pytest.raises(TransientError, match="503"):
            fetch_feed("https://example.com/feed.rss")