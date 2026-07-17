import fs from 'node:fs';
import path from 'node:path';
import { promisify } from 'node:util';
import { randomBytes, randomUUID, scrypt, timingSafeEqual } from 'node:crypto';

const scryptAsync = promisify(scrypt);

export type AiAgentStatus = 'WAITING_FOR_PROFILE' | 'READY';

export type AiAgentProfile = {
  agentId: string;
  accountId: string;
  status: AiAgentStatus;
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

export type PublicUser = {
  id: string;
  displayName: string;
  email: string;
  createdAt: string;
  basicQuestionnaire?: BasicQuestionnaire;
  basicQuestionnaireCompletedAt?: string;
  aiAgent: AiAgentProfile;
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

type AccountRecord = PublicUser & {
  salt: string;
  passwordHash: string;
};

type AccountDatabase = {
  version: 1;
  accounts: AccountRecord[];
};

type FailedAttempt = {
  count: number;
  blockedUntil: number;
};

const MAX_FAILED_ATTEMPTS = 5;
const BLOCK_DURATION_MS = 30_000;

function normalizeEmail(email: string) {
  return email.trim().toLowerCase();
}

function validateEmail(email: string) {
  return /^\S+@\S+\.\S+$/.test(email) && email.length <= 254;
}

function validatePassword(password: string) {
  return password.length >= 8 && password.length <= 128;
}

async function hashPassword(password: string, salt: string) {
  const result = await scryptAsync(password, salt, 64);
  return (result as Buffer).toString('hex');
}

function toPublicUser(account: AccountRecord): PublicUser {
  return {
    id: account.id,
    displayName: account.displayName,
    email: account.email,
    createdAt: account.createdAt,
    basicQuestionnaire: account.basicQuestionnaire,
    basicQuestionnaireCompletedAt: account.basicQuestionnaireCompletedAt,
    aiAgent: account.aiAgent,
  };
}

function createAiAgent(accountId: string, createdAt = new Date().toISOString()): AiAgentProfile {
  const agentId = randomUUID();
  return {
    agentId,
    accountId,
    status: 'WAITING_FOR_PROFILE',
    profileVersion: 1,
    createdAt,
    updatedAt: createdAt,
    modelAssignment: {
      baseModelId: 'deepseek-v4-flash',
      strategy: 'dedicated-account-model',
      assignedAt: createdAt,
    },
    identity: {
      fullName: '',
      gender: '',
      birthDate: '',
      residence: '',
      occupation: '',
    },
    personality: {
      mbti: '',
      communicationStyle: 'adaptive',
      inferredTraits: [],
    },
    preferences: {
      interests: [],
      favoriteColor: '',
      favoriteMusic: '',
      belief: '',
    },
    memoryNamespace: `agent:${agentId}:memory`,
  };
}

function cleanOptionalText(value: unknown, maximumLength: number) {
  if (typeof value !== 'string') return '';
  return value.trim().slice(0, maximumLength);
}

function normalizeQuestionnaire(input: BasicQuestionnaire): BasicQuestionnaire {
  const interests = Array.isArray(input.interests)
    ? [...new Set(input.interests.map((value) => cleanOptionalText(value, 40)).filter(Boolean))].slice(0, 3)
    : [];
  const birthDate = cleanOptionalText(input.birthDate, 10);
  if (birthDate && !/^\d{4}-\d{2}-\d{2}$/.test(birthDate)) throw new Error('出生日期格式不正确。');
  if (birthDate && new Date(`${birthDate}T00:00:00`).getTime() > Date.now()) throw new Error('出生日期不能晚于今天。');

  return {
    fullName: cleanOptionalText(input.fullName, 60),
    gender: cleanOptionalText(input.gender, 30),
    birthDate,
    residence: cleanOptionalText(input.residence, 100),
    occupation: cleanOptionalText(input.occupation, 80),
    interests,
    mbti: cleanOptionalText(input.mbti, 8).toUpperCase(),
    favoriteColor: cleanOptionalText(input.favoriteColor, 40),
    favoriteMusic: cleanOptionalText(input.favoriteMusic, 80),
    belief: cleanOptionalText(input.belief, 100),
  };
}

const lockedTextFields: Array<keyof Omit<BasicQuestionnaire, 'interests'>> = [
  'fullName', 'gender', 'birthDate', 'residence', 'occupation', 'mbti', 'favoriteColor', 'favoriteMusic', 'belief',
];

function mergeProfileSupplement(current: BasicQuestionnaire, input: BasicQuestionnaire): BasicQuestionnaire {
  const supplement = normalizeQuestionnaire(input);
  const merged: BasicQuestionnaire = { ...current, interests: [...current.interests] };

  for (const field of lockedTextFields) {
    const existingValue = current[field];
    const suppliedValue = supplement[field];
    if (existingValue) {
      if (suppliedValue && suppliedValue !== existingValue) throw new Error('已保存的个人资料不可修改，只能补充尚未填写的内容。');
      continue;
    }
    if (suppliedValue) merged[field] = suppliedValue;
  }

  const additions = supplement.interests.filter((interest) => !merged.interests.includes(interest));
  const remainingSlots = Math.max(0, 3 - merged.interests.length);
  if (additions.length > remainingSlots) throw new Error(`核心爱好只剩 ${remainingSlots} 个可补充位置。`);
  merged.interests.push(...additions);
  return merged;
}

function syncAgentProfile(account: AccountRecord, updatedAt: string) {
  const profile = account.basicQuestionnaire;
  if (!profile) return;
  const agent = account.aiAgent ?? createAiAgent(account.id, account.createdAt);
  agent.status = 'READY';
  agent.updatedAt = updatedAt;
  agent.questionnaireCompletedAt = account.basicQuestionnaireCompletedAt;
  agent.identity = {
    fullName: profile.fullName,
    gender: profile.gender,
    birthDate: profile.birthDate,
    residence: profile.residence,
    occupation: profile.occupation,
  };
  agent.personality = { ...agent.personality, mbti: profile.mbti };
  agent.preferences = {
    interests: profile.interests,
    favoriteColor: profile.favoriteColor,
    favoriteMusic: profile.favoriteMusic,
    belief: profile.belief,
  };
  account.aiAgent = agent;
}

export class AccountStore {
  private readonly failedAttempts = new Map<string, FailedAttempt>();

  constructor(private readonly databasePath: string) {}

  private readDatabase(): AccountDatabase {
    if (!fs.existsSync(this.databasePath)) return { version: 1, accounts: [] };
    try {
      const parsed = JSON.parse(fs.readFileSync(this.databasePath, 'utf8')) as AccountDatabase;
      if (parsed.version !== 1 || !Array.isArray(parsed.accounts)) throw new Error('Invalid account database.');
      return parsed;
    } catch {
      throw new Error('账户数据无法读取，请联系技术支持。');
    }
  }

  private writeDatabase(database: AccountDatabase) {
    fs.mkdirSync(path.dirname(this.databasePath), { recursive: true });
    const temporaryPath = `${this.databasePath}.${randomUUID()}.tmp`;
    fs.writeFileSync(temporaryPath, JSON.stringify(database, null, 2), { encoding: 'utf8', mode: 0o600 });
    fs.renameSync(temporaryPath, this.databasePath);
  }

  async register(input: { displayName: string; email: string; password: string }): Promise<PublicUser> {
    const displayName = input.displayName.trim();
    const email = normalizeEmail(input.email);
    if ([...displayName].length < 2 || [...displayName].length > 24) throw new Error('昵称需要保持在 2 到 24 个字符之间。');
    if (!validateEmail(email)) throw new Error('请输入有效的邮箱地址。');
    if (!validatePassword(input.password)) throw new Error('密码需要保持在 8 到 128 位之间。');

    const database = this.readDatabase();
    if (database.accounts.some((account) => account.email === email)) throw new Error('该邮箱已经注册。');

    const salt = randomBytes(16).toString('hex');
    const accountId = randomUUID();
    const createdAt = new Date().toISOString();
    const account: AccountRecord = {
      id: accountId,
      displayName,
      email,
      createdAt,
      salt,
      passwordHash: await hashPassword(input.password, salt),
      aiAgent: createAiAgent(accountId, createdAt),
    };
    database.accounts.push(account);
    this.writeDatabase(database);
    return toPublicUser(account);
  }

  async login(emailInput: string, password: string): Promise<PublicUser> {
    const email = normalizeEmail(emailInput);
    if (!validateEmail(email) || !validatePassword(password)) throw new Error('邮箱或密码不正确。');

    const attempt = this.failedAttempts.get(email);
    if (attempt && attempt.blockedUntil > Date.now()) {
      const seconds = Math.ceil((attempt.blockedUntil - Date.now()) / 1000);
      throw new Error(`尝试次数过多，请在 ${seconds} 秒后重试。`);
    }

    const database = this.readDatabase();
    const account = database.accounts.find((candidate) => candidate.email === email);
    const suppliedHash = await hashPassword(password, account?.salt ?? randomBytes(16).toString('hex'));
    const expectedHash = account?.passwordHash ?? randomBytes(64).toString('hex');
    const valid = timingSafeEqual(Buffer.from(suppliedHash, 'hex'), Buffer.from(expectedHash, 'hex'));

    if (!account || !valid) {
      const count = (attempt?.count ?? 0) + 1;
      this.failedAttempts.set(email, {
        count: count >= MAX_FAILED_ATTEMPTS ? 0 : count,
        blockedUntil: count >= MAX_FAILED_ATTEMPTS ? Date.now() + BLOCK_DURATION_MS : 0,
      });
      throw new Error('邮箱或密码不正确。');
    }

    this.failedAttempts.delete(email);
    if (!account.aiAgent) {
      account.aiAgent = createAiAgent(account.id, account.createdAt);
      this.writeDatabase(database);
    }
    return toPublicUser(account);
  }

  completeBasicQuestionnaire(accountId: string, input: BasicQuestionnaire): PublicUser {
    const database = this.readDatabase();
    const account = database.accounts.find((candidate) => candidate.id === accountId);
    if (!account) throw new Error('账户不存在，请重新登录。');

    if (account.basicQuestionnaireCompletedAt) throw new Error('个人资料已完成首次保存，之后只能补充未填写的内容。');

    account.basicQuestionnaire = normalizeQuestionnaire(input);
    account.basicQuestionnaireCompletedAt = new Date().toISOString();
    syncAgentProfile(account, account.basicQuestionnaireCompletedAt);
    this.writeDatabase(database);
    return toPublicUser(account);
  }

  supplementProfile(accountId: string, input: BasicQuestionnaire): PublicUser {
    const database = this.readDatabase();
    const account = database.accounts.find((candidate) => candidate.id === accountId);
    if (!account) throw new Error('账户不存在，请重新登录。');
    if (!account.basicQuestionnaire || !account.basicQuestionnaireCompletedAt) throw new Error('请先完成首次个人资料。');

    account.basicQuestionnaire = mergeProfileSupplement(account.basicQuestionnaire, input);
    syncAgentProfile(account, new Date().toISOString());
    this.writeDatabase(database);
    return toPublicUser(account);
  }
}
