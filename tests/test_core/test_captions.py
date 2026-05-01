import pytest
from unittest.mock import patch, MagicMock
from core.captions import (
    generate_caption_bundle,
    regenerate_single_caption,
    CaptionBundle,
    PLATFORMS,
)
from services.gemini import CaptionResult


SAMPLE_TRANSCRIPT = "Today we discussed building better habits and staying consistent over time."
SAMPLE_TITLE = "Episode 5 - Habit Building"


def _make_mock_caption(platform: str) -> CaptionResult:
    return CaptionResult(platform=platform, caption=f"Generated caption for {platform}.")


def _make_all_mock_captions(spotify_link=None):
    """Patch generate_caption to return a mock result for any platform."""
    def fake_generate(transcript_text, platform, episode_title, spotify_link=None):
        result = _make_mock_caption(platform)
        if spotify_link:
            result.with_spotify = f"{result.caption}\n\n🎧 Listen: {spotify_link}"
        return result
    return fake_generate


# ── generate_caption_bundle ───────────────────────────────────────────────────

def test_bundle_contains_all_platforms():
    with patch("core.captions.generate_caption", side_effect=_make_all_mock_captions()):
        bundle = generate_caption_bundle("ep-1", SAMPLE_TITLE, SAMPLE_TRANSCRIPT)

    assert bundle.twitter is not None
    assert bundle.linkedin is not None
    assert bundle.facebook is not None


def test_bundle_has_correct_episode_id():
    with patch("core.captions.generate_caption", side_effect=_make_all_mock_captions()):
        bundle = generate_caption_bundle("ep-42", SAMPLE_TITLE, SAMPLE_TRANSCRIPT)

    assert bundle.episode_id == "ep-42"


def test_bundle_has_correct_title():
    with patch("core.captions.generate_caption", side_effect=_make_all_mock_captions()):
        bundle = generate_caption_bundle("ep-1", SAMPLE_TITLE, SAMPLE_TRANSCRIPT)

    assert bundle.episode_title == SAMPLE_TITLE


def test_bundle_no_errors_on_success():
    with patch("core.captions.generate_caption", side_effect=_make_all_mock_captions()):
        bundle = generate_caption_bundle("ep-1", SAMPLE_TITLE, SAMPLE_TRANSCRIPT)

    assert bundle.errors == {}


def test_bundle_all_generated_true_when_complete():
    with patch("core.captions.generate_caption", side_effect=_make_all_mock_captions()):
        bundle = generate_caption_bundle("ep-1", SAMPLE_TITLE, SAMPLE_TRANSCRIPT)

    assert bundle.all_generated() is True


def test_bundle_captures_error_without_raising():
    """A failure on one platform should not block the others."""
    def fail_on_linkedin(transcript_text, platform, episode_title, spotify_link=None):
        if platform == "linkedin":
            raise Exception("Gemini rate limit")
        return _make_mock_caption(platform)

    with patch("core.captions.generate_caption", side_effect=fail_on_linkedin):
        bundle = generate_caption_bundle("ep-1", SAMPLE_TITLE, SAMPLE_TRANSCRIPT)

    assert bundle.linkedin is None
    assert "linkedin" in bundle.errors
    assert bundle.twitter is not None
    assert bundle.facebook is not None


def test_bundle_all_generated_false_when_one_failed():
    def fail_on_twitter(transcript_text, platform, episode_title, spotify_link=None):
        if platform == "twitter":
            raise Exception("failed")
        return _make_mock_caption(platform)

    with patch("core.captions.generate_caption", side_effect=fail_on_twitter):
        bundle = generate_caption_bundle("ep-1", SAMPLE_TITLE, SAMPLE_TRANSCRIPT)

    assert bundle.all_generated() is False


def test_bundle_to_dict_structure():
    with patch("core.captions.generate_caption", side_effect=_make_all_mock_captions()):
        bundle = generate_caption_bundle("ep-1", SAMPLE_TITLE, SAMPLE_TRANSCRIPT)

    d = bundle.to_dict()
    assert "twitter" in d
    assert "linkedin" in d
    assert "facebook" in d
    assert "errors" in d


def test_bundle_spotify_link_stored():
    with patch("core.captions.generate_caption", side_effect=_make_all_mock_captions(
        spotify_link="https://open.spotify.com/episode/abc"
    )):
        bundle = generate_caption_bundle(
            "ep-1", SAMPLE_TITLE, SAMPLE_TRANSCRIPT,
            spotify_link="https://open.spotify.com/episode/abc"
        )

    assert bundle.spotify_link == "https://open.spotify.com/episode/abc"


# ── regenerate_single_caption ─────────────────────────────────────────────────

def test_regenerate_updates_single_platform():
    bundle = CaptionBundle(
        episode_id="ep-1",
        episode_title=SAMPLE_TITLE,
        twitter=_make_mock_caption("twitter"),
        linkedin=_make_mock_caption("linkedin"),
        facebook=_make_mock_caption("facebook"),
    )
    new_caption = CaptionResult(platform="twitter", caption="Refreshed twitter caption.")

    with patch("core.captions.generate_caption", return_value=new_caption):
        result = regenerate_single_caption(bundle, "twitter", SAMPLE_TRANSCRIPT)

    assert result.twitter.caption == "Refreshed twitter caption."
    assert result.linkedin.caption == "Generated caption for linkedin."  # unchanged


def test_regenerate_clears_error_on_success():
    bundle = CaptionBundle(
        episode_id="ep-1",
        episode_title=SAMPLE_TITLE,
        errors={"twitter": "Previous error"},
    )
    with patch("core.captions.generate_caption", return_value=_make_mock_caption("twitter")):
        result = regenerate_single_caption(bundle, "twitter", SAMPLE_TRANSCRIPT)

    assert "twitter" not in result.errors


def test_regenerate_stores_error_on_failure():
    bundle = CaptionBundle(episode_id="ep-1", episode_title=SAMPLE_TITLE)

    with patch("core.captions.generate_caption", side_effect=Exception("API down")):
        result = regenerate_single_caption(bundle, "linkedin", SAMPLE_TRANSCRIPT)

    assert "linkedin" in result.errors


def test_regenerate_raises_on_invalid_platform():
    bundle = CaptionBundle(episode_id="ep-1", episode_title=SAMPLE_TITLE)
    with pytest.raises(ValueError, match="Unknown platform"):
        regenerate_single_caption(bundle, "tiktok", SAMPLE_TRANSCRIPT)