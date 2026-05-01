import pytest
from unittest.mock import patch, MagicMock
from services.gemini import (
    generate_caption, generate_all_captions,
    CaptionResult, SUPPORTED_PLATFORMS
)
from utils.retry import TransientError, PermanentError, CaptionError


SAMPLE_TRANSCRIPT = "Today we talked about building better habits and staying consistent."
SAMPLE_TITLE = "Episode 1 - Building Habits"


@pytest.fixture(autouse=True)
def reset_gemini_model():
    """Reset the lazy Gemini model before each test."""
    import services.gemini as gemini_module
    gemini_module._model = None
    yield
    gemini_module._model = None


def _make_mock_model(response_text="Generated caption text."):
    mock_model = MagicMock()
    mock_model.generate_content.return_value = MagicMock(text=response_text)
    return mock_model


def test_generate_caption_returns_result(mock_gemini_response):
    with patch("services.gemini._get_model", return_value=_make_mock_model()):
        result = generate_caption(
            transcript_text=SAMPLE_TRANSCRIPT,
            platform="twitter",
            episode_title=SAMPLE_TITLE,
        )
    assert isinstance(result, CaptionResult)
    assert result.platform == "twitter"
    assert result.caption == "Generated caption text."
    assert result.with_spotify is None


def test_generate_caption_appends_spotify_link():
    with patch("services.gemini._get_model", return_value=_make_mock_model()):
        result = generate_caption(
            transcript_text=SAMPLE_TRANSCRIPT,
            platform="twitter",
            episode_title=SAMPLE_TITLE,
            spotify_link="https://open.spotify.com/episode/abc123",
        )
    assert result.with_spotify is not None
    assert "https://open.spotify.com/episode/abc123" in result.with_spotify
    assert "🎧" in result.with_spotify


def test_generate_caption_raises_on_unsupported_platform():
    with pytest.raises(CaptionError, match="Unsupported platform"):
        generate_caption(
            transcript_text=SAMPLE_TRANSCRIPT,
            platform="tiktok",
            episode_title=SAMPLE_TITLE,
        )


def test_generate_caption_raises_transient_on_rate_limit():
    mock_model = MagicMock()
    mock_model.generate_content.side_effect = Exception("429 quota exceeded")

    with patch("services.gemini._get_model", return_value=mock_model):
        with pytest.raises(TransientError):
            generate_caption.__wrapped__(
                transcript_text=SAMPLE_TRANSCRIPT,
                platform="twitter",
                episode_title=SAMPLE_TITLE,
            )


def test_generate_caption_raises_permanent_on_auth_error():
    mock_model = MagicMock()
    mock_model.generate_content.side_effect = Exception("invalid api key")

    with patch("services.gemini._get_model", return_value=mock_model):
        with pytest.raises(PermanentError):
            generate_caption.__wrapped__(
                transcript_text=SAMPLE_TRANSCRIPT,
                platform="twitter",
                episode_title=SAMPLE_TITLE,
            )


def test_generate_caption_raises_on_empty_response():
    mock_model = MagicMock()
    mock_model.generate_content.return_value = MagicMock(text="   ")

    with patch("services.gemini._get_model", return_value=mock_model):
        with pytest.raises(CaptionError, match="empty"):
            generate_caption.__wrapped__(
                transcript_text=SAMPLE_TRANSCRIPT,
                platform="twitter",
                episode_title=SAMPLE_TITLE,
            )


def test_generate_all_captions_returns_all_platforms():
    with patch("services.gemini._get_model", return_value=_make_mock_model()):
        results = generate_all_captions(
            transcript_text=SAMPLE_TRANSCRIPT,
            episode_title=SAMPLE_TITLE,
        )
    assert set(results.keys()) == set(SUPPORTED_PLATFORMS)
    for platform, result in results.items():
        assert isinstance(result, CaptionResult)
        assert result.platform == platform


def test_get_model_raises_permanent_when_no_key():
    with patch("services.gemini.config") as mock_config:
        mock_config.gemini_api_key = ""
        import services.gemini as gemini_module
        gemini_module._model = None
        with pytest.raises(PermanentError, match="GEMINI_API_KEY"):
            gemini_module._get_model()