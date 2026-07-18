import argparse
from collections import deque
from pathlib import Path

from PIL import Image, ImageFilter


parser = argparse.ArgumentParser()
parser.add_argument("source", type=Path)
parser.add_argument(
    "--output",
    type=Path,
    default=Path(__file__).resolve().parents[1]
    / "SourceAssets"
    / "UI"
    / "speech_bubble_ivory.png",
)
args = parser.parse_args()
SOURCE = args.source
OUTPUT = args.output

image = Image.open(SOURCE).convert("RGB")
width, height = image.size
pixels = image.load()
binary = bytearray(width * height)

for y in range(70, 500):
    for x in range(180, 850):
        red, green, blue = pixels[x, y]
        if red - blue > 5 and red - green > 1:
            binary[y * width + x] = 1

seen = bytearray(width * height)
largest = []
for index, value in enumerate(binary):
    if not value or seen[index]:
        continue
    queue = deque([index])
    seen[index] = 1
    component = []
    while queue:
        current = queue.popleft()
        component.append(current)
        x = current % width
        y = current // width
        neighbors = (
            current - 1 if x else -1,
            current + 1 if x < width - 1 else -1,
            current - width if y else -1,
            current + width if y < height - 1 else -1,
        )
        for neighbor in neighbors:
            if neighbor >= 0 and binary[neighbor] and not seen[neighbor]:
                seen[neighbor] = 1
                queue.append(neighbor)
    if len(component) > len(largest):
        largest = component

mask = Image.new("L", image.size, 0)
mask_pixels = mask.load()
for index in largest:
    mask_pixels[index % width, index // width] = 255
mask = mask.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.GaussianBlur(1.5))

rgba = image.convert("RGBA")
rgba_pixels = rgba.load()
for y in range(height):
    for x in range(width):
        if mask.getpixel((x, y)) <= 0:
            continue
        red, green, blue = pixels[x, y]
        if red - blue <= 5 or red - green <= 1:
            rgba_pixels[x, y] = (247, 242, 232, 255)
rgba.putalpha(mask)
canvas = Image.new("RGBA", (1024, 512), (0, 0, 0, 0))
crop = rgba.crop((190, 75, 840, 485))
canvas.alpha_composite(crop, ((1024 - crop.width) // 2, (512 - crop.height) // 2))
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
canvas.save(OUTPUT)
print(f"wrote={OUTPUT} component_pixels={len(largest)}")
