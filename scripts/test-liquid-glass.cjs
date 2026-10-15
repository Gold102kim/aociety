const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { stripTypeScriptTypes } = require('node:module');

const source = fs.readFileSync(path.resolve(__dirname, '../src/liquidGlassOptics.ts'), 'utf8')
  .replace(/export function/g, 'function');
const api = {};
vm.runInNewContext(`${stripTypeScriptTypes(source)}\napi.create = createGlassDisplacement;`, { api, Uint8ClampedArray });

function pixel(map, x, y) {
  return Array.from(map.pixels.subarray((y * map.width + x) * 4, (y * map.width + x) * 4 + 4));
}

function assertSymmetric(map) {
  for (let y = 0; y < map.height; y += 1) {
    for (let x = 0; x < map.width; x += 1) {
      const current = pixel(map, x, y);
      const horizontal = pixel(map, map.width - 1 - x, y);
      const vertical = pixel(map, x, map.height - 1 - y);
      assert.equal(current[0] + horizontal[0], 256, 'Horizontal refraction must mirror around neutral red.');
      assert.equal(current[1], horizontal[1], 'Horizontal reflection must preserve the vertical component.');
      assert.equal(current[0], vertical[0], 'Vertical reflection must preserve the horizontal component.');
      assert.equal(current[1] + vertical[1], 256, 'Vertical refraction must mirror around neutral green.');
      assert.equal(current[2], 128, 'Blue must stay neutral.');
      assert.equal(current[3], 255, 'Every displacement sample must be opaque.');
    }
  }
}

for (const dimensions of [[220, 80, 22], [101, 71, 20], [40, 40, 20], [49, 31, 0], [19, 9, 2]]) {
  const map = api.create(...dimensions);
  assertSymmetric(map);
  assert.ok(map.scale >= 0 && map.scale <= 8, 'Displacement scale must stay within 8 CSS pixels.');
  assert.ok(map.scale / 2 * Math.PI / Math.min(14, dimensions[0] / 4, dimensions[1] / 4) < 1, 'The bevel gradient must not fold the backdrop back over itself.');
  assert.equal(map.pixels.length, map.width * map.height * 4);
  assert.ok(map.pixels instanceof Uint8ClampedArray);
}

const map = api.create(220, 80, 22);
assert.equal(map.width, 220, 'Small elements must not be upscaled to the texture limit.');
assert.equal(map.height, 80);
assert.deepEqual(pixel(map, 110, 40), [128, 128, 128, 255], 'The reading area must not refract.');
assert.deepEqual(pixel(map, 0, 0), [128, 128, 128, 255], 'The area outside rounded corners must stay neutral.');
assert.ok(pixel(map, 6, 40)[0] > 128, 'The left edge must sample inward, to the right.');
assert.ok(pixel(map, 213, 40)[0] < 128, 'The right edge must sample inward, to the left.');
assert.ok(pixel(map, 110, 6)[1] > 128, 'The top edge must sample inward, downward.');
assert.ok(pixel(map, 110, 73)[1] < 128, 'The bottom edge must sample inward, upward.');
assert.equal(pixel(map, 6, 40)[1], 128, 'A straight vertical edge must not drift vertically.');
assert.equal(pixel(map, 110, 6)[0], 128, 'A straight horizontal edge must not drift horizontally.');
assert.deepEqual(pixel(map, 14, 40), [128, 128, 128, 255], 'Refraction must end after the physical bevel.');
assert.ok(pixel(map, 0, 40)[0] < pixel(map, 6, 40)[0], 'The outer bevel must ease into its peak.');
assert.ok(pixel(map, 12, 40)[0] < pixel(map, 6, 40)[0], 'The bevel must ease back into the neutral interior.');
const corner = pixel(map, 10, 10);
assert.ok(corner[0] > 128 && corner[1] > 128, 'The rounded top-left bevel must bend both components inward.');
assert.equal(corner[0], corner[1], 'A circular corner must have a smooth radial normal.');

const large = api.create(1920, 1080, 30);
assert.equal(large.width, 512);
assert.equal(large.height, 288, 'Downsampling must preserve the element aspect ratio.');
assertSymmetric(large);
const portrait = api.create(1080, 1920, 30);
assert.equal(portrait.width, 288);
assert.equal(portrait.height, 512);
assert.ok(pixel(large, 1, 144)[0] > 128, 'Downsampled edges must retain their physical CSS-pixel bevel.');
assert.deepEqual(pixel(large, 5, 144), [128, 128, 128, 255], 'Texture downsampling must not expand the CSS bevel.');

for (const dimensions of [[0.01, 0.02], [Number.MIN_VALUE, Number.MIN_VALUE], [1, 1], [1, 1000000], [Number.MAX_VALUE, Number.MAX_VALUE], [Number.MAX_VALUE, Number.MIN_VALUE]]) {
  const smallOrHuge = api.create(...dimensions, 30);
  assert.ok(Number.isInteger(smallOrHuge.width) && smallOrHuge.width >= 1 && smallOrHuge.width <= 512);
  assert.ok(Number.isInteger(smallOrHuge.height) && smallOrHuge.height >= 1 && smallOrHuge.height <= 512);
  assert.ok(smallOrHuge.pixels.byteLength <= 512 * 512 * 4, 'Finite dimensions must never cause unbounded allocation.');
  assert.ok(Number.isFinite(smallOrHuge.scale) && smallOrHuge.scale >= 0 && smallOrHuge.scale <= 24);
}

assert.deepEqual(api.create(60, 40, -20).pixels, api.create(60, 40, 0).pixels, 'Negative radius must clamp to zero.');
assert.deepEqual(api.create(60, 40, 200).pixels, api.create(60, 40, 20).pixels, 'Radius must clamp to half the shorter dimension.');
assert.deepEqual(api.create(220, 80, 22).pixels, map.pixels, 'The optical field must be deterministic.');
for (const invalid of [0, -1, NaN, Infinity, -Infinity, undefined, null, '20']) {
  assert.throws(() => api.create(invalid, 80, 20), /finite, positive CSS pixels/);
  assert.throws(() => api.create(220, invalid, 20), /finite, positive CSS pixels/);
}
for (const invalid of [NaN, Infinity, -Infinity, undefined, null, '20']) {
  assert.throws(() => api.create(220, 80, invalid), /radius must be finite/);
}

console.log('Liquid glass optics passed: bounded texture allocation, inward rounded refraction, symmetry, neutral content, physical bevel, deterministic output and invalid inputs.');
