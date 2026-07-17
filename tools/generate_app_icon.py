from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
SIZE = 512


def create_icon() -> Image.Image:
    image = Image.new("RGBA", (SIZE, SIZE), (7, 11, 17, 255))
    pixels = image.load()
    for y in range(SIZE):
        for x in range(SIZE):
            distance = ((x - 360) ** 2 + (y - 130) ** 2) ** 0.5
            glow = max(0.0, 1.0 - distance / 390.0)
            pixels[x, y] = (
                int(7 + 8 * glow),
                int(11 + 23 * glow),
                int(17 + 27 * glow),
                255,
            )

    glow_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    glow_draw.rounded_rectangle((74, 74, 438, 438), radius=86, outline=(102, 227, 204, 115), width=18)
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(24))
    image.alpha_composite(glow_layer)

    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((48, 48, 464, 464), radius=104, fill=(10, 16, 24, 245), outline=(35, 57, 67, 255), width=8)

    diamond = [(256, 93), (419, 256), (256, 419), (93, 256)]
    inner = [(256, 124), (388, 256), (256, 388), (124, 256)]
    draw.polygon(diamond, fill=(102, 227, 204, 255))
    draw.polygon(inner, fill=(8, 14, 21, 255))

    light = (224, 252, 247, 255)
    accent = (102, 227, 204, 255)
    draw.rounded_rectangle((184, 167, 218, 345), radius=12, fill=light)
    draw.rounded_rectangle((205, 167, 329, 201), radius=12, fill=accent)
    draw.rounded_rectangle((205, 239, 302, 273), radius=12, fill=accent)
    draw.rounded_rectangle((205, 311, 329, 345), radius=12, fill=accent)
    return image


def main() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    image = create_icon()
    image.save(BUILD / "icon.png", optimize=True)
    image.save(BUILD / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    main()
