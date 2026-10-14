import type { ChatMessage } from './ai';

export function getRecentChatHistory(messages: ChatMessage[]) {
  return messages.filter((message) => message.id !== 'welcome').slice(-12);
}

export function isChatSendShortcut(event: { key: string; ctrlKey: boolean; metaKey: boolean; isComposing: boolean }) {
  return event.key === 'Enter' && (event.ctrlKey || event.metaKey) && !event.isComposing;
}
