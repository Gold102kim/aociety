const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const allowedDirectories = new Set(['dist', 'dist-electron']);

for (const name of allowedDirectories) {
  const target = path.resolve(root, name);
  if (path.dirname(target) !== root || !allowedDirectories.has(path.basename(target))) {
    throw new Error(`Refusing to clean unexpected path: ${target}`);
  }
  fs.rmSync(target, { recursive: true, force: true });
  if (fs.existsSync(target)) throw new Error(`Build output could not be cleaned: ${target}`);
}

console.log('Build output cleaned.');
