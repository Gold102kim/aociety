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
const manifest = JSON.parse(fs.readFileSync(path.join(dist, '.vite/manifest.json'), 'utf8'));
const entries = Object.keys(manifest).filter((key) => manifest[key].isEntry);
assert.equal(entries.length, 1, 'Production build must have exactly one HTML entry.');
function collectFiles(includeDynamic) {
  const visited = new Set();
  const files = new Set();
  function visit(key) {
    if (visited.has(key)) return;
    visited.add(key);
    const record = manifest[key];
    assert.ok(record, `Missing build manifest record: ${key}`);
    for (const file of [record.file, ...(record.css || []), ...(record.assets || [])]) files.add(file);
    for (const child of [...(record.imports || []), ...(includeDynamic ? record.dynamicImports || [] : [])]) visit(child);
  }
  visit(entries[0]);
  return files;
}
const reachableAssets = [...collectFiles(true)].filter((file) => file.startsWith('assets/')).map((file) => file.slice(7)).sort();
const assertAssets = (files) => assert.deepEqual([...files].sort(), reachableAssets, 'Build contains stale or missing assets outside the reachable manifest.');
assertAssets(assetFiles);
assert.throws(() => assertAssets([...assetFiles, 'stale-example.js']), /stale or missing/);
assert.throws(() => assertAssets(assetFiles.slice(1)), /stale or missing/);
assert.ok(assetFiles.some((name) => name.startsWith('AvatarViewport-') && name.endsWith('.js')), 'Lazy 3D chunk is missing.');
assert.ok(assetFiles.some((name) => name.startsWith('index-') && name.endsWith('.js')), 'Application JavaScript chunk is missing.');
assert.ok(assetFiles.some((name) => name.startsWith('index-') && name.endsWith('.css')), 'Application CSS chunk is missing.');
for (const page of ['LauncherHome', 'CompanionApp', 'WorldPage', 'AvatarPage', 'SocialPage', 'ProfilePage']) {
  assert.ok(assetFiles.some((name) => name.startsWith(`${page}-`) && name.endsWith('.js')), `${page} must remain lazy-loaded.`);
}
const entryName = assetFiles.find((name) => name.startsWith('index-') && name.endsWith('.js'));
const entryBytes = [...collectFiles(false)].filter((file) => file.endsWith('.js')).reduce((bytes, file) => bytes + fs.statSync(path.join(dist, file)).size, 0);
assert.ok(entryBytes <= 225 * 1024, `Initial JavaScript exceeds the 225 KiB budget: ${entryBytes} bytes.`);
assert.ok(fs.readFileSync(path.join(dist, 'index.html'), 'utf8').includes(`./assets/${entryName}`), 'HTML entry must reference the current build.');
assert.equal(assetFiles.some((name) => name.endsWith('.map')), false, 'Production source maps must not be shipped in the prototype package.');

for (const forbidden of ['accounts.json', 'accounts.json.bak', 'ai.json']) {
  assert.equal(fs.existsSync(path.join(dist, forbidden)), false, `${forbidden} must not be included in dist.`);
}

console.log(`Production build output checks passed (${assetFiles.length} assets; initial JS ${(entryBytes / 1024).toFixed(1)} KiB).`);
