const assert = require('node:assert/strict');
const fs = require('node:fs');
const { validatePackageEntry, verifyElectronRuntime } = require('./audit-local-package.cjs');
const plain = Buffer.from('public build content');
const validate = (file, metadata = {}, bytes = plain) => validatePackageEntry(file, { size: bytes.length, ...metadata }, bytes);
for (const file of ['package.json', 'dist/index.html', 'dist/assets/page.js', 'dist/models/README.md', 'dist-electron/main.js']) assert.doesNotThrow(() => validate(file));
for (const file of ['config/ai.local.json', 'dist/ai.json', 'dist/accounts.json', 'dist/auth.json', 'dist/data/profile.bin', 'dist/models/private.glb', 'dist/models/avatar.vrm', 'dist/game.umap', 'dist/voice.wav', 'dist/config/example.json', 'dist-electron/fixtures/mock.js', 'dist/../other.js', 'dist/node_modules/anything.js']) {
  assert.throws(() => validate(file), undefined, file);
}
for (const metadata of [{ link: 'elsewhere' }, { unpacked: true }, { size: 32 * 1024 * 1024 + 1 }]) assert.throws(() => validate('dist/assets/page.js', metadata));
const fakeSecret = `sk-${'x'.repeat(28)}`;
assert.throws(() => validate('dist/assets/page.js', {}, Buffer.from(fakeSecret)), /Sensitive content/);
const pkg = require('../package.json');
for (const command of ['dist:win', 'dist:representative-local']) {
  const stages = pkg.scripts[command].split('&&').map((stage) => stage.trim());
  assert.deepEqual(stages.slice(0, 2), ['pnpm audit --audit-level high', 'pnpm check'], `${command} must reject high-risk dependencies before checking or packaging.`);
  assert.ok(stages.length > 2, `${command} must build only after the safety gates.`);
}

const expectedElectron = pkg.devDependencies.electron;
const auditSource = fs.readFileSync(require.resolve('./audit-local-package.cjs'), 'utf8');
assert.ok(auditSource.includes("const expectedElectron = require('../package.json').devDependencies.electron;"), 'The root exact pin, not installed metadata, must define the expected runtime.');
assert.ok(auditSource.includes('assert.equal(require(electronPackage).version, expectedElectron,'), 'Stale installed npm metadata must be rejected before trusting its runtime.');
const inheritedRunAsNode = process.env.ELECTRON_RUN_AS_NODE;
const inheritedNodeOptions = process.env.NODE_OPTIONS;
const passedProbe = (executable, args, options) => {
  assert.equal(executable, 'isolated-electron-fixture.exe');
  assert.deepEqual(args, ['-p', 'process.versions.electron']);
  assert.equal(options.env.ELECTRON_RUN_AS_NODE, '1');
  assert.equal(options.env.NODE_OPTIONS, '');
  assert.equal(options.timeout, 5000);
  assert.equal(options.killSignal, 'SIGKILL');
  assert.equal(options.maxBuffer, 1024);
  assert.equal(options.windowsHide, true);
  assert.deepEqual(options.stdio, ['ignore', 'pipe', 'pipe']);
  return { status: 0, signal: null, stdout: `${expectedElectron}\n` };
};
assert.equal(verifyElectronRuntime('isolated-electron-fixture.exe', expectedElectron, passedProbe), expectedElectron);
for (const stdout of ['0.0.0', '', 'undefined', `${expectedElectron}\nunexpected extra output`]) {
  assert.throws(() => verifyElectronRuntime('isolated-electron-fixture.exe', expectedElectron, () => ({ status: 0, stdout })), /does not match/);
}
for (const result of [
  { status: 1, stdout: expectedElectron },
  { status: null, stdout: '' },
  { status: null, error: Object.assign(new Error('fixture timeout'), { code: 'ETIMEDOUT' }) },
  { status: 0, signal: 'SIGKILL', stdout: expectedElectron },
]) {
  assert.throws(() => verifyElectronRuntime('isolated-electron-fixture.exe', expectedElectron, () => result), /failed or timed out/);
}
assert.equal(process.env.ELECTRON_RUN_AS_NODE, inheritedRunAsNode, 'The probe must not change its caller environment.');
assert.equal(process.env.NODE_OPTIONS, inheritedNodeOptions, 'The probe must not change its caller preloads.');
console.log('Package policy passed: allowlisted contents, private data and model exclusion, audit-before-build gates and bounded actual Electron version verification.');
