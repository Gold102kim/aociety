/// <reference types="vite/client" />

interface Window {
  launcher?: {
    window: {
      minimize: () => void;
      toggleMaximize: () => void;
      close: () => void;
      enterCompanion: () => Promise<{ ok: boolean; message?: string }>;
    };
    companion: {
      getState: () => Promise<{ displayName: string; agentStatus: 'WAITING_FOR_PROFILE' | 'READY'; favoriteColor: string }>;
      restore: () => void;
      quit: () => void;
    };
    app: {
      getVersion: () => Promise<string>;
    };
    auth: {
      register: (input: { displayName: string; email: string; password: string }) => Promise<
        | { ok: true; user: LauncherUserData }
        | { ok: false; message: string }
      >;
      login: (input: { email: string; password: string }) => Promise<
        | { ok: true; user: LauncherUserData }
        | { ok: false; message: string }
      >;
      completeQuestionnaire: (input: BasicQuestionnaireData) => Promise<
        | { ok: true; user: LauncherUserData }
        | { ok: false; message: string }
      >;
      supplementProfile: (input: BasicQuestionnaireData) => Promise<
        | { ok: true; user: LauncherUserData }
        | { ok: false; message: string }
      >;
      logout: () => Promise<{ ok: boolean }>;
    };
    ai: {
      getStatus: () => Promise<{ configured: boolean; model: string; connection: 'unconfigured' | 'untested' | 'connected' | 'failed'; message?: string }>;
      chat: (input: { message: string; history: Array<{ role: 'user' | 'assistant'; content: string }> }) => Promise<
        | { ok: true; text: string; responseId: string; model: string }
        | { ok: false; message: string }
      >;
    };
    game: {
      launch: () => Promise<{ ok: boolean; message: string }>;
    };
  };
}

interface BasicQuestionnaireData {
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
}

interface LauncherUserData {
  id: string;
  displayName: string;
  email: string;
  createdAt: string;
  basicQuestionnaire?: BasicQuestionnaireData;
  basicQuestionnaireCompletedAt?: string;
  aiAgent: AiAgentProfileData;
}

interface AiAgentProfileData {
  agentId: string;
  accountId: string;
  status: 'WAITING_FOR_PROFILE' | 'READY';
  profileVersion: 1;
  createdAt: string;
  updatedAt: string;
  modelAssignment: { baseModelId: string; strategy: 'shared-base-model-account-agent' | 'dedicated-account-model'; assignedAt: string };
  identity: { fullName: string; gender: string; birthDate: string; residence: string; occupation: string };
  personality: { mbti: string; communicationStyle: 'adaptive'; inferredTraits: Array<{ name: string; confidence: number }> };
  preferences: { interests: string[]; favoriteColor: string; favoriteMusic: string; belief: string };
  memoryNamespace: string;
  questionnaireCompletedAt?: string;
}
