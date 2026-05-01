import pytest
from pathlib import Path
from PIL import Image
from core.images import (
    render_quote_card,
    QuoteCardConfig,
    QuoteCardResult,
    _measure_brightness,
    _select_font_weight,
    _wrap_text,
    _load_font,
)


@pytest.fixture
def cover_art(tmp_path):
    """Create a simple 500x500 solid colour JPEG to use as cover art."""
    img = Image.new("RGB", (500, 500), color=(30, 30, 30))
    path = tmp_path / "cover.jpg"
    img.save(str(path), format="JPEG")
    return path


@pytest.fixture
def bright_cover_art(tmp_path):
    """A very bright (near-white) cover art image."""
    img = Image.new("RGB", (500, 500), color=(240, 240, 240))
    path = tmp_path / "bright_cover.jpg"
    img.save(str(path), format="JPEG")
    return path


@pytest.fixture
def dark_cover_art(tmp_path):
    """A very dark (near-black) cover art image."""
    img = Image.new("RGB", (500, 500), color=(10, 10, 10))
    path = tmp_path / "dark_cover.jpg"
    img.save(str(path), format="JPEG")
    return path


# ── render_quote_card ─────────────────────────────────────────────────────────

def test_render_produces_jpeg_at_output_path(cover_art, tmp_path):
    output = tmp_path / "card.jpg"
    config = QuoteCardConfig(
        quote_text="This is a test quote.",
        cover_art_path=cover_art,
        output_path=output,
    )
    result = render_quote_card(config)
    assert output.exists()
    assert isinstance(result, QuoteCardResult)


def test_render_output_is_1080x1080(cover_art, tmp_path):
    output = tmp_path / "card.jpg"
    config = QuoteCardConfig(
        quote_text="Testing dimensions.",
        cover_art_path=cover_art,
        output_path=output,
    )
    render_quote_card(config)
    img = Image.open(output)
    assert img.size == (1080, 1080)


def test_render_result_has_correct_output_path(cover_art, tmp_path):
    output = tmp_path / "card.jpg"
    config = QuoteCardConfig(
        quote_text="Path check.",
        cover_art_path=cover_art,
        output_path=output,
    )
    result = render_quote_card(config)
    assert result.output_path == output


def test_render_dark_background_uses_white_text(dark_cover_art, tmp_path):
    output = tmp_path / "card.jpg"
    config = QuoteCardConfig(
        quote_text="Dark background quote.",
        cover_art_path=dark_cover_art,
        output_path=output,
    )
    result = render_quote_card(config)
    assert result.text_color == "white"


def test_render_bright_background_uses_black_text(bright_cover_art, tmp_path):
    output = tmp_path / "card.jpg"
    config = QuoteCardConfig(
        quote_text="Bright background quote.",
        cover_art_path=bright_cover_art,
        output_path=output,
    )
    result = render_quote_card(config)
    assert result.text_color == "black"


def test_render_creates_parent_directories(cover_art, tmp_path):
    output = tmp_path / "nested" / "deep" / "card.jpg"
    config = QuoteCardConfig(
        quote_text="Nested path test.",
        cover_art_path=cover_art,
        output_path=output,
    )
    render_quote_card(config)
    assert output.exists()


def test_render_with_episode_title(cover_art, tmp_path):
    output = tmp_path / "card.jpg"
    config = QuoteCardConfig(
        quote_text="Quote with title.",
        cover_art_path=cover_art,
        output_path=output,
        episode_title="Episode 1 - Pilot",
    )
    # Should not raise — title rendering is optional
    result = render_quote_card(config)
    assert result is not None


def test_render_truncates_long_quote(cover_art, tmp_path):
    output = tmp_path / "card.jpg"
    config = QuoteCardConfig(
        quote_text="x" * 500,  # over the 280 char limit
        cover_art_path=cover_art,
        output_path=output,
    )
    # Should not raise — long quotes are silently truncated
    render_quote_card(config)
    assert output.exists()


# ── _measure_brightness ───────────────────────────────────────────────────────

def test_brightness_black_image_is_zero():
    img = Image.new("RGB", (100, 100), color=(0, 0, 0))
    assert _measure_brightness(img) == pytest.approx(0.0)


def test_brightness_white_image_is_255():
    img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    assert _measure_brightness(img) == pytest.approx(255.0)


def test_brightness_mid_grey_is_near_128():
    img = Image.new("RGB", (100, 100), color=(128, 128, 128))
    assert _measure_brightness(img) == pytest.approx(128.0, abs=1.0)


def test_brightness_returns_float():
    img = Image.new("RGB", (10, 10), color=(100, 100, 100))
    assert isinstance(_measure_brightness(img), float)


# ── _select_font_weight ───────────────────────────────────────────────────────

def test_font_weight_very_dark_is_extrabold():
    assert _select_font_weight(50.0) == "ExtraBold"


def test_font_weight_mid_dark_is_bold():
    assert _select_font_weight(100.0) == "Bold"


def test_font_weight_bright_is_regular():
    assert _select_font_weight(200.0) == "Regular"


def test_font_weight_boundary_80_is_bold():
    assert _select_font_weight(80.0) == "Bold"


def test_font_weight_boundary_160_is_regular():
    assert _select_font_weight(160.0) == "Regular"