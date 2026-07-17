export type LauncherUser = {
  id: string;
  displayName: string;
  email: string;
  createdAt: string;
  basicQuestionnaire?: BasicQuestionnaire;
  basicQuestionnaireCompletedAt?: string;
  aiAgent: AiAgentProfile;
};

export type AiAgentProfile = {
  agentId: string;
  accountId: string;
  status: 'WAITING_FOR_PROFILE' | 'READY';
  profileVersion: 1;
  createdAt: string;
  updatedAt: string;
  modelAssignment: {
    baseModelId: string;
    strategy: 'dedicated-account-model';
    assignedAt: string;
  };
  identity: {
    fullName: string;
    gender: string;
    birthDate: string;
    residence: string;
    occupation: string;
  };
  personality: {
    mbti: string;
    communicationStyle: 'adaptive';
    inferredTraits: Array<{ name: string; confidence: number }>;
  };
  preferences: {
    interests: string[];
    favoriteColor: string;
    favoriteMusic: string;
    belief: string;
  };
  memoryNamespace: string;
  questionnaireCompletedAt?: string;
};

export type BasicQuestionnaire = {
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

function requireAuthApi() {
  if (!window.launcher?.auth) throw new Error('账户服务只能在桌面软件中使用。');
  return window.launcher.auth;
}

export async function register(input: {
  displayName: string;
  email: string;
  password: string;
}): Promise<LauncherUser> {
  const result = await requireAuthApi().register(input);
  if (!result.ok) throw new Error(result.message);
  return result.user;
}

export async function login(email: string, password: string): Promise<LauncherUser> {
  const result = await requireAuthApi().login({ email, password });
  if (!result.ok) throw new Error(result.message);
  return result.user;
}

export async function completeQuestionnaire(input: BasicQuestionnaire): Promise<LauncherUser> {
  const result = await requireAuthApi().completeQuestionnaire(input);
  if (!result.ok) throw new Error(result.message);
  return result.user;
}

export async function supplementProfile(input: BasicQuestionnaire): Promise<LauncherUser> {
  const result = await requireAuthApi().supplementProfile(input);
  if (!result.ok) throw new Error(result.message);
  return result.user;
}

export async function signOut() {
  await requireAuthApi().logout();
}
