import { app, BrowserWindow, ipcMain, IpcMainInvokeEvent, screen } from 'electron';
import path from 'node:path';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import { randomUUID } from 'node:crypto';
import { AccountStore, BasicQuestionnaire, PublicUser } from './auth-service';
import { AiChatMessage, AiChatService } from './ai-service';

let mainWindow: BrowserWindow | null = null;
let companionWindow: BrowserWindow | null = null;
let accountStore: AccountStore | null = null;
let currentUser: PublicUser | null = null;
let aiChatService: AiChatService | null = null;
let isQuitting = false;

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
    path.join(process.cwd(), 'config', 'game.local.json'),
  ].filter((value): value is string => Boolean(value));

  for (const configPath of candidates) {
    if (!fs.existsSync(configPath)) continue;
    try {
      const parsed = JSON.parse(fs.readFileSync(configPath, 'utf8')) as GameConfig;
      if (parsed.contractVersion === '1.0' && parsed.executablePath) return parsed;
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

function assertTrustedSender(event: IpcMainInvokeEvent) {
  if (!mainWindow || event.sender !== mainWindow.webContents) throw new Error('不受信任的请求来源。');
}

function assertAppWindowSender(event: IpcMainInvokeEvent) {
  const trusted = event.sender === mainWindow?.webContents || event.sender === companionWindow?.webContents;
  if (!trusted) throw new Error('不受信任的请求来源。');
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
  const devUrl = process.env.VITE_DEV_SERVER_URL;
  if (devUrl) {
    const url = new URL(devUrl);
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
    },
  });
  companionWindow.setAlwaysOnTop(true, 'floating');
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
    },
  });

  const devUrl = process.env.VITE_DEV_SERVER_URL;
  if (devUrl) {
    void mainWindow.loadURL(devUrl);
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
  accountStore = new AccountStore(path.join(app.getPath('userData'), 'accounts.json'));
  aiChatService = new AiChatService(app.getPath('userData'), process.cwd());
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
});

ipcMain.on('window:minimize', () => mainWindow?.minimize());
ipcMain.on('window:toggle-maximize', () => {
  if (!mainWindow) return;
  if (mainWindow.isMaximized()) mainWindow.unmaximize();
  else mainWindow.maximize();
});
ipcMain.on('window:close', () => mainWindow?.close());
ipcMain.handle('window:enter-companion', (event) => {
  assertTrustedSender(event);
  return enterCompanionMode();
});
ipcMain.on('companion:restore', (event) => {
  if (event.sender !== companionWindow?.webContents) return;
  restoreMainWindow();
});
ipcMain.on('companion:quit', (event) => {
  if (event.sender !== companionWindow?.webContents) return;
  app.quit();
});
ipcMain.handle('companion:get-state', (event) => {
  assertAppWindowSender(event);
  return currentUser
    ? { displayName: currentUser.displayName, agentStatus: currentUser.aiAgent.status, favoriteColor: currentUser.basicQuestionnaire?.favoriteColor || '薄荷绿' }
    : { displayName: 'Echo', agentStatus: 'WAITING_FOR_PROFILE', favoriteColor: '薄荷绿' };
});

ipcMain.handle('app:get-version', () => app.getVersion());

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

ipcMain.handle('auth:complete-questionnaire', (event, input: BasicQuestionnaire) => {
  assertTrustedSender(event);
  if (!accountStore || !currentUser) return { ok: false, message: '当前账户会话无效，请重新登录。' };
  try {
    currentUser = accountStore.completeBasicQuestionnaire(currentUser.id, input);
    return { ok: true, user: currentUser };
  } catch (error) {
    return { ok: false, message: error instanceof Error ? error.message : '个人资料保存失败，请稍后重试。' };
  }
});

ipcMain.handle('auth:supplement-profile', (event, input: BasicQuestionnaire) => {
  assertTrustedSender(event);
  if (!accountStore || !currentUser) return { ok: false, message: '当前账户会话无效，请重新登录。' };
  try {
    currentUser = accountStore.supplementProfile(currentUser.id, input);
    return { ok: true, user: currentUser };
  } catch (error) {
    return { ok: false, message: error instanceof Error ? error.message : '资料补充失败，请稍后重试。' };
  }
});

ipcMain.handle('ai:get-status', (event) => {
  assertTrustedSender(event);
  return aiChatService?.getStatus() ?? { configured: false, model: 'gpt-5.6-luna', connection: 'unconfigured' };
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
    });
    child.once('error', () => removeSessionFile(sessionPath));
    child.once('exit', () => removeSessionFile(sessionPath));
    child.unref();
    return { ok: true, message: '游戏已启动。' };
  } catch {
    removeSessionFile(sessionPath);
    return { ok: false, message: '游戏启动失败，请稍后重试。' };
  }
});
