// Runtime-only mock, injected by development tests or the local package harness.
// This file is excluded from the application archive.
module.exports = function installRepresentativeTransport() {
  global.__representativeRequests = [];
  global.fetch = async (url, options) => {
    if (String(url) !== 'https://api.deepseek.com/chat/completions') throw new Error('UI smoke test blocks all external requests.');
    const body = JSON.parse(options.body);
    global.__representativeRequests.push(body);
    const message = body.messages.at(-1).content;
    const simulation = body.messages[0].content.includes('private-simulation-v1');
    if (message === '角色扮演：失败回复测试') throw new Error('隔离测试：对话服务暂不可用。');
    if (simulation && message === '失败试答测试' && !global.__simulationFailedOnce) {
      global.__simulationFailedOnce = true;
      throw new Error('隔离测试：模拟服务暂不可用。');
    }
    if (message === '延迟回复测试') await new Promise((resolve, reject) => {
      global.__releaseRepresentativeReply = resolve;
      global.__rejectRepresentativeReply = reject;
    });
    const facts = simulation ? JSON.parse(body.messages[0].content.split('PERSONA_FACTS:\n')[1]) : null;
    const text = message === '延迟回复测试' ? '不应显示的晚到回复' : simulation
      ? `隔离测试试答：${Object.values(facts.preferences).join('、') || '不使用画像'}。不是真实模型输出。` : '这是隔离测试回复，不是真实模型输出。';
    return new Response(JSON.stringify({ id: `mock-${global.__representativeRequests.length}`, model: 'deepseek-test',
      choices: [{ message: { content: text } }] }), { status: 200 });
  };
};
