const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { createHash } = require('node:crypto');
const { createRequire } = require('node:module');
const { spawnSync } = require('node:child_process');
const { scanTextContent, sensitiveFileReason } = require('./test-secrets.cjs');
const builder = createRequire(require.resolve('electron-builder'));
const asar = createRequire(builder.resolve('app-builder-lib'))('@electron/asar');
const root = path.resolve(__dirname, '..');
const hash = (bytes) => createHash('sha256').update(bytes).digest('hex').toUpperCase();
const nativeEntry = (file) => file.replaceAll('/', path.sep);

function verifyElectronRuntime(executable, expectedVersion, probe = spawnSync) {
  // Run only the version expression, never the application or inherited preloads.
  const result = probe(executable, ['-p', 'process.versions.electron'], {
    env: { ...process.env, ELECTRON_RUN_AS_NODE: '1', NODE_OPTIONS: '' },
    encoding: 'utf8', timeout: 5000, killSignal: 'SIGKILL', maxBuffer: 1024,
    stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true,
  });
  assert.ok(!result.error && result.status === 0 && !result.signal, 'Electron runtime version probe failed or timed out.');
  const version = String(result.stdout ?? '').trim();
  assert.ok(version === expectedVersion, 'Electron runtime does not match the locked package version.');
  return version;
}

function validatePackageEntry(file, metadata, bytes) {
  assert.ok(file === 'package.json' || file.startsWith('dist/') || file.startsWith('dist-electron/'), 'Unexpected application path.');
  assert.ok(!file.split('/').some((part) => ['..', '.', 'node_modules', 'fixtures', 'config', 'logs'].includes(part)), 'Private or external directory in package.');
  assert.equal(sensitiveFileReason(file), null, 'Private configuration or account file in package.');
  assert.equal(/\.(?:glb|gltf|fbx|vrm|uasset|umap|blend|bin|mp3|wav)$/i.test(file), false, 'Unapproved model, game or personal binary in package.');
  assert.ok(!metadata.link && !metadata.unpacked && metadata.size <= 32 * 1024 * 1024, 'Unexpected external, linked or oversized entry.');
  assert.deepEqual(scanTextContent(bytes.toString('utf8')), [], `Sensitive content in packaged file: ${file}`);
}

function auditPackage(directory) {
  const archive = path.join(directory, 'win-unpacked/resources/app.asar');
  assert.ok(fs.existsSync(archive), 'Packaged application archive is missing.');
  const files = asar.listPackage(archive).map((file) => file.replaceAll('\\', '/').replace(/^\//, ''))
    .filter((file) => !asar.statFile(archive, nativeEntry(file), false).files).sort();
  const expected = [];
  function visit(folder) {
    for (const entry of fs.readdirSync(path.join(root, folder), { withFileTypes: true })) {
      const file = `${folder}/${entry.name}`;
      if (file.startsWith('dist/.vite/') || file === 'dist/.vite' || (file.startsWith('dist/models/') && file !== 'dist/models/README.md')) continue;
      assert.equal(entry.isSymbolicLink(), false, 'Build input must not contain links.');
      if (entry.isDirectory()) visit(file);
      else expected.push(file);
    }
  }
  visit('dist'); visit('dist-electron');
  assert.deepEqual(files, [...expected, 'package.json'].sort(), 'Unexpected, private, stale or missing files in ASAR.');
  const manifest = [];
  for (const file of files) {
    const metadata = asar.statFile(archive, nativeEntry(file), false);
    // Reject external entries and oversized claims before allocating their body.
    assert.ok(!metadata.link && !metadata.unpacked && metadata.size <= 32 * 1024 * 1024, 'Unsafe package entry metadata.');
    const bytes = asar.extractFile(archive, nativeEntry(file));
    validatePackageEntry(file, metadata, bytes);
    if (file !== 'package.json') assert.equal(hash(bytes), hash(fs.readFileSync(path.join(root, file))), `Build differs from packaged file: ${file}`);
    manifest.push({ file, bytes: bytes.length, sha256: hash(bytes) });
  }
  const pkg = JSON.parse(asar.extractFile(archive, 'package.json').toString('utf8'));
  assert.equal(pkg.main, 'dist-electron/main.js');
  assert.equal(pkg.version, require('../package.json').version);
  assert.equal(Boolean(pkg.dependencies && Object.keys(pkg.dependencies).length), false, 'Unexpected production dependencies.');
  for (const module of ['representative-store', 'representative-chat', 'simulation-types', 'representative-types', 'preload']) {
    assert.ok(files.includes(`dist-electron/${module}.js`), `Missing digital representative module: ${module}`);
  }
  const main = asar.extractFile(archive, nativeEntry('dist-electron/main.js')).toString('utf8');
  for (const ipc of ['representative:continuation', 'ai:simulate', 'representative:update']) assert.ok(main.includes(ipc));
  assert.equal(fs.existsSync(`${archive}.unpacked`), false, 'Unexpected unpacked application files.');
  const electronPackage = require.resolve('electron/package.json');
  const expectedElectron = require('../package.json').devDependencies.electron;
  assert.equal(require(electronPackage).version, expectedElectron, 'Installed Electron package does not match the root version pin.');
  verifyElectronRuntime(path.join(path.dirname(electronPackage), 'dist/electron.exe'), expectedElectron);
  const electron = verifyElectronRuntime(path.join(directory, 'win-unpacked/EchoVerseLauncher.exe'), expectedElectron);
  return { version: pkg.version, electron, asarSha256: hash(fs.readFileSync(archive)), files: manifest };
}

module.exports = { auditPackage, hash, validatePackageEntry, verifyElectronRuntime };
if (require.main === module) {
  const result = auditPackage(path.resolve(process.argv[2] || ''));
  console.log(`ASAR audit passed: ${result.files.length} current-build files, no credentials, local configuration, test fixtures, model binaries or production node_modules.`);
}
