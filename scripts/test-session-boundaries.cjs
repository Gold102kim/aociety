const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { EventEmitter } = require('node:events');
const { stripTypeScriptTypes } = require('node:module');
const { RequestEpoch } = require('../dist-electron/request-epoch.js');
const { RepresentativeStore } = require('../dist-electron/representative-store.js');
const { runPrivateSimulation, runRepresentativeChat } = require('../dist-electron/representative-chat.js');

const root = path.resolve(__dirname, '..');
const source = (file) => fs.readFileSync(path.join(root, file), 'utf8');
const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((accept, fail) => { resolve = accept; reject = fail; });
  return { promise, resolve, reject };
};
const user = (id) => ({ id, displayName: `Mock ${id}`, basicQuestionnaireCompletedAt: '2026-01-01T00:00:00Z', aiAgent: { status: 'READY' } });

function mainHarness() {
  const main = source('electron/main.ts');
  const handlers = new Map();
  const context = {
    RequestEpoch,
    sessionEpoch: new RequestEpoch(),
    conversationEpoch: new RequestEpoch(),
    runRepresentativeChat,
    runPrivateSimulation,
    currentUser: null,
    companionWindow: null,
    assertTrustedSender() {},
    assertAppWindowSender() {},
    aiChatService: { cancelCount: 0, cancelAll() { this.cancelCount += 1; }, getStatus() { return { provider: 'deepseek' }; } },
    ipcMain: { handle: (name, handler) => handlers.set(name, handler) },
    accountStore: {},
    representativeStore: {
      clearSession() {}, cancelPendingLearning() {}, beginConversation() {}, isTemporary: () => false, isLearningPaused: () => false,
      observeContext() {}, observeSavedContent() {},
      getState: async () => ({ cloudConsent: true, privacyEpoch: 0, revision: 0, memories: [], continuations: [], learningMode: 'off' }),
      learn: async () => null,
    },
    launchConfiguredGame: async () => ({ ok: true }),
  };
  vm.createContext(context);
  const helpers = main.slice(main.indexOf('function discardCompanionWindow()'), main.indexOf('function createWindow()'));
  const handlersSource = main.slice(main.indexOf("ipcMain.handle('companion:get-state'"));
  vm.runInContext(stripTypeScriptTypes(`${helpers}\n${handlersSource}`), context);
  return { context, invoke: (name, input) => handlers.get(name)({}, name === 'ai:chat' ? { temporary: false, privacyEpoch: 0, ...input } : input) };
}

async function testMainSessionBoundaries() {
  {
    const { context, invoke } = mainHarness();
    context.currentUser = user('runtime-pause');
    context.aiChatService.cancelAccount = () => {};
    const state = { revision: 2, memories: [], continuations: [], learningMode: 'learn' };
    context.representativeStore.getState = async () => state;
    context.representativeStore.update = async () => state;
    context.representativeStore.continuation = async () => ({ state });
    context.representativeStore.isLearningPaused = () => true;
    for (const channel of ['representative:get-state', 'representative:update', 'representative:continuation']) {
      const result = await invoke(channel, { kind: 'save' });
      assert.equal(result.ok, true);
      assert.equal(result.learningPaused, true, 'Every representative result carries the current runtime pause.');
      assert.equal(result.temporary, false, 'Every representative result carries the current temporary mode.');
      assert.equal(Object.hasOwn(result.state, 'learningPaused'), false, 'Runtime metadata stays outside persistent state.');
      assert.equal(Object.hasOwn(result.state, 'temporary'), false, 'Temporary mode must not be persisted in the profile.');
    }
  }
  {
    const { context, invoke } = mainHarness();
    context.currentUser = user('temporary');
    context.aiChatService.cancelAccount = () => {};
    const state = { revision: 2, memories: [{ source: 'Private profile evidence' }], continuations: [{ content: 'Private saved content' }], learningMode: 'learn' };
    const before = JSON.stringify(state);
    context.representativeStore.getState = async () => state;
    context.representativeStore.update = async () => state;
    context.representativeStore.continuation = async () => ({ state, resumed: state.continuations[0] });
    context.representativeStore.isTemporary = () => true;
    for (const channel of ['representative:get-state', 'representative:update', 'representative:continuation']) {
      const result = await invoke(channel, { kind: 'save' });
      assert.equal(result.ok, true);
      assert.equal(result.temporary, true, 'A remounted renderer must receive the live temporary mode.');
      assert.equal(result.state.memories.length, 0, 'Temporary responses must not expose long-term profile evidence.');
      assert.equal(result.state.continuations.length, 0, 'Temporary responses must not expose saved content.');
      assert.equal(Object.hasOwn(result, 'resumed'), false, 'Temporary responses must omit resumed private content.');
      assert.equal(Object.hasOwn(result.state, 'temporary'), false);
      assert.equal(JSON.stringify(result).includes('Private'), false);
    }
    assert.equal(JSON.stringify(state), before, 'Redacting the renderer result must not delete or alter persistent content.');
  }
  {
    const { context, invoke } = mainHarness();
    const accountId = 'cancel-only';
    const store = new RepresentativeStore(path.join(root, 'unused-runtime-only-store'), {});
    const cancelled = [];
    context.currentUser = user(accountId);
    context.representativeStore = store;
    context.aiChatService.cancelAccount = (id) => cancelled.push(id);
    store.beginConversation(accountId, true);
    store.observeSavedContent(accountId);
    const epoch = context.conversationEpoch.capture();
    await invoke('ai:cancel');
    assert.equal(context.conversationEpoch.isCurrent(epoch), false, 'Cancel-only must still invalidate pending requests.');
    assert.equal(store.isTemporary(accountId), true, 'Stopping generation must not switch a temporary conversation to normal mode.');
    assert.equal(store.isLearningPaused(accountId), true, 'Stopping generation must retain the non-personal context safety pause.');
    assert.deepEqual(cancelled, [accountId]);
    assert.throws(() => invoke('ai:cancel', 'false'), /对话模式无效/);
    assert.equal(store.isTemporary(accountId), true);
    assert.equal(store.isLearningPaused(accountId), true);
    await invoke('ai:cancel', false);
    assert.equal(store.isTemporary(accountId), false, 'An explicit mode starts the requested new conversation.');
    assert.equal(store.isLearningPaused(accountId), false, 'Only a new conversation clears the non-personal context safety pause.');
    await invoke('ai:cancel', true);
    assert.equal(store.isTemporary(accountId), true);
  }

  for (const channel of ['representative:get-state', 'representative:update', 'representative:continuation']) {
    for (const rejected of [false, true]) {
      const { context, invoke } = mainHarness();
      const request = deferred();
      let valid;
      context.currentUser = user('same-account');
      context.aiChatService.cancelAccount = () => {};
      const operation = channel.split(':')[1];
      if (operation === 'get-state') context.representativeStore.getState = (_id, guard) => { valid = guard; return request.promise; };
      else context.representativeStore[operation] = (_id, _input, guard) => { valid = guard; return request.promise; };
      const pending = invoke(channel, { kind: operation === 'continuation' ? 'resume' : 'mode' });
      assert.equal(valid(), true, `${channel} must accept work in the active conversation.`);
      await invoke('ai:cancel', true);
      assert.equal(valid(), false, `${channel} must invalidate a read or write that predates a mode switch.`);
      if (rejected) request.reject(new Error('Private pre-switch failure'));
      else {
        const state = { memories: [{ source: 'Private pre-switch profile' }], continuations: [{ content: 'Private pre-switch saved text' }] };
        request.resolve(operation === 'continuation' ? { state, resumed: state.continuations[0] } : state);
      }
      const result = await pending;
      assert.equal(result.ok, false, `${channel} must reject pre-switch results even if the account did not change.`);
      assert.equal(JSON.stringify(result).includes('Private pre-switch'), false, 'Old private data and errors must never reach the next conversation.');
    }
  }
  for (const cancelled of [false, true]) {
    const { context, invoke } = mainHarness();
    const request = deferred();
    const started = deferred();
    context.currentUser = user('old');
    context.aiChatService.chat = () => { started.resolve(); return request.promise; };
    context.aiChatService.cancelAccount = () => {};
    const pending = invoke('ai:simulate', { scenario: '虚构保留场景', mode: 'generic', temporary: false, privacyEpoch: 0, expectedRevision: 0 });
    await started.promise;
    if (cancelled) await invoke('ai:cancel', false);
    else { await invoke('auth:logout'); context.currentUser = user('new'); }
    request.resolve({ text: '不得显示的旧试答', model: 'deepseek-test' });
    const result = await pending;
    assert.equal(result.ok, false, 'A cancelled or old-account simulation must never reach the renderer.');
    assert.equal(JSON.stringify(result).includes('不得显示的旧试答'), false);
  }

  for (const channel of ['representative:get-state', 'representative:continuation']) {
    const { context, invoke } = mainHarness();
    const request = deferred();
    let valid;
    context.currentUser = user('old');
    if (channel === 'representative:get-state') context.representativeStore.getState = (_accountId, guard) => { valid = guard; return request.promise; };
    else context.representativeStore.continuation = (_accountId, _input, guard) => { valid = guard; return request.promise; };
    const pending = invoke(channel, { kind: 'save', item: { title: 'Private old draft', content: 'Private old content', kind: 'draft' }, expectedRevision: 0 });
    await invoke('auth:logout');
    context.currentUser = user('new');
    assert.equal(valid(), false, `${channel} must invalidate old-account work.`);
    request.resolve(channel === 'representative:get-state' ? { accountId: 'old', continuations: ['private content'] } : { state: { accountId: 'old' } });
    const result = await pending;
    assert.equal(result.ok, false);
    assert.equal(JSON.stringify(result).includes('private content'), false, 'Old-account continuation data must not reach the new renderer.');
  }

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
    await new Promise(setImmediate);
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
    await new Promise(setImmediate);
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

async function testRendererDocumentBoundaries() {
  const main = source('electron/main.ts');
  const security = main.slice(main.indexOf('function configureWindowSecurity('), main.indexOf('function companionPosition('));
  function rendererHarness(role = 'main') {
    const test = mainHarness();
    const contents = Object.assign(new EventEmitter(), { setWindowOpenHandler() {} });
    test.context.logEvent = () => {};
    test.context.isTrustedRendererUrl = () => true;
    vm.runInContext(stripTypeScriptTypes(security), test.context);
    test.context.configureWindowSecurity({ webContents: contents }, role);
    return { ...test, contents };
  }
  for (const role of ['main', 'companion']) {
    const { context, contents } = rendererHarness(role);
    context.currentUser = user('document-boundary');
    for (const details of [
      { isMainFrame: false, isSameDocument: false },
      { isMainFrame: true, isSameDocument: true },
      ...(role === 'companion' ? [{ isMainFrame: true, isSameDocument: false }] : []),
    ]) {
      contents.emit('did-start-navigation', details);
      assert.equal(context.currentUser.id, 'document-boundary', 'Subframe, same-document and companion navigation must preserve the main session.');
      assert.equal(context.aiChatService.cancelCount, 0);
    }
    if (role === 'companion') {
      contents.emit('render-process-gone', {}, { reason: 'crashed', exitCode: 1 });
      assert.equal(context.currentUser.id, 'document-boundary', 'A companion crash must not log the main renderer out.');
      assert.equal(context.aiChatService.cancelCount, 0);
    }
  }
  for (const event of ['did-start-navigation', 'render-process-gone']) {
    const { context, contents } = rendererHarness();
    context.currentUser = user('document-boundary');
    const store = new RepresentativeStore(path.join(root, 'unused-runtime-only-store'), {});
    context.representativeStore = store;
    store.beginConversation(context.currentUser.id, true);
    store.observeSavedContent(context.currentUser.id);
    const session = context.sessionEpoch.capture();
    const conversation = context.conversationEpoch.capture();
    let companionDestroyed = 0;
    context.companionWindow = { isDestroyed: () => false, destroy: () => { companionDestroyed += 1; } };
    if (event === 'did-start-navigation') contents.emit(event, { isMainFrame: true, isSameDocument: false });
    else contents.emit(event, {}, { reason: 'crashed', exitCode: 1 });
    assert.equal(context.currentUser, null, 'A new main document or renderer process must reauthenticate instead of inheriting hidden runtime privacy flags.');
    assert.equal(context.sessionEpoch.isCurrent(session), false);
    assert.equal(context.conversationEpoch.isCurrent(conversation), false);
    assert.equal(store.isTemporary('document-boundary'), false);
    assert.equal(store.isLearningPaused('document-boundary'), false);
    assert.equal(context.aiChatService.cancelCount, 1);
    assert.equal(companionDestroyed, 1, 'A new main renderer must not leave an old companion identity alive.');
  }
  {
    const { context, contents, invoke } = rendererHarness();
    const login = deferred();
    context.accountStore.login = () => login.promise;
    const pending = invoke('auth:login', { email: 'mock@example.com', password: 'MockOnly123!' });
    contents.emit('did-start-navigation', { isMainFrame: true, isSameDocument: false });
    login.resolve(user('old-document'));
    assert.equal((await pending).ok, false, 'A login from the previous document must not authenticate the replacement renderer.');
    assert.equal(context.currentUser, null);
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
  const end = component.indexOf('\n  return (', start) >= 0
    ? component.indexOf('\n  return (', start)
    : component.indexOf('\n  return <', start);
  assert.ok(end >= 0);
  const prefix = component.slice(start, end).replace('export function', 'function').replaceAll('import.meta.env.DEV', 'false');
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
  vm.runInContext(stripTypeScriptTypes(`${prefix}\nreturn { submit: typeof submit === 'undefined' ? (typeof saveSupplement === 'undefined' ? undefined : saveSupplement) : submit, requestReply: typeof requestReply === 'undefined' ? undefined : requestReply, clearConversation: typeof clearConversation === 'undefined' ? undefined : clearConversation, readPrivacy: typeof readPrivacy === 'undefined' ? undefined : readPrivacy, updatePrivacy: typeof updatePrivacy === 'undefined' ? undefined : updatePrivacy, stop: typeof stop === 'undefined' ? undefined : stop }; }\nthis.component = ${componentName};`), context);
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
  vm.runInContext(stripTypeScriptTypes(`${handlersSource}\nthis.callbacks = { authenticated, userUpdated, logout };`), context);
  const pendingLogout = context.callbacks.logout();
  context.callbacks.userUpdated(user('old'));
  context.callbacks.authenticated(user('old'));
  assert.equal(writtenUsers.length, 0, 'App must ignore stale account callbacks as soon as logout begins.');
  signout.resolve();
  await pendingLogout;
  assert.deepEqual(writtenUsers, [null]);
}

async function testLearningPauseFeedback() {
  const stateNames = [...source('src/pages/AiChatPage.tsx').matchAll(/const \[([^,]+), [^\]]+\] = useState/g)].map((match) => match[1]);
  function viewFor(getState, cancel = async () => {}) {
    const writes = [];
    let listener;
    let stateIndex = 0;
    const view = testComponentHarness('src/pages/AiChatPage.tsx', 'AiChatPage', { user: { ...user('pause-test'), aiAgent: { modelAssignment: { baseModelId: 'test-model' } } } }, {
      getAiStatus: async () => ({ configured: true, provider: 'deepseek', connection: 'untested' }),
      window: { launcher: { ai: { cancel }, representative: { getState, onChanged: (callback) => { listener = callback; return () => {}; } } } },
      useState: (value) => { const name = stateNames[stateIndex++]; return [value, (next) => writes.push({ name, next })]; },
    });
    return { ...view, writes, notice: (status) => listener(status) };
  }
  const snapshot = { revision: 4, privacyEpoch: 2, learningMode: 'learn', cloudConsent: true, memories: [], continuations: [] };
  const oldRead = deferred();
  let reads = 0;
  const paused = viewFor(() => ++reads === 1 ? oldRead.promise : Promise.resolve({ ok: true, state: snapshot, learningPaused: true, temporary: false }));
  paused.notice('paused');
  await new Promise(setImmediate);
  oldRead.resolve({ ok: true, state: snapshot, learningPaused: false, temporary: false });
  await new Promise(setImmediate);
  assert.ok(paused.writes.some(({ name, next }) => name === 'learningPaused' && next === true));
  assert.equal(paused.writes.some(({ name, next }) => name === 'learningPaused' && next === false), false, 'An older privacy read must not overwrite a newer pause event.');
  assert.equal(paused.writes.some(({ name, next }) => name === 'learningNotice' && next.includes('未保存')), false, 'A safety pause is not an encryption failure.');
  paused.unmount();

  const refresh = viewFor(async () => ({ ok: true, state: snapshot, learningPaused: true, temporary: false }));
  await new Promise(setImmediate);
  assert.ok(refresh.writes.some(({ name, next }) => name === 'learningPaused' && next === true), 'A newly mounted chat reads the runtime pause.');
  refresh.unmount();

  const stalePause = deferred();
  let clearReads = 0;
  const clearing = viewFor(() => ++clearReads === 1 ? stalePause.promise : Promise.resolve({ ok: true, state: snapshot, learningPaused: false, temporary: false }));
  await clearing.handlers.clearConversation();
  stalePause.resolve({ ok: true, state: snapshot, learningPaused: true, temporary: false });
  await new Promise(setImmediate);
  assert.equal(clearing.writes.some(({ name, next }) => name === 'learningPaused' && next === true), false, 'A pre-clear read cannot restore the old paused label.');
  clearing.unmount();

  const temporaryView = viewFor(async () => ({ ok: true, state: { ...snapshot, continuations: [] }, learningPaused: false, temporary: true }));
  await new Promise(setImmediate);
  assert.ok(temporaryView.writes.some(({ name, next }) => name === 'temporary' && next === true), 'A newly mounted chat must display the current main-process temporary mode.');
  temporaryView.unmount();

  {
    const oldMode = deferred();
    const switchedMode = deferred();
    const cancellations = [];
    let modeReads = 0;
    const switching = viewFor(() => ++modeReads === 1 ? oldMode.promise : switchedMode.promise, async (mode) => { cancellations.push(mode); });
    const pending = switching.handlers.clearConversation(true);
    await new Promise(setImmediate);
    assert.deepEqual(cancellations, [true], 'Switching modes must explicitly request the new conversation mode.');
    assert.ok(switching.writes.some(({ name, next }) => name === 'privacy' && next === null), 'Switching modes hides the old profile until a fresh result is available.');
    assert.ok(switching.writes.some(({ name, next }) => name === 'privacyBusy' && next === true));
    assert.equal(switching.writes.some(({ name, next }) => name === 'privacyBusy' && next === false), false, 'Privacy actions stay blocked while the post-switch read is pending.');
    switchedMode.resolve({ ok: true, state: { ...snapshot, memories: [], continuations: [] }, learningPaused: false, temporary: true });
    assert.equal(await pending, true);
    assert.ok(switching.writes.some(({ name, next }) => name === 'temporary' && next === true));
    oldMode.resolve({ ok: true, state: snapshot, learningPaused: false, temporary: false });
    await new Promise(setImmediate);
    assert.equal(switching.writes.some(({ name, next }) => name === 'temporary' && next === false), false, 'A pre-switch read must not overwrite the newer temporary mode in the renderer.');
    assert.equal(switching.writes.filter(({ name }) => name === 'privacy').at(-1).next.memories.length, 0);
    switching.unmount();
  }

  for (const response of [
    { ok: false, message: 'Isolated privacy read failure' },
    { ok: true, state: snapshot, learningPaused: false },
  ]) {
    const failed = viewFor(async () => response);
    await new Promise(setImmediate);
    assert.equal(await failed.handlers.readPrivacy(), false, 'A failed read or missing runtime mode metadata must not be treated as a usable privacy snapshot.');
    assert.equal(await failed.handlers.clearConversation(true), false, 'Cancelling requests alone cannot unlock a conversation whose privacy read failed.');
    assert.ok(failed.writes.some(({ name, next }) => name === 'privacy' && next === null));
    assert.ok(failed.writes.some(({ name, next }) => name === 'privacyError' && Boolean(next)));
    assert.equal(failed.writes.some(({ name, next }) => name === 'temporary' && next === false), false, 'Read failure must never invent a normal-mode snapshot.');
    failed.unmount();
  }

  const chatSource = source('src/pages/AiChatPage.tsx');
  const temporaryControl = chatSource.slice(chatSource.indexOf('className="chat-side-card representative-temporary"'));
  assert.match(temporaryControl.match(/disabled=\{([^}]+)\}/)?.[1] ?? '', /!privacy/, 'The temporary switch must be unavailable before privacy metadata has been read.');

  const ipcCalls = [];
  const ipc = Object.assign(new EventEmitter(), { invoke: (...args) => { ipcCalls.push(args); return Promise.resolve(); } });
  let api;
  vm.runInNewContext(stripTypeScriptTypes(source('electron/preload.ts').replace(/^import .*;\r?\n/gm, '')), {
    contextBridge: { exposeInMainWorld: (_name, exposed) => { api = exposed; } }, ipcRenderer: ipc,
  });
  const notices = [];
  const unsubscribe = api.representative.onChanged((status) => notices.push(status));
  for (const status of ['saved', 'failed', 'paused', 'unknown', null, { status: 'paused' }]) ipc.emit('representative:changed', {}, status);
  assert.deepEqual(notices, ['saved', 'failed', 'paused'], 'The preload bridge accepts only known status values.');
  unsubscribe();
  assert.equal(ipc.listenerCount('representative:changed'), 0);
  await api.ai.cancel();
  await api.ai.cancel(true);
  await api.ai.cancel(false);
  assert.deepEqual(ipcCalls.map((args) => args[0]), ['ai:cancel', 'ai:cancel', 'ai:cancel']);
  assert.deepEqual(ipcCalls.map((args) => args[1]), [undefined, true, false], 'The preload bridge must not turn cancel-only into a false-mode conversation reset.');
}

async function testSimulationStopPreservesConversation() {
  const cancellations = [];
  const view = testComponentHarness('src/components/PrivateSimulationPanel.tsx', 'PrivateSimulationPanel', {
    state: { revision: 2, storage: 'encrypted', memories: [], learningMode: 'learn' }, temporary: true,
    canGenerate: true, onBusyChange() {}, onRefresh: async () => true, onStatusRefresh: async () => {},
  }, {
    simulationModes: ['generic', 'confirmed', 'all'],
    window: { launcher: { ai: { cancel: async (...args) => { cancellations.push(args); } } } },
  });
  await view.handlers.stop();
  assert.deepEqual(cancellations, [[]], 'Stopping a private trial cancels its request without declaring a new conversation or clearing its context guard.');
  view.unmount();
}

async function testChatStopLifecycle() {
  const chat = source('src/pages/AiChatPage.tsx');
  const stateNames = [...chat.matchAll(/const \[([^,]+), [^\]]+\] = useState/g)].map((match) => match[1]);
  const refNames = [...chat.matchAll(/const (\w+) = useRef/g)].map((match) => match[1]);
  const snapshot = { revision: 4, privacyEpoch: 2, learningMode: 'learn', cloudConsent: true, storage: 'encrypted', memories: [], continuations: [] };
  const turn = { message: { id: 'sent', role: 'user', content: 'Existing sent message' }, history: [], savedContent: true };
  const nextTurn = { ...turn, message: { ...turn.message, id: 'next', content: 'Next message' } };
  const flush = () => new Promise(setImmediate);
  function mount() {
    const states = new Map();
    const refs = new Map();
    const writes = [];
    const requests = [];
    const cancellations = [];
    const deferredPrivacyReads = [];
    const privacyReads = [];
    let nextPrivacyFailure = '';
    let stateIndex = 0;
    let refIndex = 0;
    let statusReads = 0;
    const initial = { messages: [{ id: 'welcome', role: 'assistant', content: 'Welcome' }, turn.message], input: 'Unsent draft', privacy: snapshot, temporary: true, learningPaused: true };
    const current = { ok: true, state: snapshot, learningPaused: true, temporary: true };
    const view = testComponentHarness('src/pages/AiChatPage.tsx', 'AiChatPage', {
      user: { ...user('chat-stop-test'), aiAgent: { modelAssignment: { baseModelId: 'test-model' } } },
    }, {
      Error,
      crypto: { randomUUID: () => 'isolated-chat-id' },
      getRecentChatHistory: (messages) => messages,
      getAiStatus: async () => { statusReads += 1; return { configured: true, provider: 'deepseek', connection: 'untested' }; },
      sendAiMessage: (...args) => { const request = { ...deferred(), args }; requests.push(request); return request.promise; },
      window: { launcher: {
        ai: { cancel: (...args) => { const request = { ...deferred(), args }; cancellations.push(request); return request.promise; } },
        representative: {
          getState: () => {
            const pending = deferredPrivacyReads.shift();
            privacyReads.push(pending);
            return pending ? pending.promise : Promise.resolve(current);
          },
          update: async () => {
            const message = nextPrivacyFailure;
            nextPrivacyFailure = '';
            return message ? { ok: false, message } : current;
          },
          onChanged: () => () => {},
        },
      } },
      useRef: (value) => { const name = refNames[refIndex++]; const ref = { current: name === 'restoredDraft' ? true : value }; refs.set(name, ref); return ref; },
      useState: (value) => {
        const name = stateNames[stateIndex++];
        const initialValue = Object.hasOwn(initial, name) ? initial[name] : value;
        states.set(name, initialValue);
        return [initialValue, (next) => {
          const resolved = typeof next === 'function' ? next(states.get(name)) : next;
          states.set(name, resolved); writes.push({ name, next: resolved });
        }];
      },
    });
    assert.equal(typeof view.handlers.stop, 'function', 'Daily chat must expose a stop action without clearing the conversation.');
    return { ...view, states, refs, writes, requests, cancellations, privacyReads,
      queuePrivacyRead: () => { const pending = deferred(); deferredPrivacyReads.push(pending); return pending; },
      failPrivacyUpdate: (message) => { nextPrivacyFailure = message; },
      get statusReads() { return statusReads; } };
  }
  const reply = (text) => ({ text, responseId: text, model: 'isolated-model' });
  const settle = (pending, fails, text) => fails ? pending.reject(new Error(text)) : pending.resolve(reply(text));
  function preserved(view, messageList) {
    assert.equal(view.states.get('messages'), messageList, 'Stopping must preserve the displayed conversation.');
    assert.equal(view.states.get('input'), 'Unsent draft', 'Stopping must preserve unsent text.');
    assert.equal(view.states.get('temporary'), true, 'Stopping must preserve temporary mode.');
    assert.equal(view.states.get('learningPaused'), true, 'Stopping must not lift a safety pause.');
    assert.equal(view.refs.get('restoredDraft').current, true, 'Stopping must preserve restored-draft provenance.');
    assert.equal(view.states.get('privacy'), snapshot);
  }

  for (const staleFails of [false, true]) for (const afterAcknowledgement of [false, true]) {
    const view = mount();
    await flush();
    const staleRead = view.queuePrivacyRead();
    const pendingRead = view.handlers.readPrivacy();
    const pendingReply = view.handlers.requestReply(turn);
    const messageList = view.states.get('messages');
    const pendingStop = view.handlers.stop();
    if (afterAcknowledgement) { view.cancellations[0].resolve(); await pendingStop; }
    const beforeStaleRead = view.writes.length;
    if (staleFails) staleRead.resolve({ ok: false, message: 'Old conversation privacy read expired' });
    else staleRead.resolve({ ok: true, state: { ...snapshot, memories: [{ source: 'Stale profile' }] }, temporary: false, learningPaused: false });
    await pendingRead;
    assert.equal(view.writes.length, beforeStaleRead, 'A privacy read started before stop cannot clear state or restore old mode/learning flags.');
    preserved(view, messageList);
    if (!afterAcknowledgement) { view.cancellations[0].resolve(); await pendingStop; }
    view.requests[0].resolve(reply('Stopped reply'));
    await pendingReply;
    view.unmount();
  }

  for (const refreshFails of [false, true]) {
    const view = mount();
    await flush();
    const mutationError = 'A real privacy update was not saved';
    view.failPrivacyUpdate(mutationError);
    assert.equal(await view.handlers.updatePrivacy({ kind: 'mode', mode: 'learn', expectedRevision: snapshot.revision }), false);
    assert.equal(view.states.get('privacyError'), mutationError);
    const pendingReply = view.handlers.requestReply(turn);
    const refresh = view.queuePrivacyRead();
    const pendingStop = view.handlers.stop();
    view.cancellations[0].resolve();
    await flush();
    assert.equal(view.privacyReads.at(-1), refresh, 'Confirmed cancellation must request the current privacy snapshot.');
    assert.equal(view.refs.get('inFlight').current, true, 'Send stays blocked until the stop refresh settles.');
    await view.handlers.requestReply(nextTurn);
    view.handlers.submit({ preventDefault() {} });
    assert.equal(view.requests.length, 1);
    if (refreshFails) refresh.reject(new Error('Current privacy refresh failed'));
    else refresh.resolve({ ok: true, state: snapshot, learningPaused: true, temporary: true });
    await pendingStop;
    assert.match(view.states.get('privacyError'), /A real privacy update was not saved/, 'Stop refresh must preserve a prior genuine privacy mutation failure.');
    assert.equal(view.states.get('stopState'), 'idle', 'Successful cancellation is distinct from a settings-read failure.');
    assert.match(view.states.get('stopNotice'), /已停止/);
    if (refreshFails) {
      assert.equal(view.states.get('privacy'), null, 'An unreadable current snapshot disables consent-dependent sending on the next render.');
      assert.match(view.states.get('privacyError'), /Current privacy refresh failed/);
      assert.equal(await view.handlers.readPrivacy(), true, 'The user can explicitly recover by rereading privacy settings.');
      assert.equal(view.states.get('privacy'), snapshot);
      assert.equal(view.states.get('privacyError'), '', 'Explicit retry may dismiss the old errors after successful recovery.');
    }
    view.requests[0].resolve(reply('Stopped reply after refresh'));
    await pendingReply;
    view.unmount();
  }

  for (const supersededBy of ['privacy', 'unmount']) for (const refreshFails of [false, true]) {
    const view = mount();
    await flush();
    const pendingReply = view.handlers.requestReply(turn);
    const refresh = view.queuePrivacyRead();
    const pendingStop = view.handlers.stop();
    view.cancellations[0].resolve();
    await flush();
    assert.equal(view.privacyReads.at(-1), refresh);
    let nextReply;
    if (supersededBy === 'privacy') {
      await view.handlers.updatePrivacy({ kind: 'mode', mode: 'learn', expectedRevision: snapshot.revision });
      nextReply = view.handlers.requestReply(nextTurn);
    } else view.unmount();
    const beforeSupersededRefresh = view.writes.length;
    if (refreshFails) refresh.reject(new Error('Superseded stop refresh failed'));
    else refresh.resolve({ ok: true, state: { ...snapshot, revision: 0 }, temporary: false, learningPaused: false });
    await pendingStop;
    view.requests[0].resolve(reply('Stopped reply from prior context'));
    await pendingReply;
    assert.equal(view.writes.length, beforeSupersededRefresh, 'A stop refresh cannot write after another privacy operation or unmount.');
    if (nextReply) {
      assert.equal(view.states.get('busy'), true, 'A superseded stop refresh cannot end the new request.');
      view.requests[1].resolve(reply('Current reply after privacy change'));
      await nextReply;
      view.unmount();
    }
  }

  for (const oldReplyFails of [false, true]) {
    const view = mount();
    await flush();
    const pendingReply = view.handlers.requestReply(turn);
    const messageList = view.states.get('messages');
    const pendingStop = view.handlers.stop();
    await view.handlers.stop();
    assert.deepEqual(view.cancellations.map(({ args }) => args), [[]], 'Repeated stops must coalesce and must not declare a new conversation mode.');
    assert.equal(view.states.get('stopState'), 'stopping');
    await view.handlers.requestReply(nextTurn);
    view.handlers.submit({ preventDefault() {} });
    assert.equal(view.requests.length, 1, 'Neither submit nor retry may send before cancellation is confirmed.');
    preserved(view, messageList);
    view.cancellations[0].resolve();
    await pendingStop;
    assert.equal(view.states.get('stopState'), 'idle');
    assert.equal(view.states.get('busy'), false);
    assert.equal(view.refs.get('inFlight').current, false);
    assert.match(view.states.get('stopNotice'), /已停止/);
    preserved(view, messageList);

    const nextReply = view.handlers.requestReply(nextTurn);
    assert.equal(view.requests.length, 2, 'Confirmed cancellation must allow a new explicit request.');
    assert.equal(view.states.get('stopNotice'), '', 'A new request must clear the old stopped notice.');
    const writesBeforeLateReply = view.writes.length;
    const statusBeforeLateReply = view.statusReads;
    settle(view.requests[0], oldReplyFails, 'Stale stopped reply');
    await pendingReply;
    assert.equal(view.writes.length, writesBeforeLateReply, 'A stopped success or failure cannot write into the new request.');
    assert.equal(view.statusReads, statusBeforeLateReply, 'A stopped failure must not refresh model status.');
    assert.equal(view.states.get('busy'), true, 'A stopped request cannot end the next request spinner.');
    view.requests[1].resolve(reply('Current reply'));
    await nextReply;
    assert.equal(view.states.get('messages').at(-1).content, 'Current reply');
    assert.equal(view.states.get('busy'), false);
    view.unmount();
  }

  {
    const view = mount();
    await flush();
    const pendingReply = view.handlers.requestReply(turn);
    const messageList = view.states.get('messages');
    const pendingStop = view.handlers.stop();
    view.cancellations[0].reject(new Error('Isolated cancellation failure'));
    await pendingStop;
    assert.equal(view.states.get('stopState'), 'blocked');
    assert.equal(view.states.get('busy'), false);
    assert.equal(view.refs.get('inFlight').current, true, 'An unconfirmed cancellation must keep the synchronous send guard.');
    assert.ok(view.states.get('error'), 'An unconfirmed cancellation needs visible failure feedback.');
    assert.doesNotMatch(view.states.get('stopNotice'), /已停止/, 'Failed cancellation must not claim success.');
    await view.handlers.requestReply(nextTurn);
    view.handlers.submit({ preventDefault() {} });
    assert.equal(view.requests.length, 1, 'Failed cancellation keeps both send and retry blocked.');
    const beforeLateReply = view.writes.length;
    view.requests[0].resolve(reply('Unconfirmed stopped reply'));
    await pendingReply;
    assert.equal(view.writes.length, beforeLateReply, 'Even before a successful stop retry, old results must stay invalid.');
    const retriedStop = view.handlers.stop();
    await view.handlers.stop();
    assert.equal(view.cancellations.length, 2, 'A failed stop can be retried once without duplicate IPC calls.');
    view.cancellations[1].resolve();
    await retriedStop;
    assert.equal(view.states.get('stopState'), 'idle');
    assert.equal(view.states.get('error'), '');
    assert.equal(view.refs.get('inFlight').current, false);
    preserved(view, messageList);
    view.unmount();
  }

  for (const fails of [false, true]) {
    const view = mount();
    await flush();
    const pendingReply = view.handlers.requestReply(turn);
    const pendingStop = view.handlers.stop();
    view.unmount();
    const beforeUnmountedResponse = view.writes.length;
    settle(view.cancellations[0], fails, 'Late stop acknowledgement');
    settle(view.requests[0], fails, 'Late chat response');
    await Promise.all([pendingStop, pendingReply]);
    assert.equal(view.writes.length, beforeUnmountedResponse, 'Stop and model responses must not write after unmount.');
  }

  for (const operation of ['privacy', 'clear']) for (const stopFails of [false, true]) {
    const view = mount();
    await flush();
    const pendingReply = view.handlers.requestReply(turn);
    const pendingStop = view.handlers.stop();
    const transition = operation === 'privacy'
      ? view.handlers.updatePrivacy({ kind: 'mode', mode: 'learn', expectedRevision: snapshot.revision })
      : view.handlers.clearConversation(true);
    if (operation === 'clear') {
      assert.deepEqual(view.cancellations[1].args, [true]);
      view.cancellations[1].resolve();
    }
    await transition;
    assert.equal(view.states.get('stopState'), 'idle', 'A deliberate conversation transition clears the old stop state.');
    const nextReply = view.handlers.requestReply(nextTurn);
    assert.equal(view.requests.length, 2);
    const beforeLateStop = view.writes.length;
    settle(view.cancellations[0], stopFails, 'Old stop outcome');
    await pendingStop;
    settle(view.requests[0], stopFails, 'Old conversation reply');
    await pendingReply;
    assert.equal(view.writes.length, beforeLateStop, 'A superseded stop acknowledgement cannot change the next conversation.');
    assert.equal(view.refs.get('inFlight').current, true);
    assert.equal(view.states.get('busy'), true);
    view.requests[1].resolve(reply('Current conversation reply'));
    await nextReply;
    assert.equal(view.states.get('messages').at(-1).content, 'Current conversation reply');
    view.unmount();
  }
}

async function testPrivacyUpdateFailureFeedback() {
  const chat = source('src/pages/AiChatPage.tsx');
  const stateNames = [...chat.matchAll(/const \[([^,]+), [^\]]+\] = useState/g)].map((match) => match[1]);
  const snapshot = { revision: 4, privacyEpoch: 2, learningMode: 'off', cloudConsent: false, memories: [], continuations: [] };
  const current = { ok: true, state: snapshot, learningPaused: false, temporary: false };
  function mount(update, recover = async () => current) {
    const states = new Map();
    const writes = [];
    let stateIndex = 0;
    let reads = 0;
    const view = testComponentHarness('src/pages/AiChatPage.tsx', 'AiChatPage', {
      user: { ...user('privacy-error-test'), aiAgent: { modelAssignment: { baseModelId: 'test-model' } } },
    }, {
      Error,
      getAiStatus: async () => ({ configured: true, provider: 'deepseek', connection: 'untested' }),
      window: { launcher: { representative: {
        getState: () => ++reads === 1 ? Promise.resolve(current) : recover(),
        update, onChanged: () => () => {},
      } } },
      useState: (value) => {
        const name = stateNames[stateIndex++];
        states.set(name, value);
        return [value, (next) => {
          const resolved = typeof next === 'function' ? next(states.get(name)) : next;
          states.set(name, resolved);
          writes.push({ name, next: resolved });
        }];
      },
    });
    return { ...view, states, writes, get reads() { return reads; } };
  }
  const action = { kind: 'reset', expectedRevision: snapshot.revision };

  const recovered = mount(async () => ({ ok: false, message: 'Isolated settings write failure' }));
  await new Promise(setImmediate);
  assert.equal(await recovered.handlers.updatePrivacy(action), false);
  assert.equal(recovered.states.get('privacy'), snapshot, 'Successful recovery keeps the authoritative privacy snapshot.');
  assert.equal(recovered.states.get('privacyError'), 'Isolated settings write failure', 'Recovery must not clear the failed mutation message.');
  recovered.unmount();

  const unreadable = mount(async () => { throw new Error('Isolated settings write failure'); }, async () => {
    throw new Error('Isolated privacy recovery failure');
  });
  await new Promise(setImmediate);
  assert.equal(await unreadable.handlers.updatePrivacy(action), false);
  assert.equal(unreadable.states.get('privacy'), null, 'Failed recovery removes the usable snapshot and keeps sending disabled.');
  assert.match(unreadable.states.get('privacyError'), /Isolated settings write failure/);
  assert.match(unreadable.states.get('privacyError'), /Isolated privacy recovery failure/, 'Keep both the write failure and the reason recovery failed.');
  unreadable.unmount();

  const saved = mount(async () => current);
  await new Promise(setImmediate);
  assert.equal(await saved.handlers.updatePrivacy(action), true, 'Only a confirmed update reports success to reset confirmation.');
  assert.equal(saved.states.get('privacyError'), '');
  saved.unmount();

  const update = deferred();
  const unmountedUpdate = mount(() => update.promise);
  await new Promise(setImmediate);
  const pendingUpdate = unmountedUpdate.handlers.updatePrivacy(action);
  assert.equal(await unmountedUpdate.handlers.updatePrivacy(action), false, 'Coalesce repeated privacy mutations before a React render.');
  unmountedUpdate.unmount();
  const beforeUpdate = unmountedUpdate.writes.length;
  update.resolve({ ok: false, message: 'Late settings write failure' });
  assert.equal(await pendingUpdate, false);
  assert.equal(unmountedUpdate.writes.length, beforeUpdate, 'A late update failure cannot write after unmount.');
  assert.equal(unmountedUpdate.reads, 1, 'Do not begin recovery for an unmounted page.');

  const recovery = deferred();
  const unmountedRecovery = mount(async () => ({ ok: false, message: 'Isolated settings write failure' }), () => recovery.promise);
  await new Promise(setImmediate);
  const pendingRecovery = unmountedRecovery.handlers.updatePrivacy(action);
  await new Promise(setImmediate);
  assert.equal(unmountedRecovery.reads, 2);
  unmountedRecovery.unmount();
  const beforeRecovery = unmountedRecovery.writes.length;
  recovery.resolve(current);
  assert.equal(await pendingRecovery, false);
  assert.equal(unmountedRecovery.writes.length, beforeRecovery, 'Late recovery and mutation feedback cannot write after unmount.');

  const panel = source('src/components/RepresentativePanel.tsx');
  const confirmation = panel.match(/onChange\(\{ kind: 'reset', expectedRevision: state\.revision \}\)\.then\(([\s\S]*?)\); \}\}>确认重置/);
  assert.ok(confirmation, 'The reset action must wait for the mutation result.');
  for (const success of [false, true]) {
    const closed = [];
    vm.runInNewContext(`(${confirmation[1]})(${success});`, { setConfirmReset: (value) => closed.push(value) });
    assert.deepEqual(closed, success ? [false] : [], 'A failed reset must not close its confirmation as though it succeeded.');
  }
}

(async () => {
  await testMainSessionBoundaries();
  await testRendererDocumentBoundaries();
  await testGameLaunchSessionBoundaries();
  testOneWayIpcRejections();
  await testInitialHealthProbeCleanup();
  await testRendererLateResponses();
  await testLearningPauseFeedback();
  await testSimulationStopPreservesConversation();
  await testChatStopLifecycle();
  await testPrivacyUpdateFailureFeedback();
  console.log('Session invalidation, renderer navigation, temporary privacy, cancel-only context, game launch ownership and stale UI response tests passed.');
})().catch((error) => { console.error(error); process.exitCode = 1; });
