const assert = require('node:assert/strict');
const { runPrivateSimulation } = require('../dist-electron/representative-chat.js');
const { simulationModes } = require('../dist-electron/simulation-types.js');

const user = { id: 'fictional-owner', displayName: '虚构测试用户', aiAgent: { status: 'WAITING_FOR_PROFILE' } };
const initial = { schemaVersion: 1, accountId: user.id, revision: 7, privacyEpoch: 3, cloudConsent: false, learningMode: 'learn', storage: 'encrypted',
  memories: [
    { key: 'replyStyle', value: '简短', sourceKind: 'user_correction' },
    { key: 'musicGenre', value: '爵士乐', sourceKind: 'explicit_message' },
  ], continuations: [{ content: '不应上传的已保存草稿' }] };
let current = structuredClone(initial);
let temporary = false;
let calls = [];
const store = {
  getState: async (accountId, valid) => { assert.equal(accountId, user.id); if (!valid()) throw new Error('Expired'); return structuredClone(current); },
  isTemporary: () => temporary,
  learn: () => assert.fail('Simulation must never learn from scenarios or replies.'),
  observeContext: () => assert.fail('Simulation context must be isolated from chat.'),
  update: () => assert.fail('Simulation must not write a profile.'),
};
const ai = { getStatus: () => ({ provider: 'deepseek' }), chat: async (...args) => {
  calls.push(args); return { text: '隔离模拟试答，不是真实模型结果。', model: 'deepseek-test' };
} };
const input = (mode = 'generic', overrides = {}) => ({ scenario: '朋友临时邀约，如何回应？', mode, temporary, privacyEpoch: current.privacyEpoch, expectedRevision: current.revision, ...overrides });
const run = (data = input(), valid = () => true) => runPrivateSimulation(store, ai, user, data, valid);
const deferred = () => { let resolve; const promise = new Promise((accept) => { resolve = accept; }); return { promise, resolve }; };

(async () => {
  await assert.rejects(run(), /明确同意/);
  assert.equal(calls.length, 0);
  current.cloudConsent = true;
  const unchanged = JSON.stringify(current);
  const expected = [{}, { replyStyle: '简短' }, { replyStyle: '简短', musicGenre: '爵士乐' }];
  for (const [index, mode] of simulationModes.entries()) {
    const result = await run(input(mode, { reference: '不应上传的对照答案', history: [{ role: 'user', content: '不应上传的聊天历史' }], accountId: 'another-owner' }));
    const [owner, scenario, history, preferences, purpose] = calls.at(-1);
    assert.equal(owner.id, user.id);
    assert.equal(scenario, '朋友临时邀约，如何回应？');
    assert.deepEqual(history, []);
    assert.deepEqual(preferences, expected[index]);
    assert.equal(purpose, 'private_simulation');
    assert.doesNotMatch(JSON.stringify(calls.at(-1)), /不应上传/);
    assert.equal(result.mode, mode);
    assert.equal(result.profileRevision, 7);
    assert.equal(result.promptVersion, 'private-simulation-v1');
    assert.deepEqual(result.usedMemoryKeys, Object.keys(expected[index]));
    assert.ok(Number.isFinite(Date.parse(result.createdAt)) && result.durationMs >= 0);
  }
  assert.equal(JSON.stringify(current), unchanged, 'No profile, draft, scenario, result or feedback is written.');
  await run(input('with_memories', { scenario: '我喜欢电子音乐' }));
  assert.equal(JSON.stringify(current), unchanged, 'Even a whitelist scenario must not become personal evidence.');

  for (const overrides of [{ scenario: '' }, { scenario: 'x'.repeat(2001) }, { mode: 'invented' }, { temporary: 'false' }, { expectedRevision: -1 }, { privacyEpoch: NaN }]) {
    await assert.rejects(run(input('generic', overrides)), /模拟参数无效/);
  }
  const beforeDenied = calls.length;
  await assert.rejects(run(input('generic', { expectedRevision: 0 })), /版本已改变/);
  await assert.rejects(run(input('generic', { privacyEpoch: 0 })), /版本已改变/);
  temporary = true;
  await assert.rejects(run(input('confirmed')), /不允许使用画像/);
  await assert.rejects(run(input('generic', { temporary: false })), /模式已改变/);
  assert.equal(calls.length, beforeDenied);
  await run();
  assert.deepEqual(calls.at(-1)[3], {});
  temporary = false;
  current.learningMode = 'off';
  await assert.rejects(run(input('with_memories')), /不允许使用画像/);
  await run();
  assert.deepEqual(calls.at(-1)[3], {});
  current.learningMode = 'read_only';
  await run(input('with_memories'));
  assert.deepEqual(calls.at(-1)[3], expected[2]);
  ai.getStatus = () => ({ provider: 'openai' });
  await assert.rejects(run(), /仅支持 DeepSeek/);
  ai.getStatus = () => ({ provider: 'deepseek' });

  const immediateChat = ai.chat;
  for (const change of ['revision', 'privacyEpoch', 'session']) {
    const started = deferred();
    const released = deferred();
    let valid = true;
    ai.chat = async () => { started.resolve(); await released.promise; return { text: '不得泄露的晚到试答', model: 'deepseek-test' }; };
    const pending = run(input('with_memories'), () => valid);
    const rejected = assert.rejects(pending, /已改变|安全读取/);
    await started.promise;
    if (change === 'session') valid = false;
    else current[change] += 1;
    released.resolve();
    await rejected;
  }
  ai.chat = immediateChat;
  const read = store.getState;
  store.getState = async () => { throw new Error('C:\\private-account\\private-data'); };
  await assert.rejects(run(), (error) => /无法安全读取/.test(error.message) && !error.message.includes('private-account'));
  store.getState = read;
  current = { ...structuredClone(initial), cloudConsent: true, memories: [] };
  for (const mode of simulationModes) {
    const result = await run(input(mode));
    assert.deepEqual(result.usedMemoryKeys, [], 'Insufficient evidence stays empty; no invented profile.');
  }
  console.log('Private simulation passed: three isolated configurations, consent/provider/temporary gates, no history/reference leakage, no learning or persistence, parameter limits, empty evidence, version metadata and late-result invalidation. All scenarios and replies are fictional; no network calls or quality claims.');
})().catch((error) => { console.error(error); process.exitCode = 1; });
