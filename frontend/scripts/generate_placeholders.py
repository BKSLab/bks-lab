"""Generate placeholder assets for the frontend public/ directory.

Creates clearly-marked placeholder files with the exact names and sizes from
the design spec (sections 5-7, 15). These are NOT logo drafts — final brand
assets replace them one-to-one, keeping the file names.

Requires Pillow:  python -m pip install pillow
Usage:            python frontend/scripts/generate_placeholders.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PUBLIC = Path(__file__).resolve().parent.parent / "public"

BG_DEEP = (7, 24, 39)  # --color-bg
SURFACE = (16, 38, 54)  # --color-surface
ACCENT = (24, 184, 242)  # --color-accent
MUTED = (154, 170, 182)  # --color-text-muted

BRAND_SVGS = {
    "logo-full-dark.svg": ("#071827", "full (dark artwork)"),
    "logo-full-light.svg": ("#E8EEF2", "full (light artwork)"),
    "logo-horizontal-dark.svg": ("#071827", "horizontal (dark artwork)"),
    "logo-horizontal-light.svg": ("#E8EEF2", "horizontal (light artwork)"),
    "logo-mark-cyan.svg": ("#18B8F2", "mark (cyan)"),
    "logo-mark-white.svg": ("#FFFFFF", "mark (white)"),
    "logo-mark-dark.svg": ("#071827", "mark (dark)"),
}

IMAGES_WEBP = {
    "images/hero/bks-lab-wall.webp": (1920, 1080),
    "images/blog/blog-hero.webp": (1600, 900),
    "images/projects/work-for-everyone.webp": (1200, 675),
    "images/projects/service-desk.webp": (1200, 675),
    "images/projects/legal-rag.webp": (1200, 675),
    "images/articles/1c-async.webp": (1200, 675),
    "images/articles/ai-developer.webp": (1200, 675),
    "images/articles/business-processes.webp": (1200, 675),
    "images/articles/fastapi-microservices.webp": (1200, 675),
    "images/articles/work-life-balance.webp": (1200, 675),
    "images/articles/accessibility.webp": (1200, 675),
}

OG_IMAGES = {
    "og/bks-lab-default.jpg": (1200, 630),
    "og/blog.jpg": (1200, 630),
}

ICON_PNGS = {
    "favicon-16x16.png": 16,
    "favicon-32x32.png": 32,
    "apple-touch-icon.png": 180,
    "android-chrome-192x192.png": 192,
    "android-chrome-512x512.png": 512,
}

MANIFEST = """{
  "name": "BKS Lab",
  "short_name": "BKS Lab",
  "icons": [
    { "src": "/android-chrome-192x192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/android-chrome-512x512.png", "sizes": "512x512", "type": "image/png" }
  ],
  "theme_color": "#071827",
  "background_color": "#071827",
  "display": "standalone"
}
"""

FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
  <!-- Placeholder favicon (spec section 6): final simplified mark pending -->
  <rect x="1.5" y="1.5" width="29" height="29" rx="6" fill="#071827" stroke="#18B8F2" stroke-width="2" stroke-dasharray="4 3"/>
</svg>
"""


def brand_svg(color: str, label: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
  <!-- Placeholder brand asset (spec section 5): final "magnifier + </>" artwork pending -->
  <rect x="16" y="16" width="480" height="480" rx="48" fill="none" stroke="{color}" stroke-width="8" stroke-dasharray="24 16"/>
  <text x="256" y="246" text-anchor="middle" font-family="monospace" font-size="34" fill="{color}">BKS Lab</text>
  <text x="256" y="296" text-anchor="middle" font-family="monospace" font-size="22" fill="{color}">placeholder: {label}</text>
</svg>
"""


def raster_placeholder(path: Path, width: int, height: int, fmt: str) -> None:
    image = Image.new("RGB", (width, height), SURFACE)
    draw = ImageDraw.Draw(image)
    margin = max(8, min(width, height) // 40)
    dash = max(12, min(width, height) // 24)
    # Dashed accent border.
    x = margin
    while x < width - margin:
        draw.line([(x, margin), (min(x + dash, width - margin), margin)], fill=ACCENT, width=4)
        draw.line([(x, height - margin), (min(x + dash, width - margin), height - margin)], fill=ACCENT, width=4)
        x += dash * 2
    y = margin
    while y < height - margin:
        draw.line([(margin, y), (margin, min(y + dash, height - margin))], fill=ACCENT, width=4)
        draw.line([(width - margin, y), (width - margin, min(y + dash, height - margin))], fill=ACCENT, width=4)
        y += dash * 2
    label = path.name
    size = max(16, min(width, height) // 14)
    font = ImageFont.load_default(size=size)
    small = ImageFont.load_default(size=max(12, size // 2))
    for i, (text, f) in enumerate(((label, font), ("placeholder", small))):
        box = draw.textbbox((0, 0), text, font=f)
        tw, th = box[2] - box[0], box[3] - box[1]
        draw.text(
            ((width - tw) / 2, (height - th) / 2 + (i * 2 - 1) * size * 0.9),
            text,
            font=f,
            fill=MUTED,
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "WEBP":
        image.save(path, "WEBP", quality=80)
    else:
        image.save(path, "JPEG", quality=85)


def icon_placeholder(size: int) -> Image.Image:
    image = Image.new("RGB", (size, size), BG_DEEP)
    draw = ImageDraw.Draw(image)
    width = max(1, size // 12)
    inset = max(1, size // 16)
    draw.rectangle(
        [inset, inset, size - inset - 1, size - inset - 1],
        outline=ACCENT,
        width=width,
    )
    return image


def main() -> None:
    brand_dir = PUBLIC / "brand"
    brand_dir.mkdir(parents=True, exist_ok=True)
    for name, (color, label) in BRAND_SVGS.items():
        (brand_dir / name).write_text(brand_svg(color, label), encoding="utf-8")

    (PUBLIC / "favicon.svg").write_text(FAVICON_SVG, encoding="utf-8")
    (PUBLIC / "site.webmanifest").write_text(MANIFEST, encoding="utf-8")

    for name, size in ICON_PNGS.items():
        icon_placeholder(size).save(PUBLIC / name, "PNG")

    icon_placeholder(32).save(
        PUBLIC / "favicon.ico", "ICO", sizes=[(16, 16), (32, 32)]
    )

    for rel, (width, height) in IMAGES_WEBP.items():
        raster_placeholder(PUBLIC / rel, width, height, "WEBP")
    for rel, (width, height) in OG_IMAGES.items():
        raster_placeholder(PUBLIC / rel, width, height, "JPEG")

    print("Placeholder assets generated in", PUBLIC)


if __name__ == "__main__":
    main()
