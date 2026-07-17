import { LauncherUser } from '../auth';

export function getDevelopmentPreviewUser(): LauncherUser | null {
  const parameters = new URLSearchParams(window.location.search);
  const preview = parameters.get('preview');
  if (!import.meta.env.DEV || !['profile', 'world', 'avatar', 'chat', 'social', 'boot', 'questionnaire'].includes(preview ?? '')) return null;
  const favoriteColor = parameters.get('themeColor') || '薄荷绿';
  return {
    id: 'preview-account-id', displayName: '102Gold', email: 'preview@echoverse.local', createdAt: '2026-07-15T00:00:00.000Z',
    basicQuestionnaireCompletedAt: preview === 'questionnaire' ? undefined : '2026-07-15T00:05:00.000Z',
    basicQuestionnaire: { fullName: '金哲', gender: '男性', birthDate: '2000-01-01', residence: '上海', occupation: '游戏开发者', interests: ['游戏', '音乐', '科幻'], mbti: 'INTJ', favoriteColor, favoriteMusic: '电子音乐', belief: '' },
    aiAgent: {
      agentId: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee', accountId: 'preview-account-id', status: 'READY', profileVersion: 1,
      createdAt: '2026-07-15T00:00:00.000Z', updatedAt: '2026-07-15T00:05:00.000Z',
      modelAssignment: { baseModelId: 'deepseek-v4-flash', strategy: 'shared-base-model-account-agent', assignedAt: '2026-07-15T00:00:00.000Z' },
      identity: { fullName: '金哲', gender: '男性', birthDate: '2000-01-01', residence: '上海', occupation: '游戏开发者' },
      personality: { mbti: 'INTJ', communicationStyle: 'adaptive', inferredTraits: [] },
      preferences: { interests: ['游戏', '音乐', '科幻'], favoriteColor, favoriteMusic: '电子音乐', belief: '' },
      memoryNamespace: 'agent:preview:memory', questionnaireCompletedAt: '2026-07-15T00:05:00.000Z',
    },
  };
}
