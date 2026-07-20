const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { randomUUID } = require('node:crypto');
const { spawn } = require('node:child_process');

const root = path.resolve(__dirname, '..');
const configPath = path.join(root, 'config', 'game.local.json');
const gameLogPath = path.join(root, 'ue5_project', 'Saved', 'Logs', 'Aociety.log');

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function healthReady(url) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 1_500);
  try {
    return (await fetch(url, { signal: controller.signal })).ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timeout);
  }
}

async function waitUntil(check, timeoutMs, label) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await check()) return;
    await delay(500);
  }
  throw new Error(`${label}超时。`);
}

async function main() {
  if (!fs.existsSync(configPath)) throw new Error('缺少 config/game.local.json，请先运行 pnpm configure:local-game。');
  const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
  const startedServices = [];
  let game = null;
  const launchId = randomUUID();
  const sessionPath = path.join(os.tmpdir(), `aociety-smoke-${launchId}.json`);
  const issuedAt = new Date();
  const session = {
    contractVersion: '1.0',
    launchId,
    issuedAt: issuedAt.toISOString(),
    expiresAt: new Date(issuedAt.getTime() + 5 * 60_000).toISOString(),
    launcher: { version: 'smoke-test', platform: 'win32', locale: 'zh-CN' },
    account: { accountId: 'smoke-account', displayName: 'Smoke Test' },
    agent: {
      agentId: randomUUID(),
      status: 'READY',
      profileVersion: 1,
      baseModelId: 'deepseek-v4-flash',
    },
    auth: { ticket: `prototype_${randomUUID()}`, ticketType: 'prototype-local', exchangeUrl: null },
    game: { channel: 'smoke-test' },
  };
  fs.writeFileSync(sessionPath, `${JSON.stringify(session, null, 2)}\n`, { encoding: 'utf8', mode: 0o600 });

  try {
    for (const service of config.services || []) {
      if (await healthReady(service.healthUrl)) continue;
      const child = spawn(service.executablePath, service.args || [], {
        cwd: service.workingDirectory,
        stdio: 'ignore',
        windowsHide: true,
      });
      startedServices.push(child);
      await waitUntil(() => healthReady(service.healthUrl), service.startupTimeoutMs || 30_000, `${service.name} 启动`);
    }

    const args = [
      ...(config.additionalArgs || []),
      `-LauncherSessionFile=${sessionPath}`,
      '-LauncherContractVersion=1.0',
      `-LauncherLaunchId=${launchId}`,
    ];
    game = spawn(config.executablePath, args, {
      cwd: config.workingDirectory,
      stdio: 'ignore',
      windowsHide: false,
    });
    await new Promise((resolve, reject) => {
      game.once('spawn', resolve);
      game.once('error', reject);
    });

    await waitUntil(() => {
      if (!fs.existsSync(gameLogPath)) return false;
      return fs.readFileSync(gameLogPath, 'utf8').includes(`Launcher session accepted: launch=${launchId}`);
    }, 120_000, 'UE 启动器会话验证');

    console.log(`UE launcher session accepted: ${launchId}`);
    console.log(`Resident health ready: ${(config.services || []).every((service) => fs.existsSync(service.executablePath))}`);
  } finally {
    if (game && game.exitCode === null) game.kill();
    for (const service of startedServices) {
      if (service.exitCode === null) service.kill();
    }
    fs.rmSync(sessionPath, { force: true });
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
