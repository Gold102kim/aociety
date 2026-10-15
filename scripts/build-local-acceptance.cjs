const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { auditPackage, hash } = require('./audit-local-package.cjs');
const root = path.resolve(__dirname, '..');

(async () => {
  assert.equal(process.platform, 'win32', 'This acceptance build targets Windows.');
  const stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d+Z$/, 'Z');
  const finalizeOnly = process.argv[2] === '--finalize';
  assert.ok(process.argv.length === 2 || (finalizeOnly && process.argv.length === 4), 'Use no arguments, or --finalize with an already-built local acceptance directory.');
  const directory = finalizeOnly ? path.resolve(process.argv[3]) : path.join(root, 'release', `representative-local-${stamp}`);
  assert.equal(path.dirname(directory), path.join(root, 'release'));
  assert.ok(path.basename(directory).startsWith('representative-local-'));
  if (!finalizeOnly) {
    assert.equal(fs.existsSync(directory), false, 'Refusing to overwrite an existing acceptance build.');
    const env = { ...process.env, CSC_IDENTITY_AUTO_DISCOVERY: 'false', CSC_LINK: '', CSC_KEY_PASSWORD: '', WIN_CSC_LINK: '', WIN_CSC_KEY_PASSWORD: '' };
    const exitCode = await new Promise((resolve, reject) => {
      const child = spawn(process.execPath, [require.resolve('electron-builder/cli.js'), '--win', 'portable', '--publish', 'never', '--config', 'build/representative-local.cjs', `--config.directories.output=${directory}`], { cwd: root, env, stdio: 'inherit', windowsHide: true });
      child.once('error', reject); child.once('exit', resolve);
    });
    assert.equal(exitCode, 0, 'Packaging failed; keep the partial output for diagnosis.');
  }
  const manifest = auditPackage(directory);
  const exe = `EchoVerse-Representative-local-${manifest.version}-x64.exe`;
  const bytes = fs.readFileSync(path.join(directory, exe));
  manifest.artifact = { file: exe, bytes: bytes.length, sha256: hash(bytes) };
  manifest.createdAt = new Date().toISOString();
  manifest.scope = 'Unsigned local desktop acceptance build; no UE game, restricted models or embedded model credentials. Runtime tests are recorded separately.';
  fs.writeFileSync(path.join(directory, `${exe}.sha256`), `${manifest.artifact.sha256}  ${exe}\n`, { flag: 'wx' });
  fs.writeFileSync(path.join(directory, 'acceptance-manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`, { flag: 'wx' });
  console.log(`Local acceptance build: ${path.relative(root, directory)}`);
  console.log(`ASAR audit passed (${manifest.files.length} current-build files). SHA-256 ${manifest.artifact.sha256}`);
})().catch((error) => { console.error(error); process.exitCode = 1; });
