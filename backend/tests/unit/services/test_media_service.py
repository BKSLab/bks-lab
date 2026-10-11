"""Unit tests for the image upload pipeline (pure Pillow processing)."""

from io import BytesIO

import pytest
from PIL import Image

from src.exceptions.admin import MediaFileTooLargeError, MediaValidationError
from src.services.media import _slugify_name, process_image


def make_image(fmt: str, size: tuple[int, int] = (800, 600), mode: str = "RGB") -> bytes:
    buffer = BytesIO()
    Image.new(mode, size, "red").save(buffer, fmt)
    return buffer.getvalue()


def test_process_image_converts_to_webp() -> None:
    data, width, height = process_image(
        make_image("PNG"), max_bytes=5 * 1024 * 1024, max_width=1920
    )

    with Image.open(BytesIO(data)) as converted:
        assert converted.format == "WEBP"
    assert (width, height) == (800, 600)


def test_process_image_downscales_wide_images_keeping_ratio() -> None:
    data, width, height = process_image(
        make_image("JPEG", size=(3000, 2000)), max_bytes=5 * 1024 * 1024, max_width=1920
    )

    assert width == 1920
    assert height == 1280
    with Image.open(BytesIO(data)) as converted:
        assert converted.size == (1920, 1280)


def test_process_image_accepts_webp_input() -> None:
    data, _, _ = process_image(
        make_image("WEBP"), max_bytes=5 * 1024 * 1024, max_width=1920
    )
    with Image.open(BytesIO(data)) as converted:
        assert converted.format == "WEBP"


def test_process_image_rejects_oversize_source() -> None:
    with pytest.raises(MediaFileTooLargeError):
        process_image(b"x" * 2048, max_bytes=1024, max_width=1920)


def test_process_image_rejects_non_image_payload() -> None:
    with pytest.raises(MediaValidationError):
        process_image(b"definitely not an image", max_bytes=1024, max_width=1920)


def test_process_image_rejects_unsupported_format() -> None:
    with pytest.raises(MediaValidationError):
        process_image(make_image("GIF"), max_bytes=5 * 1024 * 1024, max_width=1920)


def test_slugify_name() -> None:
    assert _slugify_name("My Cover Photo.PNG") == "my-cover-photo"
    assert _slugify_name("обложка.png") == "image"
    assert _slugify_name("a---b__c.webp") == "a-b-c"
