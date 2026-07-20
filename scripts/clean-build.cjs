const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const allowedDirectories = new Set(['dist', 'dist-electron']);

function removeBuildOutput(target) {
  fs.rmSync(target, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
  if (!fs.existsSync(target)) return;

  // Some Windows filesystem filters allow renaming a generated directory but
  // delay deletion inside Desktop. Move only the verified build directory to
  // a same-volume temporary location, then remove it there.
  const temporaryRoot = path.join(path.parse(root).root, 'tmp');
  fs.mkdirSync(temporaryRoot, { recursive: true });
  const temporaryTarget = path.join(
    temporaryRoot,
    `echoverse-${path.basename(target)}-${process.pid}-${Date.now()}`,
  );
  if (fs.existsSync(temporaryTarget)) throw new Error(`Temporary clean path already exists: ${temporaryTarget}`);
  fs.renameSync(target, temporaryTarget);
  fs.rmSync(temporaryTarget, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
  if (fs.existsSync(temporaryTarget)) throw new Error(`Temporary build output could not be cleaned: ${temporaryTarget}`);
}

for (const name of allowedDirectories) {
  const target = path.resolve(root, name);
  if (path.dirname(target) !== root || !allowedDirectories.has(path.basename(target))) {
    throw new Error(`Refusing to clean unexpected path: ${target}`);
  }
  removeBuildOutput(target);
  if (fs.existsSync(target)) throw new Error(`Build output could not be cleaned: ${target}`);
}

console.log('Build output cleaned.');
