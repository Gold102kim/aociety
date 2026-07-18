from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


OUT_DIR = Path(r"E:\Aociety-NEW\ue5_project\SourceAssets\Snow")
SIZE = 2048
SEED = 20260715


def octave_noise(size, rng):
    result = np.zeros((size, size), dtype=np.float32)
    weight_sum = 0.0
    for grid, weight in ((16, 0.42), (32, 0.28), (64, 0.18), (128, 0.08), (512, 0.04)):
        small = rng.random((grid, grid), dtype=np.float32)
        image = Image.fromarray(np.uint8(small * 255), mode="L").resize((size, size), Image.Resampling.BICUBIC)
        image = image.filter(ImageFilter.GaussianBlur(max(0.5, size / grid / 8)))
        result += (np.asarray(image, dtype=np.float32) / 255.0) * weight
        weight_sum += weight
    return result / weight_sum


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    height = octave_noise(SIZE, rng)
    height = np.clip((height - 0.35) / 0.35, 0.0, 1.0)
    crystals = rng.random((SIZE, SIZE), dtype=np.float32)
    sparkle = np.where(crystals > 0.9975, (crystals - 0.9975) * 200.0, 0.0)

    base = np.empty((SIZE, SIZE, 3), dtype=np.uint8)
    base[..., 0] = np.clip(226 + height * 27 + sparkle * 3, 0, 255)
    base[..., 1] = np.clip(232 + height * 23 + sparkle * 3, 0, 255)
    base[..., 2] = np.clip(240 + height * 15 + sparkle * 2, 0, 255)
    Image.fromarray(base, mode="RGB").save(OUT_DIR / "T_Snow_BaseColor.png", compress_level=4)

    gradient_y, gradient_x = np.gradient(height)
    strength = 14.0
    nx = -gradient_x * strength
    ny = gradient_y * strength
    nz = np.ones_like(height)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    normal = np.stack((nx / length, ny / length, nz / length), axis=-1)
    normal = np.uint8(np.clip(normal * 0.5 + 0.5, 0.0, 1.0) * 255)
    Image.fromarray(normal, mode="RGB").save(OUT_DIR / "T_Snow_Normal.png", compress_level=4)

    roughness = np.uint8(np.clip(205 + (1.0 - height) * 35 - sparkle * 12, 120, 245))
    Image.fromarray(roughness, mode="L").save(OUT_DIR / "T_Snow_Roughness.png", compress_level=4)
    print(f"Generated snow textures in {OUT_DIR}")


if __name__ == "__main__":
    main()
