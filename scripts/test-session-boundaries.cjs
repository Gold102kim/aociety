const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { EventEmitter } = require('node:events');
const { stripTypeScriptTypes } = require('node:module');
const { RequestEpoch } = require('../dist-electron/request-epoch.js');

const root = path.resolve(__dirname, '..');
const source = (file) => fs.readFileSync(path.join(root, file), 'utf8');
const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((accept, fail) => { resolve = accept; reject = fail; });
  return { promise, resolve, reject };
};
const user = (id) => ({ id, displayName: `Mock ${id}`, aiAgent: { status: 'READY' } });

function mainHarness() {
  const main = source('electron/main.ts');
  const handlers = new Map();
  const context = {
    RequestEpoch,
    sessionEpoch: new RequestEpoch(),
    currentUser: null,
    companionWindow: null,
    assertTrustedSender() {},
    assertAppWindowSender() {},
    aiChatService: { cancelCount: 0, cancelAll() { this.cancelCount += 1; }, getStatus() { return {}; } },
    ipcMain: { handle: (name, handler) => handlers.set(name, handler) },
    accountStore: {},
    launchConfiguredGame: async () => ({ ok: true }),
  };
  vm.createContext(context);
  const helpers = main.slice(main.indexOf('function discardCompanionWindow()'), main.indexOf('function createWindow()'));
  const handlersSource = main.slice(main.indexOf("ipcMain.handle('companion:get-state'"));
  vm.runInContext(stripTypeScriptTypes(`${helpers}\n${handlersSource}`), context);
  return { context, invoke: (name, input) => handlers.get(name)({}, input) };
}

async function testMainSessionBoundaries() {
  for (const operation of ['login', 'register']) {
    const { context, invoke } = mainHarness();
    const request = deferred();
    context.accountStore[operation] = () => request.promise;
    const pending = invoke(`auth:${operation}`, { email: 'mock@example.com', password: 'MockOnly123!' });
    await invoke('auth:logout');
    request.resolve(user('old'));
    assert.equal((await pending).ok, false, `${operation} must not revive a logged-out account.`);
    assert.equal(context.currentUser, null);
    assert.equal(context.aiChatService.cancelCount, 2);
  }

  {
    const { context, invoke } = mainHarness();
    const oldRequest = deferred();
    const newRequest = deferred();
    context.accountStore.login = (email) => email === 'old@example.com' ? oldRequest.promise : newRequest.promise;
    const oldLogin = invoke('auth:login', { email: 'old@example.com', password: 'MockOnly123!' });
    const newLogin = invoke('auth:login', { email: 'new@example.com', password: 'MockOnly123!' });
    newRequest.resolve(user('new'));
    assert.equal((await newLogin).ok, true);
    oldRequest.resolve(user('old'));
    assert.equal((await oldLogin).ok, false, 'An older login must not replace the newer account.');
    assert.equal(context.currentUser.id, 'new');
  }

  for (const [channel, method] of [
    ['auth:complete-questionnaire', 'completeBasicQuestionnaire'],
    ['auth:supplement-profile', 'supplementProfile'],
  ]) {
    const { context, invoke } = mainHarness();
    const request = deferred();
    context.currentUser = user('old');
    context.accountStore[method] = () => request.promise;
    context.accountStore.login = async () => user('new');
    const pending = invoke(channel, {});
    await invoke('auth:logout');
    assert.equal((await invoke('auth:login', { email: 'new@example.com', password: 'MockOnly123!' })).ok, true);
    request.resolve(user('old'));
    assert.equal((await pending).ok, false, `${channel} must reject an expired account result.`);
    assert.equal(context.currentUser.id, 'new');
  }

  {
    const { context, invoke } = mainHarness();
    const request = deferred();
    context.currentUser = user('old');
    context.aiChatService.chat = () => request.promise;
    const pending = invoke('ai:chat', { message: 'mock message', history: [] });
    await invoke('auth:logout');
    request.resolve({ text: 'private old account reply' });
    assert.equal((await pending).ok, false, 'A reply from an expired account must not reach the next session.');
  }

  {
    const { context, invoke } = mainHarness();
    const request = deferred();
    context.currentUser = user('old');
    context.aiChatService.chat = () => request.promise;
    const pending = invoke('ai:chat', { message: 'mock message', history: [] });
    await invoke('auth:logout');
    request.reject(new Error('A private error from the previous account'));
    assert.match((await pending).message, /账户会话已改变/, 'Expired requests must not return their old private error.');
  }

  {
    const { context, invoke } = mainHarness();
    let destroyed = 0;
    const oldWindow = () => ({ isDestroyed: () => false, destroy: () => { destroyed += 1; } });
    context.currentUser = user('old');
    context.companionWindow = oldWindow();
    await invoke('auth:logout');
    assert.equal(destroyed, 1, 'Logout must destroy the companion renderer holding the old identity.');
    assert.equal(context.companionWindow, null);
    context.companionWindow = oldWindow();
    context.accountStore.login = async () => user('new');
    await invoke('auth:login', { email: 'mock@example.com', password: 'MockOnly123!' });
    assert.equal(destroyed, 2, 'Authentication must invalidate any cached companion identity.');
    assert.equal(invoke('companion:get-state').displayName, 'Mock new');
    context.companionWindow = oldWindow();
    context.accountStore.supplementProfile = async () => user('new');
    assert.equal((await invoke('auth:supplement-profile', {})).ok, true);
    assert.equal(destroyed, 3, 'Profile changes must refresh cached companion preferences.');
  }
}

function testOneWayIpcRejections() {
  const main = source('electron/main.ts');
  const handlers = new Map();
  const calls = { minimized: 0, toggled: 0, closed: 0, restored: 0, quit: 0, rejected: 0 };
  const frame = { url: 'file:///trusted/index.html' };
  const companionFrame = { url: 'file:///trusted/index.html' };
  const mainContents = { mainFrame: frame };
  const companionContents = { mainFrame: companionFrame };
  const context = {
    ipcMain: { on: (name, handler) => handlers.set(name, handler), handle() {} },
    mainWindow: {
      webContents: mainContents, minimize: () => { calls.minimized += 1; },
      isMaximized: () => false, maximize: () => { calls.toggled += 1; }, close: () => { calls.closed += 1; },
    },
    companionWindow: { webContents: companionContents },
    isTrustedRendererUrl: (url) => url === 'file:///trusted/index.html',
    logEvent: () => { calls.rejected += 1; },
    restoreMainWindow: () => { calls.restored += 1; },
    app: { quit: () => { calls.quit += 1; } },
  };
  vm.createContext(context);
  const guard = main.slice(main.indexOf('function isTrustedWindowEvent('), main.indexOf('function configureWindowSecurity('));
  const ipc = main.slice(main.indexOf("ipcMain.on('window:minimize'"), main.indexOf("ipcMain.handle('companion:get-state'"));
  vm.runInContext(stripTypeScriptTypes(`${guard}\n${ipc}`), context);
  for (const [channel, handler] of handlers) {
    const isCompanion = channel.startsWith('companion:');
    const expectedContents = isCompanion ? companionContents : mainContents;
    const expectedFrame = expectedContents.mainFrame;
    const invalidEvents = [
      { sender: isCompanion ? mainContents : companionContents, senderFrame: expectedFrame },
      { sender: expectedContents, senderFrame: { url: expectedFrame.url } },
      { sender: expectedContents, senderFrame: null },
    ];
    for (const event of invalidEvents) assert.doesNotThrow(() => handler(event), `${channel} must reject an invalid sender without crashing main.`);
    const goodUrl = expectedFrame.url;
    expectedFrame.url = 'https://untrusted.example';
    assert.doesNotThrow(() => handler({ sender: expectedContents, senderFrame: expectedFrame }));
    expectedFrame.url = goodUrl;
    assert.equal(calls.minimized + calls.toggled + calls.closed + calls.restored + calls.quit, 0);
  }
  assert.equal(calls.rejected, handlers.size * 4);
  for (const [channel, handler] of handlers) {
    const sender = channel.startsWith('companion:') ? companionContents : mainContents;
    handler({ sender, senderFrame: sender.mainFrame });
  }
  assert.equal(calls.minimized, 1);
  assert.equal(calls.toggled, 1);
  assert.equal(calls.closed, 1);
  assert.equal(calls.restored, 1);
  assert.equal(calls.quit, 1);
}

async function testInitialHealthProbeCleanup() {
  const main = source('electron/main.ts');
  let cancelled = 0;
  const context = {
    AbortController, setTimeout, clearTimeout,
    fetch: async () => ({ ok: true, body: { cancel: async () => { cancelled += 1; } } }),
  };
  vm.createContext(context);
  const probe = main.slice(main.indexOf('async function isHealthReady('), main.indexOf('async function startGameServices('));
  vm.runInContext(stripTypeScriptTypes(probe), context);
  assert.equal(await context.isHealthReady('http://127.0.0.1/mock'), true);
  assert.equal(cancelled, 1, 'The initial probe must release its response body instead of holding a connection.');
}

async function testGameLaunchSessionBoundaries() {
  function gameHarness({ deferredServices = false, deferredSpawn = false, realServiceStartup = false, preexistingService = false } = {}) {
    const main = source('electron/main.ts');
    const services = deferred();
    const spawned = deferred();
    const serviceSpawned = deferred();
    const serviceHealth = deferred();
    const calls = { spawned: 0, written: 0, removed: 0, stopped: [], killed: 0 };
    const ownedService = { name: 'owned-by-this-attempt' };
    const game = Object.assign(new EventEmitter(), {
      exitCode: null, killed: false,
      kill() { this.killed = true; calls.killed += 1; }, unref() {},
    });
    const service = Object.assign(new EventEmitter(), {
      exitCode: null, killed: false,
      kill() { this.killed = true; calls.stopped.push([this]); },
    });
    const app = new EventEmitter();
    const context = {
      currentUser: user('old'), activeGameProcess: null, sessionEpoch: new RequestEpoch(),
      pendingGameLaunch: null, gameLaunchInFlight: false, isQuitting: false,
      app, aiChatService: { cancelAll() {} },
      fs: { existsSync: () => true }, path,
      readGameConfig: () => ({ executablePath: path.join(root, 'mock-game.exe'), contractVersion: '1.0',
        services: realServiceStartup ? [{ name: 'owned-service', executablePath: 'mock-service.exe', healthUrl: 'http://127.0.0.1/mock' }] : [], }),
      startGameServices: () => deferredServices ? services.promise : Promise.resolve([ownedService]),
      stopGameServices: (processes) => calls.stopped.push(processes),
      writeLaunchSession: () => { calls.written += 1; return { sessionPath: 'mock-session.json', launchId: 'mock-launch' }; },
      removeSessionFile: () => { calls.removed += 1; },
      spawn: (executable) => {
        if (executable === 'mock-service.exe') {
          queueMicrotask(() => { service.emit('spawn'); serviceSpawned.resolve(); });
          return service;
        }
        calls.spawned += 1; spawned.resolve();
        if (!deferredSpawn) queueMicrotask(() => game.emit('spawn'));
        return game;
      },
      isHealthReady: async () => preexistingService,
      waitForServiceHealth: () => serviceHealth.promise,
      logEvent() {}, logError() {},
      expiredSessionResult: () => ({ ok: false, message: '账户会话已改变，请重新操作。' }),
    };
    vm.createContext(context);
    const launchCode = main.slice(main.indexOf('function cancelGameLaunchAttempt('), main.indexOf('async function runPackagedSmokeAutoLaunch('));
    const sessionCheck = main.slice(main.indexOf('function isCurrentSession('), main.indexOf('function createWindow()'));
    const quitCode = main.slice(main.indexOf("app.on('before-quit'"), main.indexOf("app.on('child-process-gone'"));
    const serviceCode = realServiceStartup
      ? main.slice(main.indexOf('async function startGameServices('), main.indexOf('function cancelGameLaunchAttempt('))
      : '';
    vm.runInContext(stripTypeScriptTypes(`${sessionCheck}\n${serviceCode}\n${launchCode}\n${quitCode}`), context);
    return { context, calls, game, service, ownedService, services, spawned, serviceSpawned, serviceHealth,
      quit: () => app.emit('before-quit'), launch: () => context.launchConfiguredGame(context.currentUser) };
  }

  {
    const test = gameHarness({ deferredServices: true });
    const pending = test.launch();
    test.context.sessionEpoch.invalidate();
    test.context.currentUser = user('new');
    test.services.resolve([test.ownedService]);
    assert.equal((await pending).ok, false);
    assert.equal(test.calls.spawned, 0, 'Logout/account switch while services start must prevent the old game launch.');
    assert.equal(test.calls.written, 0, 'An expired account must not get a newly issued launch session.');
    assert.equal(test.calls.stopped[0][0], test.ownedService);
    assert.equal(test.calls.killed, 0);
  }

  {
    const test = gameHarness({ deferredSpawn: true });
    const pending = test.launch();
    await test.spawned.promise;
    assert.equal(test.calls.spawned, 1);
    test.context.sessionEpoch.invalidate();
    test.context.currentUser = null;
    test.game.emit('spawn');
    assert.equal((await pending).ok, false);
    assert.equal(test.calls.killed, 1, 'Only a new process created by the expired attempt is stopped.');
    assert.equal(test.calls.removed, 1, 'The expired launch ticket must be removed.');
    assert.equal(test.calls.stopped[0][0], test.ownedService);
    assert.equal(test.context.activeGameProcess, null);
  }

  {
    const test = gameHarness();
    const existing = { exitCode: null, killed: false, kill: () => assert.fail('An existing game must not be killed.') };
    test.context.activeGameProcess = existing;
    assert.equal((await test.launch()).ok, false);
    assert.equal(test.calls.spawned, 0);
    assert.equal(test.calls.stopped.length, 0);
  }

  {
    const test = gameHarness();
    assert.equal((await test.launch()).ok, true, 'A current session must still launch normally.');
    assert.equal(test.context.activeGameProcess, test.game);
    assert.equal(test.calls.killed, 0);
    test.game.emit('exit', 0, null);
    assert.equal(test.calls.removed, 1);
    assert.equal(test.calls.stopped[0][0], test.ownedService);
  }

  {
    const test = gameHarness({ realServiceStartup: true });
    const pending = test.launch();
    await test.serviceSpawned.promise;
    assert.equal(test.service.killed, false);
    test.quit();
    // No promise/finally is allowed to run between before-quit and this check.
    assert.equal(test.service.killed, true, 'before-quit must synchronously stop its pending startup service.');
    assert.equal(test.calls.spawned, 0, 'A game is not yet owned during a hanging service health check.');
    test.serviceHealth.resolve(false);
    assert.equal((await pending).ok, false);
  }

  {
    const test = gameHarness({ deferredSpawn: true });
    const pending = test.launch();
    await test.spawned.promise;
    test.quit();
    assert.equal(test.calls.killed, 1, 'before-quit must stop the new game synchronously, before the spawn await resumes.');
    assert.equal(test.calls.removed, 1, 'before-quit must synchronously remove the uncommitted launch ticket.');
    assert.equal(test.calls.stopped[0][0], test.ownedService);
    test.game.emit('spawn');
    assert.equal((await pending).ok, false);
    assert.equal(test.calls.killed, 1, 'Later cleanup must not stop the owned game twice.');
    assert.equal(test.calls.removed, 1, 'Later cleanup must not delete a different/new ticket.');
  }

  {
    const test = gameHarness({ realServiceStartup: true, preexistingService: true });
    assert.equal((await test.launch()).ok, true);
    test.quit();
    assert.equal(test.service.killed, false, 'before-quit must never kill a preexisting service.');
    assert.equal(test.game.killed, false, 'before-quit must leave an already delivered game running.');
  }

  {
    const test = gameHarness();
    assert.equal((await test.launch()).ok, true);
    test.quit();
    assert.equal(test.calls.killed, 0);
    assert.equal(test.calls.stopped.length, 0, 'Delivered game services remain owned by the game-exit handler, not a pending attempt.');
  }
}

function testComponentHarness(file, componentName, props, extraContext = {}) {
  // Execute the real component's hook/event-handler code, without evaluating its
  // JSX or requiring a browser. This preserves its actual async guards in tests.
  const component = source(file);
  const start = component.indexOf(`export function ${componentName}(`);
  assert.ok(start >= 0);
  const end = component.indexOf('\n  return (', start);
  assert.ok(end >= 0);
  const prefix = component.slice(start, end).replace('export function', 'function');
  const cleanups = [];
  const stateWrites = [];
  const context = {
    useRef: (value) => ({ current: value }),
    useEffect: (effect) => { const cleanup = effect(); if (cleanup) cleanups.push(cleanup); },
    useState: (value) => [typeof value === 'function' ? value() : value, (next) => stateWrites.push(next)],
    emptyQuestionnaire: { interests: ['', '', ''] },
    ...extraContext,
  };
  vm.createContext(context);
  vm.runInContext(stripTypeScriptTypes(`${prefix}\nreturn { submit: typeof submit === 'undefined' ? saveSupplement : submit }; }\nthis.component = ${componentName};`), context);
  return { handlers: context.component(props), unmount: () => cleanups.forEach((cleanup) => cleanup()), stateWrites };
}

async function testRendererLateResponses() {
  const formEvent = { preventDefault() {} };
  {
    const request = deferred();
    let loginCalls = 0;
    let applied = 0;
    let stateIndex = 0;
    const initialStates = ['login', 'Mock user', 'mock@example.com', 'MockOnly123!', '', '', false];
    const view = testComponentHarness('src/pages/AccountFlow.tsx', 'AuthScreen', { onAuthenticated: () => { applied += 1; } }, {
      useState: (value) => [initialStates[stateIndex++] ?? value, () => {}],
      login: () => { loginCalls += 1; return request.promise; },
    });
    const pending = view.handlers.submit(formEvent);
    await view.handlers.submit(formEvent);
    assert.equal(loginCalls, 1, 'Authentication must coalesce synchronous duplicate submits.');
    view.unmount();
    request.resolve(user('old'));
    await pending;
    assert.equal(applied, 0, 'An unmounted authentication form must not revive a session.');
  }
  for (const [file, name, callbackName, apiName] of [
    ['src/pages/ProfilePage.tsx', 'ProfilePage', 'onUserUpdated', 'supplementProfile'],
    ['src/pages/AccountFlow.tsx', 'QuestionnaireScreen', 'onCompleted', 'completeQuestionnaire'],
  ]) {
    const request = deferred();
    let calls = 0;
    let applied = 0;
    const view = testComponentHarness(file, name, { user: user('old'), [callbackName]: () => { applied += 1; } }, {
      [apiName]: () => { calls += 1; return request.promise; },
    });
    const pending = view.handlers.submit(formEvent);
    await view.handlers.submit(formEvent);
    assert.equal(calls, 1, `${name} must coalesce repeated submits before React renders busy state.`);
    view.unmount();
    const writesBeforeResolution = view.stateWrites.length;
    request.resolve(user('old'));
    await pending;
    assert.equal(applied, 0, `${name} must not apply a response after it unmounts.`);
    assert.equal(view.stateWrites.length, writesBeforeResolution, `${name} must not write state after it unmounts.`);

    let normalApplied = 0;
    const normal = testComponentHarness(file, name, { user: user('old'), [callbackName]: () => { normalApplied += 1; } }, {
      [apiName]: async () => user('old'),
    });
    await normal.handlers.submit(formEvent);
    assert.equal(normalApplied, 1, `${name} must still apply a current successful response.`);
  }

  const app = source('src/App.tsx');
  const handlersSource = app.slice(app.indexOf('  const authenticated ='), app.indexOf('  if (booting &&'));
  const renderedUser = user('old');
  const signout = deferred();
  const writtenUsers = [];
  const context = {
    accountEpoch: { current: 0 }, renderedEpoch: 0, user: renderedUser,
    setUser: (next) => writtenUsers.push(next), setFirstBoot() {}, setBooting() {},
    signOut: () => signout.promise,
  };
  vm.createContext(context);
  vm.runInContext(stripTypeScriptTypes(`${handlersSource}\nthis.callbacks = { authenticated, questionnaireCompleted, userUpdated, logout };`), context);
  const pendingLogout = context.callbacks.logout();
  context.callbacks.userUpdated(user('old'));
  context.callbacks.questionnaireCompleted(user('old'));
  context.callbacks.authenticated(user('old'));
  assert.equal(writtenUsers.length, 0, 'App must ignore stale account callbacks as soon as logout begins.');
  signout.resolve();
  await pendingLogout;
  assert.deepEqual(writtenUsers, [null]);
}

(async () => {
  await testMainSessionBoundaries();
  await testGameLaunchSessionBoundaries();
  testOneWayIpcRejections();
  await testInitialHealthProbeCleanup();
  await testRendererLateResponses();
  console.log('Session invalidation, game launch ownership, companion identity and stale UI response tests passed.');
})().catch((error) => { console.error(error); process.exitCode = 1; });
