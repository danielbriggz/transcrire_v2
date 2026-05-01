from typing import Optional
from dataclasses import dataclass

from google import genai

from utils.retry import with_aggressive_retry, TransientError, PermanentError, CaptionError
from app.config import config
from app.logging import get_logger

logger = get_logger(__name__)

SUPPORTED_PLATFORMS = ("twitter", "linkedin", "facebook")
MODEL_NAME = "gemini-2.5-flash"

_model = None


def _get_model():
    """Lazy model initialisation — validates API key on first use."""
    global _model
    if _model is None:
        if not config.gemini_api_key:
            raise PermanentError("GEMINI_API_KEY is not set. Add it to your .env file.")
        _client = genai.Client(api_key=config.gemini_api_key)
        _model = _client.models
        logger.info({"event": "gemini_model_initialised", "model": MODEL_NAME})
    return _model


@dataclass
class CaptionResult:
    platform: str
    caption: str
    with_spotify: Optional[str] = None   # Caption with Spotify CTA appended


@with_aggressive_retry
def generate_caption(
    transcript_text: str,
    platform: str,
    episode_title: str,
    spotify_link: Optional[str] = None,
) -> CaptionResult:
    """
    Generate a platform-specific caption from episode transcript text.

    Args:
        transcript_text: Full or summarised transcript to base the caption on.
                         Truncated to 3000 chars in the prompt.
        platform:        One of: "twitter", "linkedin", "facebook".
        episode_title:   Used in the prompt for context.
        spotify_link:    If provided, appended to the caption as a CTA.

    Raises:
        TransientError:  Rate limit or server error — retries with backoff.
        PermanentError:  Bad API key — will not retry.
        CaptionError:    Empty or unparseable response.
    """
    if platform not in SUPPORTED_PLATFORMS:
        raise CaptionError(
            f"Unsupported platform: '{platform}'. Must be one of: {SUPPORTED_PLATFORMS}"
        )

    model = _get_model()
    prompt = _build_prompt(transcript_text, platform, episode_title)

    logger.info({"event": "gemini_caption_start", "platform": platform})

    try:
        response = model.generate_content(prompt)
    except Exception as e:
        error_str = str(e).lower()
        if "quota" in error_str or "rate" in error_str or "429" in error_str:
            raise TransientError(f"Gemini rate limit: {e}") from e
        if "api key" in error_str or "auth" in error_str:
            raise PermanentError(f"Gemini auth error: {e}") from e
        raise CaptionError(f"Gemini request failed: {e}") from e

    caption = _parse_response(response)
    result = CaptionResult(platform=platform, caption=caption)

    if spotify_link:
        result.with_spotify = f"{caption}\n\n🎧 Listen: {spotify_link}"

    logger.info({"event": "gemini_caption_ok", "platform": platform, "chars": len(caption)})
    return result


def generate_all_captions(
    transcript_text: str,
    episode_title: str,
    spotify_link: Optional[str] = None,
) -> dict[str, CaptionResult]:
    """Generate captions for all three platforms. Returns dict keyed by platform name."""
    return {
        platform: generate_caption(
            transcript_text=transcript_text,
            platform=platform,
            episode_title=episode_title,
            spotify_link=spotify_link,
        )
        for platform in SUPPORTED_PLATFORMS
    }


def _build_prompt(transcript: str, platform: str, title: str) -> str:
    platform_rules = {
        "twitter": (
            "Write a single tweet (max 280 characters). "
            "Be punchy and direct. Use 1–2 relevant hashtags. "
            "No emojis unless they add meaning."
        ),
        "linkedin": (
            "Write a professional LinkedIn post (150–300 words). "
            "Start with a hook. Use short paragraphs. "
            "End with a question to drive engagement. "
            "Max 3 relevant hashtags — no spam."
        ),
        "facebook": (
            "Write a warm, conversational Facebook post (100–200 words). "
            "Be approachable and community-oriented. "
            "Include a soft call-to-action."
        ),
    }
    return (
        f"You are a social media copywriter for a podcast.\n\n"
        f"Episode title: {title}\n\n"
        f"Transcript excerpt:\n{transcript[:3000]}\n\n"
        f"Task: {platform_rules[platform]}\n\n"
        f"Return ONLY the caption text. No explanations, no labels, no markdown."
    )


def _parse_response(response) -> str:
    try:
        caption = response.text.strip()
    except (AttributeError, ValueError) as e:
        raise CaptionError(f"Could not extract text from Gemini response: {e}") from e
    if not caption:
        raise CaptionError("Gemini returned an empty caption.")
    return caption