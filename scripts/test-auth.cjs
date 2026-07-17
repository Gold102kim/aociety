const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { AccountStore } = require('../dist-electron/auth-service.js');

function questionnaire(overrides = {}) {
  return {
    fullName: '',
    gender: '',
    birthDate: '',
    residence: '',
    occupation: '',
    interests: [],
    mbti: '',
    favoriteColor: '',
    favoriteMusic: '',
    belief: '',
    ...overrides,
  };
}

async function run() {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'echoverse-auth-'));
  const databasePath = path.join(directory, 'accounts.json');
  const store = new AccountStore(databasePath);

  try {
    const registered = await store.register({
      displayName: '测试居民',
      email: 'Player@Example.com',
      password: 'EchoVerse2026!',
    });
    assert.equal(registered.email, 'player@example.com');
    assert.equal(registered.displayName, '测试居民');
    assert.equal(registered.basicQuestionnaireCompletedAt, undefined);
    assert.equal(registered.aiAgent.accountId, registered.id);
    assert.equal(registered.aiAgent.status, 'WAITING_FOR_PROFILE');
    assert.equal(registered.aiAgent.modelAssignment.baseModelId, 'deepseek-v4-flash');
    assert.equal(registered.aiAgent.modelAssignment.strategy, 'shared-base-model-account-agent');
    assert.match(registered.aiAgent.memoryNamespace, new RegExp(registered.aiAgent.agentId));

    await assert.rejects(
      () => store.register({ displayName: '另一位玩家', email: 'player@example.com', password: 'EchoVerse2026!' }),
      /已经注册/,
    );
    await assert.rejects(() => store.login('player@example.com', 'WrongPassword!'), /邮箱或密码不正确/);

    const loggedIn = await store.login('PLAYER@example.com', 'EchoVerse2026!');
    assert.equal(loggedIn.id, registered.id);

    const completed = await store.completeBasicQuestionnaire(registered.id, questionnaire({
      fullName: '测试姓名',
      gender: '不填写',
      birthDate: '2000-01-02',
      residence: '上海',
      occupation: '设计师',
      interests: ['游戏', '音乐', ''],
      mbti: 'infp',
      favoriteColor: '蓝色',
      favoriteMusic: '摇滚',
      belief: '',
    }));
    assert.ok(completed.basicQuestionnaireCompletedAt);
    assert.deepEqual(completed.basicQuestionnaire.interests, ['游戏', '音乐']);
    assert.equal(completed.basicQuestionnaire.mbti, 'INFP');
    assert.equal(completed.aiAgent.agentId, registered.aiAgent.agentId);
    assert.equal(completed.aiAgent.status, 'READY');
    assert.equal(completed.aiAgent.identity.occupation, '设计师');
    assert.equal(completed.aiAgent.personality.mbti, 'INFP');
    assert.deepEqual(completed.aiAgent.preferences.interests, ['游戏', '音乐']);

    await assert.rejects(
      () => store.completeBasicQuestionnaire(registered.id, questionnaire({ fullName: '尝试覆盖' })),
      /只能补充未填写/,
    );

    const supplemented = await store.supplementProfile(registered.id, questionnaire({
      interests: ['旅行'],
      belief: '人文主义',
    }));
    assert.equal(supplemented.basicQuestionnaire.fullName, '测试姓名');
    assert.equal(supplemented.basicQuestionnaire.belief, '人文主义');
    assert.deepEqual(supplemented.basicQuestionnaire.interests, ['游戏', '音乐', '旅行']);
    assert.equal(supplemented.aiAgent.preferences.belief, '人文主义');
    assert.deepEqual(supplemented.aiAgent.preferences.interests, ['游戏', '音乐', '旅行']);

    await assert.rejects(
      () => store.supplementProfile(registered.id, questionnaire({ fullName: '另一个姓名' })),
      /不可修改/,
    );

    const invalidDateAccount = await store.register({
      displayName: '日期测试',
      email: 'date@example.com',
      password: 'EchoVerse2026!',
    });
    await assert.rejects(
      () => store.completeBasicQuestionnaire(invalidDateAccount.id, questionnaire({ birthDate: '2023-02-29' })),
      /出生日期不存在/,
    );
    const invalidDateAccountAfterFailure = await store.login('date@example.com', 'EchoVerse2026!');
    assert.equal(invalidDateAccountAfterFailure.basicQuestionnaireCompletedAt, undefined);

    const concurrentInputs = Array.from({ length: 8 }, (_, index) => ({
      displayName: `并发玩家${index + 1}`,
      email: `parallel-${index + 1}@example.com`,
      password: 'EchoVerse2026!',
    }));
    const concurrentUsers = await Promise.all(concurrentInputs.map((input) => store.register(input)));
    assert.equal(new Set(concurrentUsers.map((user) => user.id)).size, concurrentInputs.length);

    const databaseAfterConcurrentRegistration = JSON.parse(fs.readFileSync(databasePath, 'utf8'));
    const persistedEmails = new Set(databaseAfterConcurrentRegistration.accounts.map((account) => account.email));
    for (const input of concurrentInputs) assert.ok(persistedEmails.has(input.email));
    assert.equal(databaseAfterConcurrentRegistration.accounts.length, concurrentInputs.length + 2);

    const databaseWithLegacyAgentStrategy = JSON.parse(fs.readFileSync(databasePath, 'utf8'));
    const legacyStrategyAccount = databaseWithLegacyAgentStrategy.accounts.find((account) => account.id === registered.id);
    assert.ok(legacyStrategyAccount);
    legacyStrategyAccount.aiAgent.modelAssignment.strategy = 'dedicated-account-model';
    fs.writeFileSync(databasePath, JSON.stringify(databaseWithLegacyAgentStrategy, null, 2));

    const loggedInAfterQuestionnaire = await store.login('player@example.com', 'EchoVerse2026!');
    assert.ok(loggedInAfterQuestionnaire.basicQuestionnaireCompletedAt);
    assert.equal(loggedInAfterQuestionnaire.basicQuestionnaire.residence, '上海');
    assert.equal(loggedInAfterQuestionnaire.aiAgent.agentId, registered.aiAgent.agentId);
    assert.equal(loggedInAfterQuestionnaire.aiAgent.modelAssignment.strategy, 'shared-base-model-account-agent');

    const database = JSON.parse(fs.readFileSync(databasePath, 'utf8'));
    const storedAccount = database.accounts.find((account) => account.id === registered.id);
    assert.ok(storedAccount);
    assert.equal(storedAccount.password, undefined);
    assert.notEqual(storedAccount.passwordHash, 'EchoVerse2026!');
    assert.deepEqual(storedAccount.passwordKdf, { algorithm: 'scrypt', keyLength: 64, saltBytes: 16 });
    assert.equal(storedAccount.basicQuestionnaire.occupation, '设计师');
    assert.equal(storedAccount.aiAgent.status, 'READY');
    assert.equal(storedAccount.aiAgent.modelAssignment.strategy, 'shared-base-model-account-agent');

    assert.ok(fs.existsSync(`${databasePath}.bak`));
    fs.writeFileSync(databasePath, '{corrupted-json');
    const recoveredUser = await store.login('player@example.com', 'EchoVerse2026!');
    assert.equal(recoveredUser.id, registered.id);
    const recoveredDatabase = JSON.parse(fs.readFileSync(databasePath, 'utf8'));
    assert.ok(recoveredDatabase.accounts.some((account) => account.id === registered.id));
    console.log('Auth tests passed.');
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
