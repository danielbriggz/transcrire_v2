import httpx
import feedparser
from dataclasses import dataclass
from typing import Optional

from utils.retry import with_standard_retry, TransientError, RSSError
from app.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RSSEpisodeResult:
    """Structured result from a successful RSS episode match."""
    title: str
    audio_url: str
    published_date: str
    cover_art_url: Optional[str]
    spotify_link: Optional[str]
    season: Optional[int]
    episode_number: Optional[int]
    description: Optional[str]


@with_standard_retry
def fetch_feed(feed_url: str) -> feedparser.FeedParserDict:
    """
    Download and parse an RSS feed.
    Raises TransientError on network failure, RSSError on parse failure.
    """
    logger.info({"event": "rss_fetch_start", "url": feed_url})
    try:
        response = httpx.get(feed_url, timeout=30, follow_redirects=True)
        response.raise_for_status()
    except httpx.TimeoutException as e:
        raise TransientError(f"RSS fetch timed out: {feed_url}") from e
    except httpx.HTTPStatusError as e:
        if e.response.status_code >= 500:
            raise TransientError(f"RSS server error {e.response.status_code}") from e
        raise RSSError(f"RSS fetch failed with status {e.response.status_code}") from e
    except httpx.RequestError as e:
        raise TransientError(f"RSS network error: {e}") from e

    feed = feedparser.parse(response.text)

    if feed.bozo and not feed.entries:
        raise RSSError(f"Feed parse failed: {feed.bozo_exception}")

    logger.info({"event": "rss_fetch_ok", "entries": len(feed.entries)})
    return feed


def match_episode(
    feed: feedparser.FeedParserDict,
    episode_number: int,
    season: Optional[int] = None,
) -> RSSEpisodeResult:
    """
    Find an episode in a parsed feed by episode and optional season number.
    Raises RSSError if no match is found.

    Checks itunes:episode and itunes:season tags first.
    Falls back to positional matching (episode_number as 1-based index from newest).
    """
    logger.info({"event": "rss_match_start", "episode": episode_number, "season": season})

    for entry in feed.entries:
        ep_num = _get_itunes_int(entry, "itunes_episode")
        s_num = _get_itunes_int(entry, "itunes_season")

        ep_match = ep_num == episode_number
        season_match = (season is None) or (s_num == season)

        if ep_match and season_match:
            return _build_result(entry)

    # Fallback: positional match (newest first)
    if 1 <= episode_number <= len(feed.entries):
        logger.warning({"event": "rss_match_positional_fallback", "episode": episode_number})
        return _build_result(feed.entries[episode_number - 1])

    raise RSSError(
        f"No episode found for episode={episode_number}, season={season} "
        f"in feed with {len(feed.entries)} entries."
    )


def download_audio(audio_url: str, destination_path) -> None:
    """
    Stream-download an audio file to disk.
    Uses streaming to avoid loading large audio files into memory.
    """
    from pathlib import Path
    dest = Path(destination_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    logger.info({"event": "audio_download_start", "url": audio_url})
    try:
        with httpx.stream("GET", audio_url, timeout=120, follow_redirects=True) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=65536):
                    f.write(chunk)
    except httpx.TimeoutException as e:
        raise TransientError(f"Audio download timed out: {audio_url}") from e
    except httpx.HTTPStatusError as e:
        raise RSSError(f"Audio download failed: {e.response.status_code}") from e

    logger.info({"event": "audio_download_ok", "path": str(dest)})


def _get_itunes_int(entry, tag: str) -> Optional[int]:
    value = entry.get(tag)
    try:
        return int(value) if value is not None else None
    except (ValueError, TypeError):
        return None


def _build_result(entry) -> RSSEpisodeResult:
    audio_url = None
    for link in entry.get("enclosures", []):
        if "audio" in link.get("type", ""):
            audio_url = link.get("href")
            break

    if not audio_url:
        raise RSSError(f"No audio enclosure found for entry: {entry.get('title')}")

    cover_art = (
        entry.get("itunes_image", {}).get("href")
        or entry.get("image", {}).get("href")
    )

    return RSSEpisodeResult(
        title=entry.get("title", "Untitled"),
        audio_url=audio_url,
        published_date=entry.get("published", ""),
        cover_art_url=cover_art,
        spotify_link=None,
        season=_get_itunes_int(entry, "itunes_season"),
        episode_number=_get_itunes_int(entry, "itunes_episode"),
        description=entry.get("summary", ""),
    )