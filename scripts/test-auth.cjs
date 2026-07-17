const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { AccountStore } = require('../dist-electron/auth-service.js');

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
    assert.equal(registered.aiAgent.modelAssignment.baseModelId, 'echo-persona-v1');
    assert.match(registered.aiAgent.memoryNamespace, new RegExp(registered.aiAgent.agentId));

    await assert.rejects(
      () => store.register({ displayName: '另一位玩家', email: 'player@example.com', password: 'EchoVerse2026!' }),
      /已经注册/,
    );
    await assert.rejects(() => store.login('player@example.com', 'WrongPassword!'), /邮箱或密码不正确/);

    const loggedIn = await store.login('PLAYER@example.com', 'EchoVerse2026!');
    assert.equal(loggedIn.id, registered.id);

    const completed = store.completeBasicQuestionnaire(registered.id, {
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
    });
    assert.ok(completed.basicQuestionnaireCompletedAt);
    assert.deepEqual(completed.basicQuestionnaire.interests, ['游戏', '音乐']);
    assert.equal(completed.basicQuestionnaire.mbti, 'INFP');
    assert.equal(completed.aiAgent.agentId, registered.aiAgent.agentId);
    assert.equal(completed.aiAgent.status, 'READY');
    assert.equal(completed.aiAgent.identity.occupation, '设计师');
    assert.equal(completed.aiAgent.personality.mbti, 'INFP');
    assert.deepEqual(completed.aiAgent.preferences.interests, ['游戏', '音乐']);

    assert.throws(
      () => store.completeBasicQuestionnaire(registered.id, {
        fullName: '尝试覆盖', gender: '', birthDate: '', residence: '', occupation: '', interests: [], mbti: '', favoriteColor: '', favoriteMusic: '', belief: '',
      }),
      /只能补充未填写/,
    );

    const supplemented = store.supplementProfile(registered.id, {
      fullName: '',
      gender: '',
      birthDate: '',
      residence: '',
      occupation: '',
      interests: ['旅行'],
      mbti: '',
      favoriteColor: '',
      favoriteMusic: '',
      belief: '人文主义',
    });
    assert.equal(supplemented.basicQuestionnaire.fullName, '测试姓名');
    assert.equal(supplemented.basicQuestionnaire.belief, '人文主义');
    assert.deepEqual(supplemented.basicQuestionnaire.interests, ['游戏', '音乐', '旅行']);
    assert.equal(supplemented.aiAgent.preferences.belief, '人文主义');
    assert.deepEqual(supplemented.aiAgent.preferences.interests, ['游戏', '音乐', '旅行']);

    assert.throws(
      () => store.supplementProfile(registered.id, {
        fullName: '另一个姓名', gender: '', birthDate: '', residence: '', occupation: '', interests: [], mbti: '', favoriteColor: '', favoriteMusic: '', belief: '',
      }),
      /不可修改/,
    );

    const loggedInAfterQuestionnaire = await store.login('player@example.com', 'EchoVerse2026!');
    assert.ok(loggedInAfterQuestionnaire.basicQuestionnaireCompletedAt);
    assert.equal(loggedInAfterQuestionnaire.basicQuestionnaire.residence, '上海');
    assert.equal(loggedInAfterQuestionnaire.aiAgent.agentId, registered.aiAgent.agentId);

    const database = JSON.parse(fs.readFileSync(databasePath, 'utf8'));
    assert.equal(database.accounts[0].password, undefined);
    assert.notEqual(database.accounts[0].passwordHash, 'EchoVerse2026!');
    assert.equal(database.accounts[0].basicQuestionnaire.occupation, '设计师');
    assert.equal(database.accounts[0].aiAgent.status, 'READY');
    console.log('Auth tests passed.');
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
