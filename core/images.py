from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from PIL import Image, ImageFilter, ImageDraw, ImageFont

from app.logging import get_logger

logger = get_logger(__name__)

CARD_SIZE = (1080, 1080)
BLUR_RADIUS = 20
OVERLAY_OPACITY = 160        # 0–255. Higher = darker overlay.
FONT_DIR = Path("assets/fonts")
FONT_FILENAME = "AtkinsonHyperlegibleMono-{weight}.ttf"
MAX_QUOTE_CHARS = 280
TEXT_MARGIN = 80
LINE_SPACING = 1.4


@dataclass
class QuoteCardConfig:
    quote_text: str
    cover_art_path: Path
    output_path: Path
    episode_title: Optional[str] = None
    font_size: int = 52


@dataclass
class QuoteCardResult:
    output_path: Path
    font_weight_used: str
    brightness_score: float
    text_color: str          # "white" or "black"


def render_quote_card(config: QuoteCardConfig) -> QuoteCardResult:
    """
    Compose a 1080×1080 quote card and save it to config.output_path.

    Steps:
    1. Load and resize cover art to 1080×1080
    2. Apply Gaussian blur
    3. Apply semi-transparent dark overlay
    4. Detect background brightness → choose text colour
    5. Select font weight based on brightness
    6. Word-wrap and render quote text centred on card
    7. Render episode title at bottom-left (optional)
    8. Save as JPEG
    """
    logger.info({"event": "image_render_start", "output": str(config.output_path)})

    cover = Image.open(config.cover_art_path).convert("RGB")
    cover = cover.resize(CARD_SIZE, Image.LANCZOS)
    blurred = cover.filter(ImageFilter.GaussianBlur(radius=BLUR_RADIUS))

    overlay = Image.new("RGBA", CARD_SIZE, (0, 0, 0, OVERLAY_OPACITY))
    card = Image.alpha_composite(blurred.convert("RGBA"), overlay)

    brightness = _measure_brightness(blurred)
    text_color = "white" if brightness < 128 else "black"
    weight = _select_font_weight(brightness)

    font_path = FONT_DIR / FONT_FILENAME.format(weight=weight)
    font = _load_font(font_path, config.font_size)

    draw = ImageDraw.Draw(card)
    quote = config.quote_text[:MAX_QUOTE_CHARS]
    wrapped = _wrap_text(quote, font, draw, CARD_SIZE[0] - TEXT_MARGIN * 2)
    _draw_centred_text(draw, wrapped, font, text_color, config.font_size)

    if config.episode_title:
        title_font = _load_font(font_path, 28)
        draw.text(
            (TEXT_MARGIN, CARD_SIZE[1] - TEXT_MARGIN),
            config.episode_title,
            font=title_font,
            fill=text_color,
            anchor="lb",
        )

    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    card.convert("RGB").save(str(config.output_path), format="JPEG", quality=95)

    logger.info({
        "event": "image_render_ok",
        "font_weight": weight,
        "brightness": round(brightness, 2),
        "text_color": text_color,
    })
    return QuoteCardResult(
        output_path=config.output_path,
        font_weight_used=weight,
        brightness_score=brightness,
        text_color=text_color,
    )


def _measure_brightness(image: Image.Image) -> float:
    """Perceptual brightness using ITU-R 601 luma. Returns 0–255."""
    pixels = list(image.convert("L").getdata())
    return sum(pixels) / len(pixels)


def _select_font_weight(brightness: float) -> str:
    if brightness < 80:
        return "ExtraBold"
    elif brightness < 160:
        return "Bold"
    return "Regular"


def _load_font(font_path: Path, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(font_path), size)
    except (IOError, OSError):
        logger.warning({"event": "font_fallback", "path": str(font_path)})
        return ImageFont.load_default()


def _wrap_text(text: str, font, draw: ImageDraw.ImageDraw, max_width: int) -> list[str]:
    words = text.split()
    lines, current = [], []
    for word in words:
        test = " ".join(current + [word])
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines


def _draw_centred_text(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font,
    color: str,
    font_size: int,
) -> None:
    line_height = int(font_size * LINE_SPACING)
    y = (CARD_SIZE[1] - line_height * len(lines)) // 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        x = (CARD_SIZE[0] - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), line, font=font, fill=color)
        y += line_height