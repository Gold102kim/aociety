const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');

const defaultRoot = path.resolve(__dirname, '..');
// Only used by source ZIPs without Git metadata. A Git checkout is scanned from
// its actual publication candidates, including force-tracked ignored files.
const fallbackExcludedDirectories = new Set([
  '.git', '.pnpm-store', 'node_modules', 'runtime', 'dist', 'dist-electron',
  'release', '.vite', '.doc_review', '.agents', '.codex', '.vs', '.idea',
  '.vscode', '__pycache__', '.pytest_cache', 'Binaries', 'DerivedDataCache',
  'Intermediate', 'Saved', 'backups', 'build_temp', 'artifacts', 'models',
  'data', 'logs', 'recordings', 'uploads', 'user_data',
]);
const MAX_TEXT_BYTES = 16 * 1024 * 1024;
const textExtensions = new Set(['.cjs', '.mjs', '.js', '.ts', '.tsx', '.py', '.ps1', '.bat', '.cmd', '.sh', '.ini', '.env', '.json', '.jsonl', '.toml', '.yaml', '.yml', '.xml', '.config', '.conf', '.properties', '.md', '.txt', '.csv', '.sql', '.pem', '.key']);
const secretPatterns = [
  { label: 'API key', expression: /\bsk-[A-Za-z0-9_-]{24,}\b/g },
  { label: 'GitHub token', expression: /\b(?:gh[opusr]|github_pat)_[A-Za-z0-9_]{20,}\b/g },
  { label: 'Google API key', expression: /\bAIza[A-Za-z0-9_-]{30,}\b/g },
  { label: 'Google account credential', expression: /\bAQ\.[A-Za-z0-9_-]{30,}\b/g },
  { label: 'AWS access key', expression: /\b(?:AKIA|ASIA)[A-Z0-9]{16}\b/g },
  { label: 'npm token', expression: /\bnpm_[A-Za-z0-9]{20,}\b/g },
  { label: 'Slack token', expression: /\bxox[baprs]-[A-Za-z0-9-]{10,}\b/g },
  { label: 'private key', expression: /-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY(?: BLOCK)?-----/g },
];
const personalPath = /\b[A-Za-z]:[\\/]+Users[\\/]+[^\\/\r\n"'<>]+/i;

function sensitiveFileReason(relativePath) {
  const name = path.posix.basename(relativePath.replaceAll('\\', '/')).toLowerCase();
  if (name === '.env' || (name.startsWith('.env.') && !/\.(?:example|sample|template)$/.test(name))) return 'local environment file';
  if (/^(?:auth|accounts|credentials|ai|device-auth)\.json(?:\..*)?$/.test(name) || name === 'cap_sid') return 'private account or credential store';
  if (/\.local\.json$/.test(name)) return 'local machine configuration';
  if (/\.(?:db|sqlite|sqlite3)(?:-(?:wal|shm))?$/.test(name)) return 'local database';
  if (/\.(?:p12|pfx)$/.test(name) || /^(?:id_rsa|id_ecdsa|id_ed25519)$/.test(name)) return 'private credential file';
  if (/\.(?:log|pid)$/.test(name)) return 'local runtime output';
  return null;
}

function isWithin(root, absolutePath) {
  const relativePath = path.relative(root, absolutePath);
  return relativePath !== '..' && !relativePath.startsWith(`..${path.sep}`) && !path.isAbsolute(relativePath);
}

function inspectCandidatePath(root, relativePath) {
  const absolutePath = path.resolve(root, relativePath);
  if (!isWithin(root, absolutePath)) return { reason: 'file outside repository boundary' };
  // lstat every ancestor, not just the leaf. Never dereference a directory or
  // file symlink/junction into another project or the user's private folders.
  const parts = path.relative(root, absolutePath).split(path.sep);
  let candidate = root;
  for (const part of parts) {
    candidate = path.join(candidate, part);
    let stat;
    try { stat = fs.lstatSync(candidate); } catch (error) {
      if (error.code === 'ENOENT') return { missing: true };
      return { reason: 'candidate cannot be inspected' };
    }
    if (stat.isSymbolicLink()) return { reason: 'symbolic link or junction requires manual review' };
  }
  try {
    if (!isWithin(root, fs.realpathSync(absolutePath))) return { reason: 'file outside repository boundary' };
    const stat = fs.lstatSync(absolutePath);
    return stat.isFile() ? { absolutePath, stat } : { missing: true };
  } catch { return { reason: 'candidate cannot be inspected' }; }
}

function gitCandidates(root) {
  if (!fs.existsSync(path.join(root, '.git'))) return null;
  const options = { cwd: root, encoding: 'utf8', maxBuffer: 32 * 1024 * 1024, windowsHide: true, stdio: ['ignore', 'pipe', 'ignore'] };
  try {
    const gitRoot = execFileSync('git', ['rev-parse', '--show-toplevel'], options).trim();
    const normalizeCase = (value) => process.platform === 'win32' ? value.toLowerCase() : value;
    if (normalizeCase(fs.realpathSync(gitRoot)) !== normalizeCase(root)) throw new Error('Repository boundary mismatch.');
    return [...new Set(execFileSync('git', ['ls-files', '--cached', '--others', '--exclude-standard', '-z', '--', '.'], options).split('\0').filter(Boolean))];
  } catch { throw new Error('Git publication candidates cannot be enumerated.'); }
}

function fallbackCandidates(root) {
  const candidates = [];
  function visit(directory) {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const relativePath = path.relative(root, path.join(directory, entry.name)).replaceAll('\\', '/');
      if (entry.isDirectory()) {
        if (!fallbackExcludedDirectories.has(entry.name)) visit(path.join(directory, entry.name));
      } else if (!sensitiveFileReason(relativePath) && !/\.(?:tmp|bak|py[cod])$/i.test(entry.name)) {
        // Directory symlinks are not traversed; retained candidates are rejected
        // by inspectCandidatePath rather than reading their target.
        candidates.push(relativePath);
      }
    }
  }
  visit(root);
  return candidates;
}

function readTextCandidate(absolutePath, stat) {
  const handle = fs.openSync(absolutePath, 'r');
  try {
    const head = Buffer.alloc(Math.min(stat.size, 8192));
    fs.readSync(handle, head, 0, head.length, 0);
    const utf16le = head[0] === 0xff && head[1] === 0xfe;
    const utf16be = head[0] === 0xfe && head[1] === 0xff;
    if (!utf16le && !utf16be && head.includes(0) && !textExtensions.has(path.extname(absolutePath).toLowerCase())) return { binary: true };
    if (stat.size > MAX_TEXT_BYTES) return { reason: 'text file exceeds automated review size limit' };
    const content = fs.readFileSync(handle);
    if (utf16be) {
      if (content.length % 2) return { reason: 'invalid UTF-16 text file' };
      content.swap16();
    }
    return { text: content.toString(utf16le || utf16be ? 'utf16le' : 'utf8') };
  } finally { fs.closeSync(handle); }
}

function safeReportedPath(relativePath) {
  let safe = relativePath;
  for (const pattern of secretPatterns) {
    pattern.expression.lastIndex = 0;
    safe = safe.replace(pattern.expression, '[REDACTED]');
  }
  return safe;
}

function scanRepository(rootInput = defaultRoot) {
  const root = fs.realpathSync(path.resolve(rootInput));
  const gitFiles = gitCandidates(root);
  const candidates = gitFiles ?? fallbackCandidates(root);
  const findings = [];
  let scannedTextFiles = 0;
  const addFinding = (file, reason) => findings.push({ file: safeReportedPath(file), reason });
  for (const candidate of candidates.sort()) {
    const file = candidate.replaceAll('\\', '/');
    const inspected = inspectCandidatePath(root, file);
    if (inspected.missing) continue;
    if (inspected.reason) { addFinding(file, inspected.reason); continue; }
    const privateReason = sensitiveFileReason(file);
    if (privateReason) addFinding(file, privateReason);
    let content;
    try { content = readTextCandidate(inspected.absolutePath, inspected.stat); }
    catch { addFinding(file, 'candidate cannot be read'); continue; }
    if (content.reason) { addFinding(file, content.reason); continue; }
    if (content.binary) continue;
    scannedTextFiles += 1;
    for (const pattern of secretPatterns) {
      pattern.expression.lastIndex = 0;
      if (pattern.expression.test(content.text)) addFinding(file, `possible ${pattern.label}`);
    }
    if (personalPath.test(content.text)) addFinding(file, 'developer-specific absolute user path');
  }
  return { mode: gitFiles ? 'Git publication candidates' : 'source ZIP fallback', scannedTextFiles, findings };
}

function run() {
  const result = scanRepository();
  if (result.findings.length) {
    console.error('Sensitive material check failed. Review these publication candidates:');
    for (const finding of result.findings) console.error(`${JSON.stringify(finding.file)}: ${finding.reason}`);
    process.exitCode = 1;
    return;
  }
  console.log(`Sensitive material checks passed (${result.mode}; ${result.scannedTextFiles} text files).`);
}

module.exports = { scanRepository };
if (require.main === module) {
  try { run(); } catch {
    // A filesystem/Git error may itself contain sensitive paths or values.
    console.error('Sensitive material check could not complete. Inspect repository access before publishing.');
    process.exitCode = 1;
  }
}
