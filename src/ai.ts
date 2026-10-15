export type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
};

function requireAiApi() {
  if (!window.launcher?.ai) throw new Error('AI 对话只能在桌面软件中使用。');
  return window.launcher.ai;
}

export function getAiStatus() {
  return requireAiApi().getStatus();
}

export async function sendAiMessage(message: string, history: ChatMessage[], temporary: boolean, privacyEpoch: number, savedContent = false) {
  const result = await requireAiApi().chat({
    message,
    history: history.map(({ role, content }) => ({ role, content: content.slice(0, 2000) })),
    temporary,
    privacyEpoch,
    savedContent,
  });
  if (!result.ok) throw new Error(result.message);
  return result;
}
