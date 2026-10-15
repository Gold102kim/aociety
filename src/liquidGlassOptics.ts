export function createGlassDisplacement(
  width: number,
  height: number,
  radius: number,
): { width: number; height: number; pixels: Uint8ClampedArray; scale: number } {
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    throw new RangeError('Glass dimensions must be finite, positive CSS pixels.');
  }
  if (!Number.isFinite(radius)) {
    throw new RangeError('Glass radius must be finite CSS pixels.');
  }

  const longest = Math.max(width, height);
  const textureLongest = Math.min(512, Math.ceil(longest));
  const textureWidth = Math.max(1, Math.round(textureLongest * (width / longest)));
  const textureHeight = Math.max(1, Math.round(textureLongest * (height / longest)));
  const pixels = new Uint8ClampedArray(textureWidth * textureHeight * 4);
  const cornerRadius = Math.max(0, Math.min(radius, Math.min(width, height) / 2));
  const bevel = Math.min(14, Math.min(width, height) / 4);
  // Keep the optical gradient below a fold: edges bend rather than double back.
  const scale = Math.min(8, bevel * .55);

  for (let y = 0; y < textureHeight; y += 1) {
    const pointY = ((2 * y + 1 - textureHeight) / (2 * textureHeight)) * height;
    for (let x = 0; x < textureWidth; x += 1) {
      const offset = (y * textureWidth + x) * 4;
      pixels[offset] = 128;
      pixels[offset + 1] = 128;
      pixels[offset + 2] = 128;
      pixels[offset + 3] = 255;
      if (bevel === 0) continue;

      const pointX = ((2 * x + 1 - textureWidth) / (2 * textureWidth)) * width;
      const edgeX = Math.abs(pointX) - (width / 2 - cornerRadius);
      const edgeY = Math.abs(pointY) - (height / 2 - cornerRadius);
      const outsideX = Math.max(edgeX, 0);
      const outsideY = Math.max(edgeY, 0);
      const cornerDistance = Math.hypot(outsideX, outsideY);
      const distance = cornerDistance + Math.min(Math.max(edgeX, edgeY), 0) - cornerRadius;
      if (distance >= 0 || distance <= -bevel) continue;

      let normalX = 0;
      let normalY = 0;
      if (cornerDistance > 0) {
        normalX = (outsideX / cornerDistance) * Math.sign(pointX);
        normalY = (outsideY / cornerDistance) * Math.sign(pointY);
      } else if (edgeX > edgeY) {
        normalX = Math.sign(pointX);
      } else if (edgeY > edgeX) {
        normalY = Math.sign(pointY);
      } else {
        normalX = Math.sign(pointX) * Math.SQRT1_2;
        normalY = Math.sign(pointY) * Math.SQRT1_2;
      }

      // A smooth, bounded bevel refracts inward without warping the reading area.
      const strength = Math.sin((Math.PI * -distance) / bevel) ** 2;
      pixels[offset] -= Math.sign(normalX) * Math.round(Math.abs(normalX) * 127 * strength);
      pixels[offset + 1] -= Math.sign(normalY) * Math.round(Math.abs(normalY) * 127 * strength);
    }
  }

  return { width: textureWidth, height: textureHeight, pixels, scale };
}
