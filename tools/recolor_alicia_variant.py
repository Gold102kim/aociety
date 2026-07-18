from pathlib import Path

from PIL import Image, ImageEnhance


ROOT = Path(r"E:\Aociety-NEW\SourceAssets\Characters\NPC_Cute\Export\AliciaSakura\Textures")


def hue_shift(path: Path, offset: int, saturation: float) -> None:
    image = Image.open(path).convert("RGBA")
    alpha = image.getchannel("A")
    hsv = image.convert("RGB").convert("HSV")
    hue, sat, value = hsv.split()
    hue = hue.point(lambda value: (value + offset) % 256)
    shifted = Image.merge("HSV", (hue, sat, value)).convert("RGB")
    shifted = ImageEnhance.Color(shifted).enhance(saturation)
    shifted.putalpha(alpha)
    shifted.save(path)


hue_shift(ROOT / "Alicia_hair.png", 205, 1.35)
hue_shift(ROOT / "Alicia_wear.png", 48, 1.25)
print("[AocietyCharacterVariant] AliciaSakura textures recolored")
