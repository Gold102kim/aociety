const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const packageJson = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
const releaseDirectory = path.join(root, 'release');
const prefix = `EchoVerse-Launcher-${packageJson.version}-`;
const artifacts = fs.existsSync(releaseDirectory)
  ? fs.readdirSync(releaseDirectory).filter((name) => name.startsWith(prefix) && name.endsWith('.exe'))
  : [];

assert.equal(artifacts.length, 1, `Expected exactly one ${prefix}*.exe artifact, found ${artifacts.length}.`);
const artifactPath = path.join(releaseDirectory, artifacts[0]);
const digest = crypto.createHash('sha256').update(fs.readFileSync(artifactPath)).digest('hex').toUpperCase();
const checksumPath = `${artifactPath}.sha256`;
fs.writeFileSync(checksumPath, `${digest}  ${artifacts[0]}\n`, 'utf8');

console.log(`SHA-256 ${digest}  ${artifacts[0]}`);
