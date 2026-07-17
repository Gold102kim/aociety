const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const excludedDirectories = new Set(['.git', 'node_modules', 'dist', 'dist-electron', 'release', '.vite', '.doc_review']);
const scannedExtensions = new Set(['.cjs', '.cs', '.env', '.js', '.json', '.md', '.py', '.ts', '.tsx', '.txt', '.yaml', '.yml']);
const findings = [];
const secretPatterns = [
  { label: 'API key', expression: /\bsk-[A-Za-z0-9_-]{24,}\b/g },
  { label: 'GitHub token', expression: /\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b/g },
  { label: 'Google API key', expression: /\bAIza[A-Za-z0-9_-]{30,}\b/g },
  { label: 'private key', expression: /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/g },
];

function visit(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (entry.isDirectory() && excludedDirectories.has(entry.name)) continue;
    const absolutePath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      visit(absolutePath);
      continue;
    }
    if (!entry.isFile() || !scannedExtensions.has(path.extname(entry.name).toLowerCase())) continue;

    const relativePath = path.relative(root, absolutePath);
    const content = fs.readFileSync(absolutePath, 'utf8');
    for (const pattern of secretPatterns) {
      pattern.expression.lastIndex = 0;
      if (pattern.expression.test(content)) findings.push(`${relativePath}: possible ${pattern.label}`);
    }
    if (/\b[A-Za-z]:\\Users\\[^\\\r\n]+/i.test(content)) findings.push(`${relativePath}: developer-specific absolute user path`);
  }
}

visit(root);
assert.deepEqual(findings, [], `Sensitive material check failed:\n${findings.join('\n')}`);
assert.equal(fs.existsSync(path.join(root, 'config', 'ai.local.json')), false, 'config/ai.local.json must not exist in the project tree.');

console.log('Sensitive material checks passed.');
