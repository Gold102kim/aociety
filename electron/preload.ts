import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('launcher', {
  window: {
    minimize: () => ipcRenderer.send('window:minimize'),
    toggleMaximize: () => ipcRenderer.send('window:toggle-maximize'),
    close: () => ipcRenderer.send('window:close'),
    enterCompanion: () => ipcRenderer.invoke('window:enter-companion') as Promise<{ ok: boolean; message?: string }>,
  },
  companion: {
    getState: () => ipcRenderer.invoke('companion:get-state') as Promise<{ displayName: string; agentStatus: 'WAITING_FOR_PROFILE' | 'READY'; favoriteColor: string }>,
    restore: () => ipcRenderer.send('companion:restore'),
    quit: () => ipcRenderer.send('companion:quit'),
  },
  app: {
    getVersion: () => ipcRenderer.invoke('app:get-version') as Promise<string>,
  },
  auth: {
    register: (input: { displayName: string; email: string; password: string }) =>
      ipcRenderer.invoke('auth:register', input) as Promise<AuthResult>,
    login: (input: { email: string; password: string }) =>
      ipcRenderer.invoke('auth:login', input) as Promise<AuthResult>,
    completeQuestionnaire: (input: BasicQuestionnaire) =>
      ipcRenderer.invoke('auth:complete-questionnaire', input) as Promise<AuthResult>,
    supplementProfile: (input: BasicQuestionnaire) =>
      ipcRenderer.invoke('auth:supplement-profile', input) as Promise<AuthResult>,
    logout: () => ipcRenderer.invoke('auth:logout') as Promise<{ ok: boolean }>,
  },
  ai: {
    getStatus: () => ipcRenderer.invoke('ai:get-status') as Promise<AiStatus>,
    chat: (input: { message: string; history: AiChatMessage[] }) => ipcRenderer.invoke('ai:chat', input) as Promise<AiChatResult>,
  },
  game: {
    launch: () => ipcRenderer.invoke('game:launch') as Promise<{ ok: boolean; message: string }>,
  },
});

type AuthResult =
  | { ok: true; user: LauncherUser }
  | { ok: false; message: string };

type AiChatMessage = { role: 'user' | 'assistant'; content: string };
type AiStatus = { configured: boolean; model: string; connection: 'unconfigured' | 'untested' | 'connected' | 'failed'; message?: string };
type AiChatResult =
  | { ok: true; text: string; responseId: string; model: string }
  | { ok: false; message: string };

type LauncherUser = {
  id: string;
  displayName: string;
  email: string;
  createdAt: string;
  basicQuestionnaire?: BasicQuestionnaire;
  basicQuestionnaireCompletedAt?: string;
  aiAgent: AiAgentProfile;
};

type AiAgentProfile = {
  agentId: string;
  accountId: string;
  status: 'WAITING_FOR_PROFILE' | 'READY';
  profileVersion: 1;
  createdAt: string;
  updatedAt: string;
  modelAssignment: { baseModelId: string; strategy: 'dedicated-account-model'; assignedAt: string };
  identity: { fullName: string; gender: string; birthDate: string; residence: string; occupation: string };
  personality: { mbti: string; communicationStyle: 'adaptive'; inferredTraits: Array<{ name: string; confidence: number }> };
  preferences: { interests: string[]; favoriteColor: string; favoriteMusic: string; belief: string };
  memoryNamespace: string;
  questionnaireCompletedAt?: string;
};

type BasicQuestionnaire = {
  fullName: string;
  gender: string;
  birthDate: string;
  residence: string;
  occupation: string;
  interests: string[];
  mbti: string;
  favoriteColor: string;
  favoriteMusic: string;
  belief: string;
};
