import { app, BrowserWindow, ipcMain, IpcMainEvent, IpcMainInvokeEvent, screen, session } from 'electron';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
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

// Keep local prototype data stable between `electron .` development runs and
// packaged builds whose productName is different from the npm package name.
app.setPath('userData', path.join(app.getPath('appData'), 'echoverse-launcher'));
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
};

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
      const validArgs = parsed.additionalArgs === undefined
        || (Array.isArray(parsed.additionalArgs) && parsed.additionalArgs.every((value) => typeof value === 'string'));
      if (parsed.contractVersion === '1.0' && typeof parsed.executablePath === 'string' && validArgs) return parsed;
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

ipcMain.handle('game:launch', (event) => {
  assertTrustedSender(event);
  if (!currentUser) {
    return { ok: false, message: '当前账户会话无效，请重新登录。' };
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

  const { launchId, sessionPath } = writeLaunchSession(currentUser, config);
  try {
    const args = [
      `-LauncherSessionFile=${sessionPath}`,
      `-LauncherContractVersion=${config.contractVersion}`,
      `-LauncherLaunchId=${launchId}`,
      ...(config.additionalArgs ?? []),
    ];
    const child = spawn(config.executablePath, args, {
      cwd: config.workingDirectory || path.dirname(config.executablePath),
      detached: true,
      stdio: 'ignore',
      windowsHide: true,
    });
    child.once('error', (error) => {
      logError('game.launch_failed', error, { channel: config.channel || 'development' });
      removeSessionFile(sessionPath);
    });
    child.once('exit', (code, signal) => {
      logEvent('info', 'game.exited', { code, signal });
      removeSessionFile(sessionPath);
    });
    child.unref();
    logEvent('info', 'game.launched', { launchId, channel: config.channel || 'development' });
    return { ok: true, message: '游戏已启动。' };
  } catch (error) {
    logError('game.launch_failed', error, { channel: config.channel || 'development' });
    removeSessionFile(sessionPath);
    return { ok: false, message: '游戏启动失败，请稍后重试。' };
  }
});
