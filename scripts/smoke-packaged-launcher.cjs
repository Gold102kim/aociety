const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { AccountStore } = require('../dist-electron/auth-service.js');

const root = path.resolve(__dirname, '..');
const launcherPath = path.join(root, 'release', 'EchoVerse-Launcher-0.4.0-x64.exe');
const gameConfigPath = path.join(root, 'config', 'game.local.json');
const gameLogPath = path.join(root, 'ue5_project', 'Saved', 'Logs', 'Aociety.log');
const smokeRoot = path.join('C:\\tmp', `echoverse-packaged-smoke-${process.pid}-${Date.now()}`);
const resultPath = path.join(smokeRoot, 'result.json');
const email = 'packaged-smoke@echoverse.local';
const password = 'EchoVerseSmoke2026!';

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function waitUntil(check, timeoutMs, label) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const result = await check();
    if (result) return result;
    await delay(500);
  }
  throw new Error(`${label}超时。`);
}

async function main() {
  assert.ok(fs.existsSync(launcherPath), `缺少启动器：${launcherPath}`);
  assert.ok(fs.existsSync(gameConfigPath), '缺少 config/game.local.json。');
  fs.mkdirSync(smokeRoot, { recursive: true });
  fs.copyFileSync(gameConfigPath, path.join(smokeRoot, 'game.json'));

  const store = new AccountStore(path.join(smokeRoot, 'accounts.json'));
  const registered = await store.register({ displayName: '启动联调', email, password });
  await store.completeBasicQuestionnaire(registered.id, {
    fullName: '',
    gender: '',
    birthDate: '',
    residence: '',
    occupation: '联调测试',
    interests: ['游戏'],
    mbti: '',
    favoriteColor: '绿色',
    favoriteMusic: '',
    belief: '',
  });

  const launcher = spawn(launcherPath, [], {
    cwd: path.dirname(launcherPath),
    env: {
      ...process.env,
      ECHO_SMOKE_AUTOLAUNCH: '1',
      ECHO_USER_DATA_DIR: smokeRoot,
      ECHO_SMOKE_EMAIL: email,
      ECHO_SMOKE_PASSWORD: password,
      ECHO_SMOKE_RESULT_PATH: resultPath,
      ECHO_SMOKE_AUTOQUIT_MS: '20000',
    },
    stdio: 'ignore',
    windowsHide: false,
  });

  try {
    const result = await waitUntil(() => {
      if (!fs.existsSync(resultPath)) return null;
      return JSON.parse(fs.readFileSync(resultPath, 'utf8'));
    }, 90_000, '启动器启动游戏');
    assert.equal(result.ok, true, result.message);
    assert.ok(result.launchId, '启动器没有返回 launchId。');

    await waitUntil(() => {
      if (!fs.existsSync(gameLogPath)) return false;
      return fs.readFileSync(gameLogPath, 'utf8').includes(`Launcher session accepted: launch=${result.launchId}`);
    }, 120_000, 'UE 接收启动器会话');

    console.log(`Packaged launcher opened UE successfully: ${result.launchId}`);
  } finally {
    await new Promise((resolve) => {
      if (launcher.exitCode !== null) return resolve();
      const timeout = setTimeout(resolve, 30_000);
      launcher.once('exit', () => {
        clearTimeout(timeout);
        resolve();
      });
    });
    if (launcher.exitCode === null) launcher.kill();
    fs.rmSync(smokeRoot, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
