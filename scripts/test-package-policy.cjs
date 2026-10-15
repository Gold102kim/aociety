const assert = require('node:assert/strict');
const { validatePackageEntry } = require('./audit-local-package.cjs');
const plain = Buffer.from('public build content');
const validate = (file, metadata = {}, bytes = plain) => validatePackageEntry(file, { size: bytes.length, ...metadata }, bytes);
for (const file of ['package.json', 'dist/index.html', 'dist/assets/page.js', 'dist/models/README.md', 'dist-electron/main.js']) assert.doesNotThrow(() => validate(file));
for (const file of ['config/ai.local.json', 'dist/ai.json', 'dist/accounts.json', 'dist/auth.json', 'dist/data/profile.bin', 'dist/models/private.glb', 'dist/models/avatar.vrm', 'dist/game.umap', 'dist/voice.wav', 'dist/config/example.json', 'dist-electron/fixtures/mock.js', 'dist/../other.js', 'dist/node_modules/anything.js']) {
  assert.throws(() => validate(file), undefined, file);
}
for (const metadata of [{ link: 'elsewhere' }, { unpacked: true }, { size: 32 * 1024 * 1024 + 1 }]) assert.throws(() => validate('dist/assets/page.js', metadata));
const fakeSecret = `sk-${'x'.repeat(28)}`;
assert.throws(() => validate('dist/assets/page.js', {}, Buffer.from(fakeSecret)), /Sensitive content/);
console.log('Package policy passed: allowlisted application paths, private stores/configs, model/game binaries, test fixtures, path traversal, external entries, size limits and embedded credentials.');
