const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

function validateAssets({ glbPath, previewPath, iconPath }, allowMissingLocalAssets = false) {
  const hasGlb = fs.existsSync(glbPath);
  const hasPreview = fs.existsSync(previewPath);
  const skipAvatar = allowMissingLocalAssets && !hasGlb && !hasPreview;
  assert.ok(fs.existsSync(iconPath), 'Windows application icon is missing.');
  const icon = fs.readFileSync(iconPath);
  assert.ok(icon.length >= 6, 'Application icon header is truncated.');
  assert.deepEqual([...icon.subarray(0, 4)], [0, 0, 1, 0], 'Application icon is not an ICO file.');
  assert.ok(icon.readUInt16LE(4) >= 6, 'Application icon must contain multiple Windows sizes.');

  if (skipAvatar) return { skippedAvatar: true, glbBytes: 0 };
  assert.ok(hasGlb, 'Avatar GLB is missing. Restore licensed local assets or explicitly use source-only mode when both avatar files are absent.');
  assert.ok(hasPreview, 'Avatar preview PNG is missing. Partial local assets may not be skipped.');
  const glb = fs.readFileSync(glbPath);
  assert.ok(glb.length <= 25 * 1024 * 1024, 'Avatar GLB exceeds 25 MiB.');
  assert.ok(glb.length >= 20, 'GLB header is truncated.');
  assert.equal(glb.subarray(0, 4).toString('ascii'), 'glTF');
  assert.equal(glb.readUInt32LE(4), 2, 'Avatar must use glTF 2.0.');
  assert.equal(glb.readUInt32LE(8), glb.length, 'GLB header length does not match file size.');

  const jsonChunkLength = glb.readUInt32LE(12);
  assert.equal(glb.readUInt32LE(16), 0x4e4f534a, 'First GLB chunk must be JSON.');
  assert.ok(jsonChunkLength > 0 && jsonChunkLength % 4 === 0, 'GLB JSON chunk must be nonempty and aligned.');
  assert.ok(20 + jsonChunkLength <= glb.length, 'GLB JSON chunk exceeds file size.');
  const document = JSON.parse(glb.subarray(20, 20 + jsonChunkLength).toString('utf8').trimEnd());
  assert.ok((document.meshes?.length ?? 0) > 0, 'Avatar contains no meshes.');
  assert.ok((document.images?.length ?? 0) >= 5, 'Avatar is missing embedded textures.');
  assert.ok((document.skins?.length ?? 0) >= 1, 'Avatar is missing its skeleton skin.');
  const preview = fs.readFileSync(previewPath);
  assert.deepEqual([...preview.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10], 'Preview is not a PNG.');
  return { skippedAvatar: false, glbBytes: glb.length };
}

module.exports = { validateAssets };

if (require.main === module) {
  const root = path.resolve(__dirname, '..');
  const result = validateAssets({
    glbPath: path.join(root, 'public', 'models', 'ecy-avatar.glb'),
    previewPath: path.join(root, 'public', 'models', 'ecy-avatar-preview.png'),
    iconPath: path.join(root, 'build', 'icon.ico'),
  }, process.env.ECHO_ALLOW_MISSING_LOCAL_ASSETS === '1');
  if (result.skippedAvatar) {
    console.log('SOURCE-ONLY: licensed local avatar model and preview are both absent; avatar validation explicitly skipped. Application icon validated. See public/models/README.md.');
  } else {
    console.log(`Avatar asset tests passed (${(result.glbBytes / 1024 / 1024).toFixed(2)} MiB).`);
  }
  require('./test-asset-policy.cjs');
}
