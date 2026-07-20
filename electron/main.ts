import { app, BrowserWindow, ipcMain, IpcMainEvent, IpcMainInvokeEvent, screen, session } from 'electron';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn, type ChildProcess } from 'node:child_process';
import fs from 'node:fs';
import { randomUUID } from 'node:crypto';
import { AccountStore, BasicQuestionnaire, PublicUser } from './auth-service';
import { AiChatMessage, AiChatService } from './ai-service';
import { initializeLogger, logError, logEvent } from './logger';

let mainWindow: BrowserWindow | null = null;
let companionWindow: BrowserWindow | null = null;
let accountStore: AccountStore | null = null;
let currentUser: PublicUser | null = null;
let aiChatService: AiChatService | null = null;
let isQuitting = false;
let activeGameProcess: ChildProcess | null = null;

type GameServiceConfig = {
  name: string;
  executablePath: string;
  workingDirectory?: string;
  args?: string[];
  healthUrl: string;
  startupTimeoutMs?: number;
};

// Keep local prototype data stable between `electron .` development runs and
// packaged builds whose productName is different from the npm package name.
// An explicit isolated directory is accepted only by the local smoke harness.
const smokeAutoLaunchEnabled = process.env.ECHO_SMOKE_AUTOLAUNCH === '1';
const requestedSmokeUserData = process.env.ECHO_USER_DATA_DIR;
if (smokeAutoLaunchEnabled && requestedSmokeUserData && path.isAbsolute(requestedSmokeUserData)) {
  app.setPath('userData', requestedSmokeUserData);
} else {
  app.setPath('userData', path.join(app.getPath('appData'), 'echoverse-launcher'));
}
initializeLogger(app.getPath('userData'));
process.on('uncaughtExceptionMonitor', (error) => logError('process.uncaught_exception', error));
process.on('unhandledRejection', (reason) => logError('process.unhandled_rejection', reason));

const hasSingleInstanceLock = app.requestSingleInstanceLock();
if (!hasSingleInstanceLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (app.isReady()) restoreMainWindow();
    else app.once('ready', restoreMainWindow);
  });
}

type GameConfig = {
  contractVersion: '1.0';
  executablePath: string;
  workingDirectory?: string;
  channel?: string;
  authExchangeUrl?: string;
  additionalArgs?: string[];
  services?: GameServiceConfig[];
};

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((entry) => typeof entry === 'string');
}

function isLocalHealthUrl(value: string) {
  try {
    const url = new URL(value);
    const localHost = url.hostname === '127.0.0.1' || url.hostname === 'localhost';
    return url.protocol === 'http:' && localHost && !url.username && !url.password;
  } catch {
    return false;
  }
}

function isGameServiceConfig(value: unknown): value is GameServiceConfig {
  if (!value || typeof value !== 'object') return false;
  const service = value as Partial<GameServiceConfig>;
  return typeof service.name === 'string'
    && typeof service.executablePath === 'string'
    && typeof service.healthUrl === 'string'
    && isLocalHealthUrl(service.healthUrl)
    && (service.args === undefined || isStringArray(service.args))
    && (service.workingDirectory === undefined || typeof service.workingDirectory === 'string')
    && (service.startupTimeoutMs === undefined
      || (Number.isFinite(service.startupTimeoutMs) && service.startupTimeoutMs >= 1_000 && service.startupTimeoutMs <= 120_000));
}

function readGameConfig(): GameConfig | null {
  const explicitPath = process.env.ECHO_GAME_CONFIG;
  const candidates = [
    explicitPath,
    path.join(app.getPath('userData'), 'game.json'),
    !app.isPackaged ? path.join(app.getAppPath(), 'config', 'game.local.json') : undefined,
  ].filter((value): value is string => Boolean(value));

  for (const configPath of candidates) {
    if (!fs.existsSync(configPath)) continue;
    try {
      const parsed = JSON.parse(fs.readFileSync(configPath, 'utf8')) as GameConfig;
      const validArgs = parsed.additionalArgs === undefined || isStringArray(parsed.additionalArgs);
      const validServices = parsed.services === undefined
        || (Array.isArray(parsed.services) && parsed.services.every(isGameServiceConfig));
      if (parsed.contractVersion === '1.0' && typeof parsed.executablePath === 'string' && validArgs && validServices) return parsed;
    } catch {
      // Continue to the next supported configuration location.
    }
  }

  if (process.env.GAME_EXECUTABLE_PATH) {
    return {
      contractVersion: '1.0',
      executablePath: process.env.GAME_EXECUTABLE_PATH,
      channel: 'development',
    };
  }
  return null;
}

async function isHealthReady(healthUrl: string) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 1_500);
  try {
    const response = await fetch(healthUrl, { method: 'GET', signal: controller.signal, cache: 'no-store' });
    return response.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timeout);
  }
}

async function waitForHealth(healthUrl: string, timeoutMs: number) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await isHealthReady(healthUrl)) return true;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  return false;
}

async function startGameServices(config: GameConfig) {
  const started: ChildProcess[] = [];
  try {
    for (const service of config.services ?? []) {
      if (await isHealthReady(service.healthUrl)) {
        logEvent('info', 'game.service_already_ready', { name: service.name, healthUrl: service.healthUrl });
        continue;
      }
      if (!fs.existsSync(service.executablePath)) throw new Error(`服务程序不存在：${service.name}`);
      if (service.workingDirectory && !fs.existsSync(service.workingDirectory)) throw new Error(`服务目录不存在：${service.name}`);

      const child = spawn(service.executablePath, service.args ?? [], {
        cwd: service.workingDirectory || path.dirname(service.executablePath),
        detached: false,
        stdio: 'ignore',
        windowsHide: true,
      });
      await new Promise<void>((resolve, reject) => {
        child.once('spawn', resolve);
        child.once('error', reject);
      });
      started.push(child);

      const ready = await waitForHealth(service.healthUrl, service.startupTimeoutMs ?? 30_000);
      if (!ready) throw new Error(`服务启动超时：${service.name}`);
      logEvent('info', 'game.service_started', { name: service.name, healthUrl: service.healthUrl });
    }
    return started;
  } catch (error) {
    stopGameServices(started);
    throw error;
  }
}

function stopGameServices(processes: ChildProcess[]) {
  for (const process of processes) {
    if (process.exitCode === null && !process.killed) process.kill();
  }
}

async function launchConfiguredGame(user: PublicUser) {
  if (activeGameProcess && activeGameProcess.exitCode === null && !activeGameProcess.killed) {
    return { ok: false, message: '游戏已经在运行。' };
  }

  const config = readGameConfig();
  if (!config) {
    return {
      ok: false,
      message: '尚未配置游戏。复制 config/game.example.json 为 config/game.local.json，并填写 UE5 程序路径。',
    };
  }

  if (!fs.existsSync(config.executablePath)) {
    return { ok: false, message: '配置的游戏程序不存在，请检查 executablePath。' };
  }

  let startedServices: ChildProcess[] = [];
  try {
    startedServices = await startGameServices(config);
  } catch (error) {
    stopGameServices(startedServices);
    logError('game.service_start_failed', error, { channel: config.channel || 'development' });
    return { ok: false, message: error instanceof Error ? error.message : '游戏服务启动失败。' };
  }

  const { launchId, sessionPath } = writeLaunchSession(user, config);
  try {
    const args = [
      ...(config.additionalArgs ?? []),
      `-LauncherSessionFile=${sessionPath}`,
      `-LauncherContractVersion=${config.contractVersion}`,
      `-LauncherLaunchId=${launchId}`,
    ];
    const child = spawn(config.executablePath, args, {
      cwd: config.workingDirectory || path.dirname(config.executablePath),
      detached: true,
      stdio: 'ignore',
      windowsHide: false,
    });
    await new Promise<void>((resolve, reject) => {
      child.once('spawn', resolve);
      child.once('error', reject);
    });
    activeGameProcess = child;
    child.once('exit', (code, signal) => {
      logEvent('info', 'game.exited', { code, signal });
      removeSessionFile(sessionPath);
      stopGameServices(startedServices);
      if (activeGameProcess === child) activeGameProcess = null;
    });
    child.unref();
    logEvent('info', 'game.launched', { launchId, channel: config.channel || 'development' });
    return { ok: true, message: '游戏已启动。', launchId };
  } catch (error) {
    logError('game.launch_failed', error, { channel: config.channel || 'development' });
    removeSessionFile(sessionPath);
    stopGameServices(startedServices);
    return { ok: false, message: '游戏启动失败，请稍后重试。' };
  }
}

async function runPackagedSmokeAutoLaunch() {
  if (!smokeAutoLaunchEnabled || !accountStore) return;
  const email = process.env.ECHO_SMOKE_EMAIL || '';
  const password = process.env.ECHO_SMOKE_PASSWORD || '';
  const resultPathValue = process.env.ECHO_SMOKE_RESULT_PATH || '';
  const userDataRoot = path.resolve(app.getPath('userData'));
  const resultPath = resultPathValue ? path.resolve(resultPathValue) : '';
  const resultPathAllowed = resultPath.startsWith(`${userDataRoot}${path.sep}`);

  try {
    currentUser = await accountStore.login(email, password);
    const result = await launchConfiguredGame(currentUser);
    if (resultPathAllowed) fs.writeFileSync(resultPath, `${JSON.stringify(result)}\n`, { encoding: 'utf8', mode: 0o600 });
    logEvent(result.ok ? 'info' : 'error', 'smoke.game_launch_result', { ok: result.ok, message: result.message });

    const autoQuitMs = Math.min(120_000, Math.max(5_000, Number(process.env.ECHO_SMOKE_AUTOQUIT_MS) || 45_000));
    setTimeout(() => {
      if (activeGameProcess && activeGameProcess.exitCode === null) activeGameProcess.kill();
      setTimeout(() => app.quit(), 1_500);
    }, autoQuitMs);
  } catch (error) {
    const result = { ok: false, message: error instanceof Error ? error.message : '冒烟测试登录失败。' };
    if (resultPathAllowed) fs.writeFileSync(resultPath, `${JSON.stringify(result)}\n`, { encoding: 'utf8', mode: 0o600 });
    logError('smoke.game_launch_failed', error);
    setTimeout(() => app.quit(), 1_000);
  }
}

function writeLaunchSession(user: PublicUser, config: GameConfig) {
  const launchId = randomUUID();
  const sessionDirectory = path.join(app.getPath('userData'), 'sessions');
  fs.mkdirSync(sessionDirectory, { recursive: true });
  const sessionPath = path.join(sessionDirectory, `${launchId}.json`);
  const issuedAt = new Date();
  const expiresAt = new Date(issuedAt.getTime() + 2 * 60 * 1000);

  const session = {
    contractVersion: '1.0',
    launchId,
    issuedAt: issuedAt.toISOString(),
    expiresAt: expiresAt.toISOString(),
    launcher: {
      version: app.getVersion(),
      platform: process.platform,
      locale: app.getLocale() || 'zh-CN',
    },
    account: {
      accountId: user.id,
      displayName: user.displayName,
    },
    agent: {
      agentId: user.aiAgent.agentId,
      status: user.aiAgent.status,
      profileVersion: user.aiAgent.profileVersion,
      baseModelId: user.aiAgent.modelAssignment.baseModelId,
    },
    auth: {
      ticket: `prototype_${randomUUID()}`,
      ticketType: 'prototype-local',
      exchangeUrl: config.authExchangeUrl || null,
    },
    game: {
      channel: config.channel || 'development',
    },
  };

  fs.writeFileSync(sessionPath, JSON.stringify(session, null, 2), { encoding: 'utf8', mode: 0o600 });
  return { launchId, sessionPath };
}

function removeSessionFile(sessionPath: string) {
  try {
    fs.rmSync(sessionPath, { force: true });
  } catch {
    // Session files expire quickly; failure to remove is non-fatal.
  }
}

function cleanupExpiredSessionFiles() {
  const directory = path.join(app.getPath('userData'), 'sessions');
  if (!fs.existsSync(directory)) return;
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (!entry.isFile() || !entry.name.endsWith('.json')) continue;
    const sessionPath = path.join(directory, entry.name);
    try {
      const value = JSON.parse(fs.readFileSync(sessionPath, 'utf8')) as { expiresAt?: string };
      const expiresAt = value.expiresAt ? new Date(value.expiresAt).getTime() : Number.NaN;
      if (!Number.isFinite(expiresAt) || expiresAt <= Date.now()) removeSessionFile(sessionPath);
    } catch {
      removeSessionFile(sessionPath);
    }
  }
}

function getDevServerUrl() {
  const value = process.env.VITE_DEV_SERVER_URL;
  if (!value) return null;
  const url = new URL(value);
  const localHost = url.hostname === '127.0.0.1' || url.hostname === 'localhost';
  if (url.protocol !== 'http:' || !localHost) throw new Error('开发服务器只允许使用本机 HTTP 地址。');
  return url;
}

function isTrustedRendererUrl(value: string) {
  try {
    const url = new URL(value);
    const devUrl = getDevServerUrl();
    if (devUrl) return url.origin === devUrl.origin;
    if (url.protocol !== 'file:') return false;
    const expected = path.resolve(__dirname, '..', 'dist', 'index.html');
    return path.resolve(fileURLToPath(url)) === expected;
  } catch {
    return false;
  }
}

function assertTrustedSender(event: IpcMainInvokeEvent) {
  const frame = event.senderFrame;
  const trustedFrame = frame && frame === event.sender.mainFrame && isTrustedRendererUrl(frame.url);
  if (!mainWindow || event.sender !== mainWindow.webContents || !trustedFrame) throw new Error('不受信任的请求来源。');
}

function assertAppWindowSender(event: IpcMainInvokeEvent) {
  const trusted = event.sender === mainWindow?.webContents || event.sender === companionWindow?.webContents;
  const frame = event.senderFrame;
  if (!trusted || !frame || frame !== event.sender.mainFrame || !isTrustedRendererUrl(frame.url)) throw new Error('不受信任的请求来源。');
}

function assertWindowEvent(event: IpcMainEvent, expectedWindow: BrowserWindow | null) {
  const frame = event.senderFrame;
  if (!expectedWindow || event.sender !== expectedWindow.webContents || !frame || frame !== event.sender.mainFrame || !isTrustedRendererUrl(frame.url)) {
    throw new Error('不受信任的请求来源。');
  }
}

function configureWindowSecurity(window: BrowserWindow, role: 'main' | 'companion') {
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  window.webContents.on('will-navigate', (event, targetUrl) => {
    if (!isTrustedRendererUrl(targetUrl)) event.preventDefault();
  });
  window.webContents.on('will-attach-webview', (event) => event.preventDefault());
  window.webContents.on('render-process-gone', (_event, details) => {
    logEvent('error', 'renderer.process_gone', { role, reason: details.reason, exitCode: details.exitCode });
  });
  window.webContents.on('did-fail-load', (_event, errorCode, errorDescription, _validatedUrl, isMainFrame) => {
    if (isMainFrame) logEvent('error', 'renderer.load_failed', { role, errorCode, errorDescription });
  });
}

function companionPosition(width: number, height: number) {
  const referenceBounds = mainWindow?.getBounds();
  const display = referenceBounds
    ? screen.getDisplayMatching(referenceBounds)
    : screen.getPrimaryDisplay();
  const margin = 18;
  return {
    x: Math.round(display.workArea.x + display.workArea.width - width - margin),
    y: Math.round(display.workArea.y + display.workArea.height - height),
  };
}

function loadCompanionPage(window: BrowserWindow) {
  const devUrl = getDevServerUrl();
  if (devUrl) {
    const url = new URL(devUrl.toString());
    url.searchParams.set('mode', 'companion');
    void window.loadURL(url.toString());
  } else {
    void window.loadFile(path.join(__dirname, '..', 'dist', 'index.html'), { query: { mode: 'companion' } });
  }
}

function createCompanionWindow() {
  if (companionWindow && !companionWindow.isDestroyed()) return companionWindow;
  const width = 300;
  const height = 360;
  const position = companionPosition(width, height);
  companionWindow = new BrowserWindow({
    width,
    height,
    x: position.x,
    y: position.y,
    minWidth: width,
    minHeight: height,
    maxWidth: width,
    maxHeight: height,
    frame: false,
    transparent: true,
    backgroundColor: '#00000000',
    alwaysOnTop: true,
    resizable: false,
    skipTaskbar: true,
    hasShadow: false,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      devTools: !app.isPackaged,
    },
  });
  companionWindow.setAlwaysOnTop(true, 'floating');
  configureWindowSecurity(companionWindow, 'companion');
  loadCompanionPage(companionWindow);
  companionWindow.on('closed', () => {
    companionWindow = null;
    if (!isQuitting && mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.show();
      mainWindow.focus();
    }
  });
  return companionWindow;
}

function enterCompanionMode() {
  if (!currentUser) return { ok: false, message: '请先登录账户再进入伴生模式。' };
  const companion = createCompanionWindow();
  const showCompanion = () => {
    mainWindow?.hide();
    companion.show();
    companion.focus();
  };
  if (companion.webContents.isLoading()) companion.once('ready-to-show', showCompanion);
  else showCompanion();
  return { ok: true };
}

function restoreMainWindow() {
  companionWindow?.hide();
  if (!mainWindow || mainWindow.isDestroyed()) createWindow();
  mainWindow?.show();
  mainWindow?.focus();
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1120,
    minHeight: 720,
    frame: false,
    backgroundColor: '#080a10',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      devTools: !app.isPackaged,
    },
  });

  configureWindowSecurity(mainWindow, 'main');
  const devUrl = getDevServerUrl();
  if (devUrl) {
    void mainWindow.loadURL(devUrl.toString());
  } else {
    void mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  }

  mainWindow.once('ready-to-show', () => mainWindow?.show());
  mainWindow.on('closed', () => {
    mainWindow = null;
    if (companionWindow && !companionWindow.isDestroyed()) companionWindow.close();
  });
}

app.whenReady().then(() => {
  if (!hasSingleInstanceLock) return;
  session.defaultSession.setPermissionRequestHandler((_webContents, _permission, callback) => callback(false));
  cleanupExpiredSessionFiles();
  accountStore = new AccountStore(path.join(app.getPath('userData'), 'accounts.json'));
  aiChatService = new AiChatService(app.getPath('userData'), app.isPackaged ? path.dirname(process.execPath) : app.getAppPath());
  logEvent('info', 'app.ready', { version: app.getVersion(), packaged: app.isPackaged, platform: process.platform });
  createWindow();
  void runPackagedSmokeAutoLaunch();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
app.on('before-quit', () => {
  isQuitting = true;
  logEvent('info', 'app.before_quit');
});
app.on('child-process-gone', (_event, details) => {
  logEvent('warn', 'app.child_process_gone', { type: details.type, reason: details.reason, exitCode: details.exitCode });
});

ipcMain.on('window:minimize', (event) => {
  assertWindowEvent(event, mainWindow);
  mainWindow?.minimize();
});
ipcMain.on('window:toggle-maximize', (event) => {
  assertWindowEvent(event, mainWindow);
  if (!mainWindow) return;
  if (mainWindow.isMaximized()) mainWindow.unmaximize();
  else mainWindow.maximize();
});
ipcMain.on('window:close', (event) => {
  assertWindowEvent(event, mainWindow);
  mainWindow?.close();
});
ipcMain.handle('window:enter-companion', (event) => {
  assertTrustedSender(event);
  return enterCompanionMode();
});
ipcMain.on('companion:restore', (event) => {
  assertWindowEvent(event, companionWindow);
  restoreMainWindow();
});
ipcMain.on('companion:quit', (event) => {
  assertWindowEvent(event, companionWindow);
  app.quit();
});
ipcMain.handle('companion:get-state', (event) => {
  assertAppWindowSender(event);
  return currentUser
    ? { displayName: currentUser.displayName, agentStatus: currentUser.aiAgent.status, favoriteColor: currentUser.basicQuestionnaire?.favoriteColor || '薄荷绿' }
    : { displayName: 'Echo', agentStatus: 'WAITING_FOR_PROFILE', favoriteColor: '薄荷绿' };
});

ipcMain.handle('app:get-version', (event) => {
  assertAppWindowSender(event);
  return app.getVersion();
});

ipcMain.handle('auth:register', async (event, input: { displayName: string; email: string; password: string }) => {
  assertTrustedSender(event);
  if (!accountStore) return { ok: false, message: '账户服务尚未准备完成。' };
  try {
    currentUser = await accountStore.register(input);
    return { ok: true, user: currentUser };
  } catch (error) {
    return { ok: false, message: error instanceof Error ? error.message : '注册失败，请稍后重试。' };
  }
});

ipcMain.handle('auth:login', async (event, input: { email: string; password: string }) => {
  assertTrustedSender(event);
  if (!accountStore) return { ok: false, message: '账户服务尚未准备完成。' };
  try {
    currentUser = await accountStore.login(input.email, input.password);
    return { ok: true, user: currentUser };
  } catch (error) {
    return { ok: false, message: error instanceof Error ? error.message : '登录失败，请稍后重试。' };
  }
});

ipcMain.handle('auth:logout', (event) => {
  assertTrustedSender(event);
  currentUser = null;
  return { ok: true };
});

ipcMain.handle('auth:complete-questionnaire', async (event, input: BasicQuestionnaire) => {
  assertTrustedSender(event);
  if (!accountStore || !currentUser) return { ok: false, message: '当前账户会话无效，请重新登录。' };
  try {
    currentUser = await accountStore.completeBasicQuestionnaire(currentUser.id, input);
    return { ok: true, user: currentUser };
  } catch (error) {
    return { ok: false, message: error instanceof Error ? error.message : '个人资料保存失败，请稍后重试。' };
  }
});

ipcMain.handle('auth:supplement-profile', async (event, input: BasicQuestionnaire) => {
  assertTrustedSender(event);
  if (!accountStore || !currentUser) return { ok: false, message: '当前账户会话无效，请重新登录。' };
  try {
    currentUser = await accountStore.supplementProfile(currentUser.id, input);
    return { ok: true, user: currentUser };
  } catch (error) {
    return { ok: false, message: error instanceof Error ? error.message : '资料补充失败，请稍后重试。' };
  }
});

ipcMain.handle('ai:get-status', (event) => {
  assertTrustedSender(event);
  return aiChatService?.getStatus() ?? { configured: false, model: 'deepseek-v4-flash', connection: 'unconfigured' };
});

ipcMain.handle('ai:chat', async (event, input: { message: string; history: AiChatMessage[] }) => {
  assertTrustedSender(event);
  if (!currentUser || !aiChatService) return { ok: false, message: '当前账户会话或 AI 服务无效，请重新登录。' };
  try {
    const result = await aiChatService.chat(currentUser, input?.message, input?.history);
    return { ok: true, ...result };
  } catch (error) {
    return { ok: false, message: error instanceof Error ? error.message : 'AI 回复生成失败，请稍后重试。' };
  }
});

ipcMain.handle('game:launch', async (event) => {
  assertTrustedSender(event);
  if (!currentUser) {
    return { ok: false, message: '当前账户会话无效，请重新登录。' };
  }
  return launchConfiguredGame(currentUser);
});
