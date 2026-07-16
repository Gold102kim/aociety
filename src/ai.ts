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

export async function sendAiMessage(message: string, history: ChatMessage[]) {
  const result = await requireAiApi().chat({
    message,
    history: history.map(({ role, content }) => ({ role, content })),
  });
  if (!result.ok) throw new Error(result.message);
  return result;
}
