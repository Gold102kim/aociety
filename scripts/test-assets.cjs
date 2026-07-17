const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const glbPath = path.join(root, 'public', 'models', 'ecy-avatar.glb');
const previewPath = path.join(root, 'public', 'models', 'ecy-avatar-preview.png');
const iconPath = path.join(root, 'build', 'icon.ico');
const maximumGlbBytes = 25 * 1024 * 1024;

assert.ok(fs.existsSync(glbPath), 'Avatar GLB is missing.');
assert.ok(fs.existsSync(previewPath), 'Avatar preview PNG is missing.');
assert.ok(fs.existsSync(iconPath), 'Windows application icon is missing.');

const glb = fs.readFileSync(glbPath);
assert.ok(glb.length <= maximumGlbBytes, `Avatar GLB exceeds ${maximumGlbBytes} bytes.`);
assert.equal(glb.subarray(0, 4).toString('ascii'), 'glTF');
assert.equal(glb.readUInt32LE(4), 2, 'Avatar must use glTF 2.0.');
assert.equal(glb.readUInt32LE(8), glb.length, 'GLB header length does not match file size.');

const jsonChunkLength = glb.readUInt32LE(12);
const jsonChunkType = glb.readUInt32LE(16);
assert.equal(jsonChunkType, 0x4e4f534a, 'First GLB chunk must be JSON.');
const document = JSON.parse(glb.subarray(20, 20 + jsonChunkLength).toString('utf8').trimEnd());
assert.ok((document.meshes?.length ?? 0) > 0, 'Avatar contains no meshes.');
assert.ok((document.images?.length ?? 0) >= 5, 'Avatar is missing embedded textures.');
assert.ok((document.skins?.length ?? 0) >= 1, 'Avatar is missing its skeleton skin.');

const preview = fs.readFileSync(previewPath);
assert.deepEqual([...preview.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10], 'Preview is not a PNG.');

const icon = fs.readFileSync(iconPath);
assert.deepEqual([...icon.subarray(0, 4)], [0, 0, 1, 0], 'Application icon is not an ICO file.');
assert.ok(icon.readUInt16LE(4) >= 6, 'Application icon must contain multiple Windows sizes.');

console.log(`Avatar asset tests passed (${(glb.length / 1024 / 1024).toFixed(2)} MiB).`);
