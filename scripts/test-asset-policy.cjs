const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { validateAssets } = require('./test-assets.cjs');

const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'aociety-asset-policy-'));
const paths = {
  glbPath: path.join(directory, 'avatar.glb'),
  previewPath: path.join(directory, 'preview.png'),
  iconPath: path.join(directory, 'icon.ico'),
};
try {
  fs.writeFileSync(paths.iconPath, Buffer.from([0, 0, 1, 0, 6, 0]));
  assert.throws(() => validateAssets(paths), /Avatar GLB is missing/);
  assert.equal(validateAssets(paths, true).skippedAvatar, true, 'Only explicitly opted-in source-only mode may omit both avatar files.');
  fs.writeFileSync(paths.glbPath, Buffer.from('corrupt'));
  assert.throws(() => validateAssets(paths, true), /preview PNG is missing/, 'A partial asset pair must fail even in source-only mode.');
  fs.writeFileSync(paths.previewPath, Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]));
  assert.throws(() => validateAssets(paths, true), /header is truncated/, 'Present but corrupt assets must never be skipped.');
  const json = JSON.stringify({ meshes: [{}], images: [{}, {}, {}, {}, {}], skins: [{}] });
  const padded = Buffer.from(json.padEnd(Math.ceil(json.length / 4) * 4, ' '));
  const header = Buffer.alloc(20);
  header.write('glTF', 0, 'ascii');
  header.writeUInt32LE(2, 4);
  header.writeUInt32LE(header.length + padded.length, 8);
  header.writeUInt32LE(padded.length, 12);
  header.writeUInt32LE(0x4e4f534a, 16);
  fs.writeFileSync(paths.glbPath, Buffer.concat([header, padded]));
  assert.equal(validateAssets(paths, true).skippedAvatar, false);
  assert.equal(validateAssets(paths).skippedAvatar, false);
  fs.writeFileSync(paths.previewPath, Buffer.from('not a PNG'));
  assert.throws(() => validateAssets(paths, true), /not a PNG/, 'A corrupt preview may not be skipped.');
  fs.rmSync(paths.glbPath);
  assert.throws(() => validateAssets(paths, true), /GLB is missing/, 'The other partial-pair direction must also fail.');
  fs.rmSync(paths.previewPath);
  fs.rmSync(paths.iconPath);
  assert.throws(() => validateAssets(paths, true), /icon is missing/, 'Source-only mode still requires distributable application assets.');
  console.log('Local asset policy regression tests passed.');
} finally {
  fs.rmSync(directory, { recursive: true, force: true });
}
