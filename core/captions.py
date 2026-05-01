from dataclasses import dataclass, field
from typing import Optional

from services.gemini import CaptionResult, generate_caption
from core.transcript import truncate_for_prompt
from app.logging import get_logger

logger = get_logger(__name__)

PLATFORMS = ("twitter", "linkedin", "facebook")


@dataclass
class CaptionBundle:
    """All platform captions for one episode, plus error tracking."""
    episode_id: str
    episode_title: str
    twitter: Optional[CaptionResult] = None
    linkedin: Optional[CaptionResult] = None
    facebook: Optional[CaptionResult] = None
    spotify_link: Optional[str] = None
    errors: dict[str, str] = field(default_factory=dict)

    def all_generated(self) -> bool:
        return all([self.twitter, self.linkedin, self.facebook])

    def to_dict(self) -> dict:
        return {
            "twitter": self.twitter.caption if self.twitter else None,
            "twitter_spotify": self.twitter.with_spotify if self.twitter else None,
            "linkedin": self.linkedin.caption if self.linkedin else None,
            "linkedin_spotify": self.linkedin.with_spotify if self.linkedin else None,
            "facebook": self.facebook.caption if self.facebook else None,
            "facebook_spotify": self.facebook.with_spotify if self.facebook else None,
            "errors": self.errors,
        }


def generate_caption_bundle(
    episode_id: str,
    episode_title: str,
    transcript_text: str,
    spotify_link: Optional[str] = None,
) -> CaptionBundle:
    """
    Generate captions for all platforms and return a CaptionBundle.

    Failures on individual platforms are caught and stored in bundle.errors
    rather than raising — a LinkedIn failure does not block Twitter output.
    """
    bundle = CaptionBundle(
        episode_id=episode_id,
        episode_title=episode_title,
        spotify_link=spotify_link,
    )
    prompt_text = truncate_for_prompt(transcript_text)

    for platform in PLATFORMS:
        try:
            result = generate_caption(
                transcript_text=prompt_text,
                platform=platform,
                episode_title=episode_title,
                spotify_link=spotify_link,
            )
            setattr(bundle, platform, result)
            logger.info({"event": "caption_generated", "platform": platform})
        except Exception as e:
            bundle.errors[platform] = str(e)
            logger.error({"event": "caption_failed", "platform": platform, "error": str(e)})

    return bundle


def regenerate_single_caption(
    bundle: CaptionBundle,
    platform: str,
    transcript_text: str,
) -> CaptionBundle:
    """
    Regenerate the caption for one platform without touching the others.
    Used for the CLI/GUI single-caption regeneration feature.
    """
    if platform not in PLATFORMS:
        raise ValueError(f"Unknown platform: '{platform}'. Must be one of {PLATFORMS}")

    try:
        result = generate_caption(
            transcript_text=truncate_for_prompt(transcript_text),
            platform=platform,
            episode_title=bundle.episode_title,
            spotify_link=bundle.spotify_link,
        )
        setattr(bundle, platform, result)
        bundle.errors.pop(platform, None)
        logger.info({"event": "caption_regenerated", "platform": platform})
    except Exception as e:
        bundle.errors[platform] = str(e)
        logger.error({"event": "caption_regeneration_failed", "platform": platform, "error": str(e)})

    return bundle