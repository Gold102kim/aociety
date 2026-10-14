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
    identity: { fullName: '测试姓名', gender: '女性', birthDate: '2000-01-02', residence: '上海', occupation: '设计师' },
    personality: { mbti: 'INFP', communicationStyle: 'adaptive', inferredTraits: [] },
    preferences: { interests: ['游戏', '音乐'], favoriteColor: '蓝色', favoriteMusic: '摇滚', belief: '私人信仰' },
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
assert.doesNotMatch(instructions, /测试姓名/);
assert.doesNotMatch(instructions, /2000-01-02/);
assert.doesNotMatch(instructions, /上海/);
assert.doesNotMatch(instructions, /私人信仰/);

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

  const insecureOpenAiService = new AiChatService(directory, directory, {
    ECHOVERSE_OPENAI_API_KEY: 'echoverse-test-key',
    ECHOVERSE_OPENAI_BASE_URL: 'http://api.openai.com/v1',
  });
  assert.equal(insecureOpenAiService.getStatus().configured, false);
  assert.equal(insecureOpenAiService.getStatus().connection, 'failed');
  assert.match(insecureOpenAiService.getStatus().message, /官方 HTTPS 地址/);

  const spoofedOpenAiService = new AiChatService(directory, directory, {
    ECHOVERSE_OPENAI_API_KEY: 'echoverse-test-key',
    ECHOVERSE_OPENAI_BASE_URL: 'https://api.openai.com.attacker.example/v1',
  });
  assert.equal(spoofedOpenAiService.getStatus().configured, false);
  assert.match(spoofedOpenAiService.getStatus().message, /官方 HTTPS 地址/);

  const configDirectory = path.join(directory, 'config');
  fs.mkdirSync(configDirectory, { recursive: true });
  const configPath = path.join(configDirectory, 'ai.local.json');
  const writeConfig = (config) => fs.writeFileSync(configPath, JSON.stringify(config));
  writeConfig({
    provider: 'deepseek',
    apiKey: 'deepseek-test-key',
    model: 'deepseek-v4-flash',
    baseUrl: 'https://api.deepseek.com',
    maxOutputTokens: 400,
  });
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

  writeConfig({
    provider: 'deepseek',
    apiKey: 'deepseek-test-key',
    model: 'deepseek-v4-flash',
    baseUrl: 'https://api.deepseek.com.attacker.example',
  });
  const spoofedDeepSeekService = new AiChatService(directory, directory, {});
  assert.equal(spoofedDeepSeekService.getStatus().configured, false);
  await assert.rejects(
    spoofedDeepSeekService.chat(user, '你好', []),
    /官方 HTTPS 地址/,
  );

  let openAiRequestBody = null;
  global.fetch = async (url, options) => {
    requestedUrl = String(url);
    openAiRequestBody = JSON.parse(options.body);
    return {
      ok: true,
      status: 200,
      json: async () => ({
        id: 'openai-response',
        model: 'gpt-test-model',
        output: [{ type: 'message', content: [{ type: 'output_text', text: 'OpenAI 测试回复' }] }],
      }),
    };
  };
  const openAiService = new AiChatService(directory, directory, {
    ECHOVERSE_OPENAI_API_KEY: 'echoverse-test-key',
    ECHOVERSE_OPENAI_MODEL: 'gpt-test-model',
  });
  const openAiResult = await openAiService.chat(user, '你好', []);
  assert.equal(requestedUrl, 'https://api.openai.com/v1/responses');
  assert.equal(openAiRequestBody.model, 'gpt-test-model');
  assert.notEqual(openAiRequestBody.model, user.aiAgent.modelAssignment.baseModelId);
  assert.equal(openAiResult.text, 'OpenAI 测试回复');

  let mismatchFetchCalled = false;
  global.fetch = async () => {
    mismatchFetchCalled = true;
    throw new Error('不应发起请求');
  };
  const mismatchedOpenAiService = new AiChatService(directory, directory, {
    ECHOVERSE_OPENAI_API_KEY: 'echoverse-test-key',
    ECHOVERSE_OPENAI_MODEL: 'deepseek-v4-flash',
  });
  assert.equal(mismatchedOpenAiService.getStatus().configured, false);
  await assert.rejects(
    mismatchedOpenAiService.chat(user, '你好', []),
    /OpenAI 服务不能使用 DeepSeek 模型/,
  );
  assert.equal(mismatchFetchCalled, false);

  writeConfig({
    provider: 'deepseek',
    apiKey: 'deepseek-test-key',
    model: 'deepseek-v4-flash',
    baseUrl: 'https://api.deepseek.com',
  });
  let releaseFirstRequest;
  let concurrentFetchCount = 0;
  global.fetch = async () => {
    concurrentFetchCount += 1;
    if (concurrentFetchCount === 1) {
      return new Promise((resolve) => {
        releaseFirstRequest = () => resolve({
          ok: true,
          status: 200,
          json: async () => ({ choices: [{ message: { content: '首条回复' } }] }),
        });
      });
    }
    return {
      ok: true,
      status: 200,
      json: async () => ({ choices: [{ message: { content: '释放后的回复' } }] }),
    };
  };
  const concurrentService = new AiChatService(directory, directory, {});
  const firstRequest = concurrentService.chat(user, '第一条', []);
  assert.equal(typeof releaseFirstRequest, 'function');
  await assert.rejects(
    concurrentService.chat(user, '重叠请求', []),
    /上一条消息仍在处理中/,
  );
  assert.equal(concurrentFetchCount, 1);
  releaseFirstRequest();
  assert.equal((await firstRequest).text, '首条回复');
  assert.equal((await concurrentService.chat(user, '下一条', [])).text, '释放后的回复');

  const cancellable = new AiChatService(directory, directory, {});
  const pendingReplies = [];
  global.fetch = async (_url, options) => new Promise((resolve) => {
    pendingReplies.push({ signal: options.signal, resolve });
  });
  const oldReply = cancellable.chat(user, '退出前的消息', []);
  const oldRejected = assert.rejects(oldReply, /已取消/);
  cancellable.cancelAccount(user.id);
  assert.equal(pendingReplies[0].signal.aborted, true, 'Logout must abort the actual HTTP signal.');
  const freshReply = cancellable.chat(user, '重新登录后的消息', [null, { role: 'system', content: 'unsafe history' }, { role: 'assistant', content: 'valid history' }]);
  pendingReplies[0].resolve({ ok: true, status: 200, json: async () => ({ choices: [{ message: { content: '旧的私密回复' } }] }) });
  await oldRejected;
  await assert.rejects(cancellable.chat(user, '仍在等待新消息', []), /上一条消息仍在处理中/, 'Old cleanup must not release the new request slot.');
  pendingReplies[1].resolve({ ok: true, status: 200, json: async () => ({ choices: [{ message: { content: '新的回复' } }] }) });
  assert.equal((await freshReply).text, '新的回复');
  assert.equal(cancellable.getStatus().connection, 'connected');
  const cancelAllReply = cancellable.chat(user, '应用关闭前的消息', []);
  const cancelAllRejected = assert.rejects(cancelAllReply, /已取消/);
  cancellable.cancelAll();
  assert.equal(pendingReplies[2].signal.aborted, true);
  pendingReplies[2].resolve({ ok: true, status: 200, json: async () => ({ choices: [{ message: { content: '不应返回' } }] }) });
  await cancelAllRejected;
  assert.equal(cancellable.getStatus().connection, 'connected', 'Intentional cancellation must not mark the service disconnected.');

  let cleanedHistory;
  global.fetch = async (_url, options) => {
    cleanedHistory = JSON.parse(options.body).messages;
    return { ok: true, status: 200, json: async () => ({ choices: [{ message: { content: '合法回复' } }] }) };
  };
  await new AiChatService(directory, directory, {}).chat(user, '测试异常历史', [null, false, { role: 'system', content: 'ignored' }, { role: 'assistant', content: '合法历史' }]);
  assert.equal(cleanedHistory.length, 3, 'Only system persona, valid history and latest message may be forwarded.');
  assert.equal(cleanedHistory[1].content, '合法历史');
  global.fetch = async () => ({ ok: false, status: 401, json: async () => ({ error: { message: 'Bearer deepseek-test-key internal private data' } }) });
  const safeErrorService = new AiChatService(directory, directory, {});
  await assert.rejects(safeErrorService.chat(user, '测试安全错误', []), /HTTP 401/);
  assert.doesNotMatch(safeErrorService.getStatus().message, /deepseek-test-key|private data/);
  global.fetch = async () => { throw new Error('transport included deepseek-test-key'); };
  await assert.rejects(safeErrorService.chat(user, '测试凭据掩码', []), /已隐藏凭据/);
  assert.doesNotMatch(safeErrorService.getStatus().message, /deepseek-test-key/);

  let failOnce = true;
  global.fetch = async () => {
    if (failOnce) {
      failOnce = false;
      throw new Error('模拟上游失败');
    }
    return {
      ok: true,
      status: 200,
      json: async () => ({ choices: [{ message: { content: '失败后恢复' } }] }),
    };
  };
  const failureReleaseService = new AiChatService(directory, directory, {});
  await assert.rejects(failureReleaseService.chat(user, '触发失败', []), /模拟上游失败/);
  assert.equal((await failureReleaseService.chat(user, '失败后重试', [])).text, '失败后恢复');

  let rateLimitedFetchCount = 0;
  global.fetch = async () => {
    rateLimitedFetchCount += 1;
    return {
      ok: true,
      status: 200,
      json: async () => ({ choices: [{ message: { content: '限流测试回复' } }] }),
    };
  };
  const rateLimitedService = new AiChatService(directory, directory, {});
  for (let index = 0; index < 12; index += 1) {
    await rateLimitedService.chat(user, `消息 ${index}`, []);
  }
  await assert.rejects(rateLimitedService.chat(user, '第十三条', []), /请求过于频繁/);
  assert.equal(rateLimitedFetchCount, 12);
} finally {
  global.fetch = originalFetch;
  fs.rmSync(directory, { recursive: true, force: true });
}

console.log('AI persona tests passed.');
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
