const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { buildPersonaInstructions, AiChatService } = require('../dist-electron/ai-service.js');

const user = {
  id: 'account-test', displayName: '测试居民', email: 'test@example.com', createdAt: new Date().toISOString(),
  basicQuestionnaireCompletedAt: new Date().toISOString(),
  aiAgent: {
    agentId: 'agent-test', accountId: 'account-test', status: 'READY', profileVersion: 1,
    createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(),
    modelAssignment: { baseModelId: 'deepseek-v4-flash', strategy: 'dedicated-account-model', assignedAt: new Date().toISOString() },
    identity: { fullName: '测试姓名', gender: '女性', birthDate: '', residence: '上海', occupation: '设计师' },
    personality: { mbti: 'INFP', communicationStyle: 'adaptive', inferredTraits: [] },
    preferences: { interests: ['游戏', '音乐'], favoriteColor: '蓝色', favoriteMusic: '摇滚', belief: '' },
    memoryNamespace: 'agent:test:memory', questionnaireCompletedAt: new Date().toISOString(),
  },
};

(async function run() {
const instructions = buildPersonaInstructions(user);
assert.match(instructions, /专属数字分身 AI/);
assert.match(instructions, /INFP/);
assert.match(instructions, /设计师/);
assert.match(instructions, /游戏/);
assert.match(instructions, /不得虚构长期记忆/);

const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'echoverse-ai-'));
const originalFetch = global.fetch;
try {
  const service = new AiChatService(directory, directory, {});
  assert.equal(service.getStatus().configured, false);
  assert.equal(service.getStatus().connection, 'unconfigured');
  const ambientService = new AiChatService(directory, directory, { OPENAI_API_KEY: 'ambient-test-key' });
  assert.equal(ambientService.getStatus().configured, false);
  const dedicatedService = new AiChatService(directory, directory, { ECHOVERSE_OPENAI_API_KEY: 'echoverse-test-key' });
  assert.equal(dedicatedService.getStatus().configured, true);
  assert.equal(dedicatedService.getStatus().connection, 'untested');

  const configDirectory = path.join(directory, 'config');
  fs.mkdirSync(configDirectory, { recursive: true });
  fs.writeFileSync(path.join(configDirectory, 'ai.local.json'), JSON.stringify({
    provider: 'deepseek',
    apiKey: 'deepseek-test-key',
    model: 'deepseek-v4-flash',
    baseUrl: 'https://api.deepseek.com',
    maxOutputTokens: 400,
  }));
  let requestedUrl = '';
  let requestedBody = null;
  global.fetch = async (url, options) => {
    requestedUrl = String(url);
    requestedBody = JSON.parse(options.body);
    return {
      ok: true,
      status: 200,
      json: async () => ({ id: 'deepseek-response', model: 'deepseek-v4-flash', choices: [{ message: { content: '测试回复' } }] }),
    };
  };
  const deepseekService = new AiChatService(directory, directory, {});
  assert.equal(deepseekService.getStatus().model, 'deepseek-v4-flash');
  const result = await deepseekService.chat(user, '你好', []);
  assert.equal(requestedUrl, 'https://api.deepseek.com/chat/completions');
  assert.equal(requestedBody.model, 'deepseek-v4-flash');
  assert.equal(requestedBody.messages[0].role, 'system');
  assert.equal(result.text, '测试回复');
  assert.equal(result.model, 'deepseek-v4-flash');
} finally {
  global.fetch = originalFetch;
  fs.rmSync(directory, { recursive: true, force: true });
}

console.log('AI persona tests passed.');
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
