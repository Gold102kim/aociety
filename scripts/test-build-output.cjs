const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const dist = path.join(root, 'dist');
const assets = path.join(dist, 'assets');

assert.ok(fs.existsSync(path.join(dist, 'index.html')), 'dist/index.html is missing.');
assert.ok(fs.existsSync(assets), 'dist/assets is missing.');
assert.ok(fs.existsSync(path.join(dist, 'illustrations/forest-town.svg')), 'Home concept illustration is missing.');

const assetFiles = fs.readdirSync(assets, { withFileTypes: true }).filter((entry) => entry.isFile()).map((entry) => entry.name);
assert.ok(assetFiles.length >= 3, 'Production build is missing expected JavaScript/CSS chunks.');
assert.ok(assetFiles.length <= 10, `Production build contains ${assetFiles.length} assets; stale hashed files may be present.`);
assert.ok(assetFiles.some((name) => name.startsWith('AvatarViewport-') && name.endsWith('.js')), 'Lazy 3D chunk is missing.');
assert.ok(assetFiles.some((name) => name.startsWith('index-') && name.endsWith('.js')), 'Application JavaScript chunk is missing.');
assert.ok(assetFiles.some((name) => name.startsWith('index-') && name.endsWith('.css')), 'Application CSS chunk is missing.');
for (const page of ['LauncherHome', 'CompanionApp', 'WorldPage', 'AvatarPage', 'SocialPage', 'ProfilePage']) {
  assert.ok(assetFiles.some((name) => name.startsWith(`${page}-`) && name.endsWith('.js')), `${page} must remain lazy-loaded.`);
}
const entryName = assetFiles.find((name) => name.startsWith('index-') && name.endsWith('.js'));
const entryBytes = fs.statSync(path.join(assets, entryName)).size;
assert.ok(entryBytes <= 225 * 1024, `Initial JavaScript exceeds the 225 KiB budget: ${entryBytes} bytes.`);
assert.equal(assetFiles.some((name) => name.endsWith('.map')), false, 'Production source maps must not be shipped in the prototype package.');

for (const forbidden of ['accounts.json', 'accounts.json.bak', 'ai.json']) {
  assert.equal(fs.existsSync(path.join(dist, forbidden)), false, `${forbidden} must not be included in dist.`);
}

console.log(`Production build output checks passed (${assetFiles.length} assets; initial JS ${(entryBytes / 1024).toFixed(1)} KiB).`);
