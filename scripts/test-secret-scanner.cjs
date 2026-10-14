const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');

const scannerPath = path.join(__dirname, 'test-secrets.cjs');
const scannerSource = fs.readFileSync(scannerPath, 'utf8');
const temporaryRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'echoverse-secret-scanner-'));
// These fake values are assembled so the regression test itself is not a leak.
const fakeSecrets = {
  api: ['sk', 'a'.repeat(40)].join('-'),
  github: ['ghp', 'b'.repeat(40)].join('_'),
  githubApp: ['ghs', 'c'.repeat(40)].join('_'),
  githubFine: ['github_pat', 'd'.repeat(50)].join('_'),
  google: ['AI', 'za', 'e'.repeat(35)].join(''),
  googleAccount: ['AQ', 'f'.repeat(45)].join('.'),
  aws: ['AK', 'IA', 'A'.repeat(16)].join(''),
  npm: ['npm', 'g'.repeat(35)].join('_'),
  slack: ['xoxb', 'h'.repeat(30)].join('-'),
  privateKey: ['-----BEGIN', 'OPENSSH', 'PRIVATE KEY-----'].join(' '),
};
const forwardPersonalPath = ['C:', 'Users', 'DemoReviewer', 'secret.txt'].join('/');
const backwardPersonalPath = ['C:', 'Users', 'DemoReviewer', 'secret.txt'].join('\\');

function writeFixture(root, relativePath, content = '') {
  const absolutePath = path.join(root, relativePath);
  fs.mkdirSync(path.dirname(absolutePath), { recursive: true });
  fs.writeFileSync(absolutePath, content);
  return absolutePath;
}

function fixture(name, hasGit = true) {
  const root = path.join(temporaryRoot, name);
  fs.mkdirSync(root);
  if (hasGit) fs.mkdirSync(path.join(root, '.git'));
  return root;
}

function loadScanner({ candidates = [], failGit = false, onOpen = () => {} } = {}) {
  const module = { exports: {} };
  const fsProxy = Object.create(fs);
  fsProxy.openSync = (...args) => { onOpen(args[0]); return fs.openSync(...args); };
  // Model Git's index/nonignored enumeration at the process boundary. No git
  // init/add/commit or writes to the user's repository are performed by tests.
  const execFileSync = (command, args, options) => {
    assert.equal(command, 'git');
    if (failGit) throw new Error('Mock Git unavailable.');
    assert.equal(options.windowsHide, true);
    if (args[0] === 'rev-parse') return `${options.cwd}\n`;
    assert.deepEqual(Array.from(args), ['ls-files', '--cached', '--others', '--exclude-standard', '-z', '--', '.']);
    return `${candidates.join('\0')}\0`;
  };
  const context = {
    module, exports: module.exports, __dirname: path.dirname(scannerPath), Buffer, process, console,
    require: (name) => name === 'node:fs' ? fsProxy : name === 'node:child_process' ? { execFileSync } : require(name),
  };
  vm.runInNewContext(scannerSource, context, { filename: scannerPath });
  return module.exports.scanRepository;
}

function plain(result) { return JSON.parse(JSON.stringify(result)); }
function hasFinding(result, file, reason) {
  return result.findings.some((finding) => finding.file === file && finding.reason.includes(reason));
}
function assertNoSecretEcho(result) {
  const renderedReport = JSON.stringify(result);
  for (const secret of Object.values(fakeSecrets)) assert.ok(!renderedReport.includes(secret), 'The scanner report must never include a credential value.');
  assert.ok(!renderedReport.includes('DemoReviewer'), 'Only relative file paths and problem types belong in the report.');
}

try {
  {
    const root = fixture('ignored-local-files');
    writeFixture(root, 'README.md', 'Source-only prototype.');
    writeFixture(root, '.env.example', 'DEEPSEEK_API_KEY=your-key-here');
    writeFixture(root, '.env', `DEEPSEEK_API_KEY=${fakeSecrets.api}`);
    writeFixture(root, 'auth.json', JSON.stringify({ token: fakeSecrets.github }));
    writeFixture(root, 'accounts.json', JSON.stringify({ email: 'private@example.com' }));
    writeFixture(root, 'data/residents.db', fakeSecrets.api);
    writeFixture(root, 'config/ai.local.json', JSON.stringify({ apiKey: fakeSecrets.api }));
    const opened = [];
    const scan = loadScanner({ candidates: ['README.md', '.env.example'], onOpen: (file) => opened.push(path.relative(root, file)) });
    const result = plain(scan(root));
    assert.equal(result.mode, 'Git publication candidates');
    assert.deepEqual(result.findings, []);
    assert.deepEqual(opened.sort(), ['.env.example', 'README.md'].sort());
    assert.equal(fs.readFileSync(path.join(root, '.env'), 'utf8'), `DEEPSEEK_API_KEY=${fakeSecrets.api}`, 'The scanner must not modify local configuration.');
  }

  {
    const root = fixture('force-tracked-private-files');
    writeFixture(root, '.env', `DEEPSEEK_API_KEY=${fakeSecrets.api}`);
    writeFixture(root, 'auth.json', '{}');
    writeFixture(root, 'accounts.json', '{}');
    writeFixture(root, 'data/residents.sqlite3', Buffer.from([0, 1, 2]));
    writeFixture(root, 'config/ai.local.json', '{}');
    const scan = loadScanner({ candidates: ['.env', 'auth.json', 'accounts.json', 'data/residents.sqlite3', 'config/ai.local.json'] });
    const result = plain(scan(root));
    assert.ok(hasFinding(result, '.env', 'local environment'));
    assert.ok(hasFinding(result, '.env', 'API key'));
    assert.ok(hasFinding(result, 'auth.json', 'credential store'));
    assert.ok(hasFinding(result, 'accounts.json', 'account'));
    assert.ok(hasFinding(result, 'data/residents.sqlite3', 'local database'));
    assert.ok(hasFinding(result, 'config/ai.local.json', 'local machine configuration'));
    assertNoSecretEcho(result);
  }

  {
    const root = fixture('force-tracked-opaque-credentials');
    const files = ['ai.json', 'device-auth.json', 'cap_sid', 'config/custom.local.json'];
    for (const file of files) writeFixture(root, file, '{}');
    const result = plain(loadScanner({ candidates: files })(root));
    for (const file of files) assert.ok(hasFinding(result, file, file.endsWith('.local.json') ? 'local machine configuration' : 'credential store'));
    assertNoSecretEcho(result);
  }

  {
    const root = fixture('new-source-leaks');
    writeFixture(root, 'tools/setup.ps1', `$value = '${forwardPersonalPath}'\n${fakeSecrets.api}`);
    writeFixture(root, 'config/tool.ini', `[local]\npath=${backwardPersonalPath}\nkey=${fakeSecrets.github}`);
    writeFixture(root, 'config/escaped.json', JSON.stringify({ path: backwardPersonalPath }));
    const scan = loadScanner({ candidates: ['tools/setup.ps1', 'config/tool.ini', 'config/escaped.json', 'deleted-tracked.txt'] });
    const result = plain(scan(root));
    assert.ok(hasFinding(result, 'tools/setup.ps1', 'absolute user path'));
    assert.ok(hasFinding(result, 'tools/setup.ps1', 'API key'));
    assert.ok(hasFinding(result, 'config/tool.ini', 'absolute user path'));
    assert.ok(hasFinding(result, 'config/tool.ini', 'GitHub token'));
    assert.ok(hasFinding(result, 'config/escaped.json', 'absolute user path'));
    assert.ok(!result.findings.some((finding) => finding.file === 'deleted-tracked.txt'));
    assertNoSecretEcho(result);
  }

  {
    const root = fixture('credential-types');
    writeFixture(root, 'config/debug.txt', Object.values(fakeSecrets).join('\n'));
    const result = plain(loadScanner({ candidates: ['config/debug.txt'] })(root));
    for (const reason of ['API key', 'GitHub token', 'Google API key', 'Google account credential', 'AWS access key', 'npm token', 'Slack token', 'private key']) {
      assert.ok(hasFinding(result, 'config/debug.txt', reason), `Missing ${reason} detection.`);
    }
    assertNoSecretEcho(result);
  }

  {
    const root = fixture('utf16-source');
    writeFixture(root, 'tools/legacy.ps1', Buffer.concat([Buffer.from([0xff, 0xfe]), Buffer.from(fakeSecrets.api, 'utf16le')]));
    const result = plain(loadScanner({ candidates: ['tools/legacy.ps1'] })(root));
    assert.ok(hasFinding(result, 'tools/legacy.ps1', 'API key'), 'Windows UTF-16 PowerShell files must be scanned.');
  }

  {
    const root = fixture('symlink-boundary');
    const outside = fixture('outside-target', false);
    writeFixture(outside, 'secret.txt', fakeSecrets.api);
    fs.symlinkSync(outside, path.join(root, 'linked'), process.platform === 'win32' ? 'junction' : 'dir');
    const opened = [];
    const result = plain(loadScanner({ candidates: ['linked', 'linked/secret.txt'], onOpen: (file) => opened.push(file) })(root));
    assert.deepEqual(opened, [], 'Neither the linked directory nor a candidate below it may be dereferenced.');
    assert.equal(result.findings.length, 2);
    assert.ok(result.findings.every((finding) => finding.reason.includes('symbolic link or junction')));
    assertNoSecretEcho(result);
  }

  {
    const root = fixture('source-zip', false);
    writeFixture(root, 'src/main.ts', 'export const prototype = true;');
    writeFixture(root, '.env', fakeSecrets.api);
    writeFixture(root, 'auth.json', fakeSecrets.api);
    writeFixture(root, 'accounts.json', fakeSecrets.api);
    writeFixture(root, 'local.db', fakeSecrets.api);
    writeFixture(root, 'data/private.json', fakeSecrets.api);
    writeFixture(root, 'node_modules/fixture/index.js', fakeSecrets.api);
    writeFixture(root, 'release/fixture.txt', fakeSecrets.api);
    writeFixture(root, 'config/local.ini', forwardPersonalPath);
    fs.symlinkSync(path.join(temporaryRoot, 'outside-target'), path.join(root, 'linked'), process.platform === 'win32' ? 'junction' : 'dir');
    const opened = [];
    const result = plain(loadScanner({ failGit: true, onOpen: (file) => opened.push(path.relative(root, file).replaceAll('\\', '/')) })(root));
    assert.equal(result.mode, 'source ZIP fallback');
    assert.deepEqual(opened.sort(), ['config/local.ini', 'src/main.ts'].sort());
    assert.ok(hasFinding(result, 'config/local.ini', 'absolute user path'));
    assert.ok(hasFinding(result, 'linked', 'symbolic link or junction'));
    assertNoSecretEcho(result);
  }

  {
    const root = fixture('git-fail-closed');
    writeFixture(root, '.env', fakeSecrets.api);
    assert.throws(() => loadScanner({ failGit: true })(root), /Git publication candidates cannot be enumerated/, 'Git enumeration failure must not silently exclude tracked private files.');
  }

  {
    const root = fixture('sensitive-filename');
    const file = `${fakeSecrets.api}.txt`;
    writeFixture(root, file, fakeSecrets.api);
    const result = plain(loadScanner({ candidates: [file] })(root));
    assert.equal(result.findings[0].file, '[REDACTED].txt');
    assertNoSecretEcho(result);
  }

  console.log('Upload secret gate tests passed: Git candidates, tracked private files, ignored local data, paths, tokens, UTF-16, source ZIP fallback and symlink boundaries.');
} finally {
  // Only this freshly created test fixture tree is removed; local configs are
  // never included and symlink/junction removal does not follow their targets.
  const validated = fs.realpathSync(temporaryRoot);
  assert.ok(validated.startsWith(`${fs.realpathSync(os.tmpdir())}${path.sep}`));
  fs.rmSync(validated, { recursive: true, force: true });
}
