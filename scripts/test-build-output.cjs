const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const dist = path.join(root, 'dist');
const assets = path.join(dist, 'assets');

assert.ok(fs.existsSync(path.join(dist, 'index.html')), 'dist/index.html is missing.');
assert.ok(fs.existsSync(assets), 'dist/assets is missing.');

const assetFiles = fs.readdirSync(assets, { withFileTypes: true }).filter((entry) => entry.isFile()).map((entry) => entry.name);
assert.ok(assetFiles.length >= 3, 'Production build is missing expected JavaScript/CSS chunks.');
assert.ok(assetFiles.length <= 10, `Production build contains ${assetFiles.length} assets; stale hashed files may be present.`);
assert.ok(assetFiles.some((name) => name.startsWith('AvatarViewport-') && name.endsWith('.js')), 'Lazy 3D chunk is missing.');
assert.ok(assetFiles.some((name) => name.startsWith('index-') && name.endsWith('.js')), 'Application JavaScript chunk is missing.');
assert.ok(assetFiles.some((name) => name.startsWith('index-') && name.endsWith('.css')), 'Application CSS chunk is missing.');
assert.equal(assetFiles.some((name) => name.endsWith('.map')), false, 'Production source maps must not be shipped in the prototype package.');

for (const forbidden of ['accounts.json', 'accounts.json.bak', 'ai.json']) {
  assert.equal(fs.existsSync(path.join(dist, forbidden)), false, `${forbidden} must not be included in dist.`);
}

console.log(`Production build output checks passed (${assetFiles.length} assets).`);
