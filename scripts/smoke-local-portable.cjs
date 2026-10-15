const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { AccountStore } = require('../dist-electron/auth-service.js');
const { auditPackage, hash } = require('./audit-local-package.cjs');
const directory = path.resolve(process.argv[2] || '');
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'echoverse-local-portable-'));
const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
let child;
let exited = false;

(async () => {
  const audit = auditPackage(directory);
  const manifest = JSON.parse(fs.readFileSync(path.join(directory, 'acceptance-manifest.json'), 'utf8'));
  assert.equal(audit.asarSha256, manifest.asarSha256);
  const exe = path.join(directory, manifest.artifact.file);
  assert.equal(path.dirname(exe), directory);
  assert.equal(hash(fs.readFileSync(exe)), manifest.artifact.sha256);
  const store = new AccountStore(path.join(temporary, 'accounts.json'));
  await store.register({ displayName: '便携启动测试', email: 'portable-test@example.local', password: 'IsolatedPortable2026!' });
  // A guaranteed-missing target prevents any UE/service startup, even if the
  // developer has game-related environment variables in the calling shell.
  const disabledGame = path.join(temporary, 'game-disabled.exe');
  assert.equal(fs.existsSync(disabledGame), false);
  fs.writeFileSync(path.join(temporary, 'game.json'), JSON.stringify({ contractVersion: '1.0', executablePath: disabledGame, services: [] }));
  const resultPath = path.join(temporary, 'result.json');
  const env = { ...process.env, ECHO_SMOKE_AUTOLAUNCH: '1', ECHO_USER_DATA_DIR: temporary, ECHO_SMOKE_EMAIL: 'portable-test@example.local', ECHO_SMOKE_PASSWORD: 'IsolatedPortable2026!', ECHO_SMOKE_RESULT_PATH: resultPath, ECHO_SMOKE_AUTOQUIT_MS: '5000', ECHOVERSE_OPENAI_API_KEY: '' };
  delete env.ELECTRON_RUN_AS_NODE; delete env.ECHO_GAME_CONFIG; delete env.GAME_EXECUTABLE_PATH;
  child = spawn(exe, [], { cwd: directory, env, stdio: 'ignore', windowsHide: true });
  child.once('exit', () => { exited = true; });
  let spawnError;
  child.once('error', (error) => { spawnError = error; });
  const deadline = Date.now() + 60_000;
  while (!fs.existsSync(resultPath) && Date.now() < deadline && !exited && !spawnError) await delay(200);
  if (spawnError) throw spawnError;
  assert.ok(fs.existsSync(resultPath), 'Portable extraction/startup did not reach the isolated application.');
  const result = JSON.parse(fs.readFileSync(resultPath, 'utf8'));
  assert.equal(result.ok, false, 'A game launch must never succeed in this representative-only test.');
  assert.match(result.message, /不存在|未配置|尚未配置/);
  const records = fs.readFileSync(path.join(temporary, 'logs/main.log'), 'utf8').trim().split('\n').map((line) => JSON.parse(line));
  assert.ok(records.some((record) => record.event === 'app.ready' && record.details.packaged === true && record.details.version === manifest.version));
  const exitDeadline = Date.now() + 30_000;
  while (!exited && Date.now() < exitDeadline) await delay(200);
  assert.ok(exited, 'Portable wrapper did not exit cleanly.');
  assert.equal(child.exitCode, 0);
  const afterExit = fs.readFileSync(path.join(temporary, 'logs/main.log'), 'utf8');
  assert.ok(afterExit.includes('app.before_quit'));
  fs.writeFileSync(path.join(directory, 'portable-smoke.json'), `${JSON.stringify({ passed: true, createdAt: new Date().toISOString(), sha256: manifest.artifact.sha256,
    scope: 'Actual portable EXE extraction, isolated packaged boot and clean exit. Game target deliberately absent; no model requests, real user data or game-runtime acceptance.' }, null, 2)}\n`);
  console.log('Portable smoke passed: verified EXE hash, isolated packaged boot, disabled game target and clean wrapper exit. No model calls or real account changes.');
})().catch((error) => { console.error(error); process.exitCode = 1; }).finally(() => {
  if (child && !exited) child.kill();
  assert.equal(path.dirname(temporary), os.tmpdir());
  assert.ok(path.basename(temporary).startsWith('echoverse-local-portable-'));
  if (!child || exited) fs.rmSync(temporary, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
  else console.warn('Test startup did not finish; its isolated temporary directory was preserved for diagnosis.');
});
