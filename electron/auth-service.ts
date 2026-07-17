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
    strategy: 'shared-base-model-account-agent' | 'dedicated-account-model';
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
  passwordKdf?: {
    algorithm: 'scrypt';
    keyLength: 64;
    saltBytes: 16;
  };
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
const MAX_PENDING_OPERATIONS = 32;
const MAX_CRYPTO_OPERATIONS_PER_WINDOW = 20;
const CRYPTO_RATE_WINDOW_MS = 10_000;
const PASSWORD_KDF = { algorithm: 'scrypt', keyLength: 64, saltBytes: 16 } as const;

function normalizeEmail(email: string) {
  return email.trim().toLowerCase();
}

function validateEmail(email: string) {
  return /^\S+@\S+\.\S+$/.test(email) && email.length <= 254;
}

function validatePassword(password: string) {
  return typeof password === 'string' && password.length >= 8 && password.length <= 128;
}

async function hashPassword(password: string, salt: string) {
  const result = await scryptAsync(password, salt, PASSWORD_KDF.keyLength);
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
      strategy: 'shared-base-model-account-agent',
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
  const source = (input && typeof input === 'object' ? input : {}) as Partial<BasicQuestionnaire>;
  const interests = Array.isArray(source.interests)
    ? [...new Set(source.interests.map((value) => cleanOptionalText(value, 40)).filter(Boolean))].slice(0, 3)
    : [];
  const birthDate = cleanOptionalText(source.birthDate, 10);
  if (birthDate && !/^\d{4}-\d{2}-\d{2}$/.test(birthDate)) throw new Error('出生日期格式不正确。');
  if (birthDate) {
    const [year, month, day] = birthDate.split('-').map(Number);
    const parsed = new Date(Date.UTC(year, month - 1, day));
    const validCalendarDate = parsed.getUTCFullYear() === year
      && parsed.getUTCMonth() === month - 1
      && parsed.getUTCDate() === day;
    if (!validCalendarDate) throw new Error('出生日期不存在。');
    if (parsed.getTime() > Date.now()) throw new Error('出生日期不能晚于今天。');
  }

  return {
    fullName: cleanOptionalText(source.fullName, 60),
    gender: cleanOptionalText(source.gender, 30),
    birthDate,
    residence: cleanOptionalText(source.residence, 100),
    occupation: cleanOptionalText(source.occupation, 80),
    interests,
    mbti: cleanOptionalText(source.mbti, 8).toUpperCase(),
    favoriteColor: cleanOptionalText(source.favoriteColor, 40),
    favoriteMusic: cleanOptionalText(source.favoriteMusic, 80),
    belief: cleanOptionalText(source.belief, 100),
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isQuestionnaireRecord(value: unknown): value is BasicQuestionnaire {
  if (!isRecord(value)) return false;
  const textFields = ['fullName', 'gender', 'birthDate', 'residence', 'occupation', 'mbti', 'favoriteColor', 'favoriteMusic', 'belief'];
  return textFields.every((field) => typeof value[field] === 'string')
    && Array.isArray(value.interests)
    && value.interests.length <= 3
    && value.interests.every((item) => typeof item === 'string');
}

function isAiAgentRecord(value: unknown, accountId: string): value is AiAgentProfile {
  if (!isRecord(value) || value.accountId !== accountId || typeof value.agentId !== 'string') return false;
  if (value.status !== 'WAITING_FOR_PROFILE' && value.status !== 'READY') return false;
  if (value.profileVersion !== 1 || typeof value.createdAt !== 'string' || typeof value.updatedAt !== 'string') return false;
  const assignment = value.modelAssignment;
  const identity = value.identity;
  const personality = value.personality;
  const preferences = value.preferences;
  if (!isRecord(assignment) || typeof assignment.baseModelId !== 'string' || typeof assignment.assignedAt !== 'string') return false;
  if (assignment.strategy !== 'dedicated-account-model' && assignment.strategy !== 'shared-base-model-account-agent') return false;
  if (!isRecord(identity) || !['fullName', 'gender', 'birthDate', 'residence', 'occupation'].every((field) => typeof identity[field] === 'string')) return false;
  if (!isRecord(personality) || typeof personality.mbti !== 'string' || personality.communicationStyle !== 'adaptive' || !Array.isArray(personality.inferredTraits)) return false;
  if (!isRecord(preferences) || typeof preferences.favoriteColor !== 'string' || typeof preferences.favoriteMusic !== 'string' || typeof preferences.belief !== 'string') return false;
  return Array.isArray(preferences.interests) && preferences.interests.every((item) => typeof item === 'string') && typeof value.memoryNamespace === 'string';
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
  private operationQueue: Promise<void> = Promise.resolve();
  private pendingOperations = 0;
  private recentCryptoOperations: number[] = [];

  constructor(private readonly databasePath: string) {}

  private parseDatabase(filePath: string): AccountDatabase {
    const parsed = JSON.parse(fs.readFileSync(filePath, 'utf8')) as AccountDatabase;
    if (parsed.version !== 1 || !Array.isArray(parsed.accounts)) throw new Error('Invalid account database.');
    const accountIds = new Set<string>();
    const accountEmails = new Set<string>();
    for (const account of parsed.accounts) {
      if (!account || typeof account.id !== 'string' || typeof account.displayName !== 'string' || typeof account.email !== 'string' || typeof account.createdAt !== 'string') throw new Error('Invalid account record.');
      if (!/^[a-f0-9]{32}$/i.test(account.salt) || !/^[a-f0-9]{128}$/i.test(account.passwordHash)) throw new Error('Invalid password record.');
      if (account.passwordKdf && (account.passwordKdf.algorithm !== 'scrypt' || account.passwordKdf.keyLength !== 64 || account.passwordKdf.saltBytes !== 16)) throw new Error('Unsupported password record.');
      const normalizedEmail = normalizeEmail(account.email);
      if (!validateEmail(normalizedEmail) || accountIds.has(account.id) || accountEmails.has(normalizedEmail)) throw new Error('Duplicate or invalid account identity.');
      account.id = account.id.trim();
      account.email = normalizedEmail;
      accountIds.add(account.id);
      accountEmails.add(account.email);
      if (account.basicQuestionnaire !== undefined && !isQuestionnaireRecord(account.basicQuestionnaire)) throw new Error('Invalid questionnaire record.');
      if (account.basicQuestionnaireCompletedAt && !account.basicQuestionnaire) throw new Error('Incomplete questionnaire record.');
      if (account.aiAgent !== undefined && !isAiAgentRecord(account.aiAgent, account.id)) throw new Error('Invalid AI agent record.');
    }
    return parsed;
  }

  private readDatabase(): AccountDatabase {
    if (!fs.existsSync(this.databasePath)) return { version: 1, accounts: [] };
    try {
      return this.parseDatabase(this.databasePath);
    } catch {
      const backupPath = `${this.databasePath}.bak`;
      if (fs.existsSync(backupPath)) {
        try {
          const recovered = this.parseDatabase(backupPath);
          try {
            fs.copyFileSync(backupPath, this.databasePath);
          } catch {
            // The validated backup can still serve this operation if repair is not writable.
          }
          return recovered;
        } catch {
          // The primary and backup copies are both invalid.
        }
      }
      throw new Error('账户数据无法读取，请联系技术支持。');
    }
  }

  private writeDatabase(database: AccountDatabase) {
    fs.mkdirSync(path.dirname(this.databasePath), { recursive: true });
    const temporaryPath = `${this.databasePath}.${randomUUID()}.tmp`;
    try {
      const handle = fs.openSync(temporaryPath, 'w', 0o600);
      try {
        fs.writeFileSync(handle, JSON.stringify(database, null, 2), { encoding: 'utf8' });
        fs.fsyncSync(handle);
      } finally {
        fs.closeSync(handle);
      }
      if (fs.existsSync(this.databasePath)) {
        try {
          this.parseDatabase(this.databasePath);
          fs.copyFileSync(this.databasePath, `${this.databasePath}.bak`);
        } catch {
          // Never replace a known-good backup with a corrupted primary file.
        }
      }
      fs.renameSync(temporaryPath, this.databasePath);
    } finally {
      if (fs.existsSync(temporaryPath)) fs.rmSync(temporaryPath, { force: true });
    }
  }

  private async serialized<T>(operation: () => Promise<T> | T): Promise<T> {
    if (this.pendingOperations >= MAX_PENDING_OPERATIONS) throw new Error('账户服务当前请求过多，请稍后重试。');
    this.pendingOperations += 1;
    const previous = this.operationQueue;
    let release!: () => void;
    this.operationQueue = new Promise<void>((resolve) => { release = resolve; });
    await previous;
    try {
      return await operation();
    } finally {
      this.pendingOperations -= 1;
      release();
    }
  }

  private consumeCryptoBudget() {
    const threshold = Date.now() - CRYPTO_RATE_WINDOW_MS;
    this.recentCryptoOperations = this.recentCryptoOperations.filter((timestamp) => timestamp > threshold);
    if (this.recentCryptoOperations.length >= MAX_CRYPTO_OPERATIONS_PER_WINDOW) throw new Error('账户验证请求过于频繁，请稍后重试。');
    this.recentCryptoOperations.push(Date.now());
  }

  async register(input: { displayName: string; email: string; password: string }): Promise<PublicUser> {
    return this.serialized(async () => {
      const displayName = typeof input?.displayName === 'string' ? input.displayName.trim() : '';
      const email = normalizeEmail(typeof input?.email === 'string' ? input.email : '');
      const password = typeof input?.password === 'string' ? input.password : '';
      if ([...displayName].length < 2 || [...displayName].length > 24) throw new Error('昵称需要保持在 2 到 24 个字符之间。');
      if (!validateEmail(email)) throw new Error('请输入有效的邮箱地址。');
      if (!validatePassword(password)) throw new Error('密码需要保持在 8 到 128 位之间。');

      const database = this.readDatabase();
      if (database.accounts.some((account) => account.email === email)) throw new Error('该邮箱已经注册。');
      this.consumeCryptoBudget();

      const salt = randomBytes(PASSWORD_KDF.saltBytes).toString('hex');
      const accountId = randomUUID();
      const createdAt = new Date().toISOString();
      const account: AccountRecord = {
        id: accountId,
        displayName,
        email,
        createdAt,
        salt,
        passwordHash: await hashPassword(password, salt),
        passwordKdf: PASSWORD_KDF,
        aiAgent: createAiAgent(accountId, createdAt),
      };
      database.accounts.push(account);
      this.writeDatabase(database);
      return toPublicUser(account);
    });
  }

  async login(emailInput: string, password: string): Promise<PublicUser> {
    return this.serialized(async () => {
      const email = normalizeEmail(typeof emailInput === 'string' ? emailInput : '');
      const suppliedPassword = typeof password === 'string' ? password : '';
      if (!validateEmail(email) || !validatePassword(suppliedPassword)) throw new Error('邮箱或密码不正确。');

    const attempt = this.failedAttempts.get(email);
    if (attempt && attempt.blockedUntil > Date.now()) {
      const seconds = Math.ceil((attempt.blockedUntil - Date.now()) / 1000);
      throw new Error(`尝试次数过多，请在 ${seconds} 秒后重试。`);
    }

      const database = this.readDatabase();
      const account = database.accounts.find((candidate) => candidate.email === email);
      this.consumeCryptoBudget();
      const suppliedHash = await hashPassword(suppliedPassword, account?.salt ?? randomBytes(PASSWORD_KDF.saltBytes).toString('hex'));
      const expectedHash = account?.passwordHash ?? randomBytes(PASSWORD_KDF.keyLength).toString('hex');
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
      let migrated = false;
      if (!account.aiAgent) {
        account.aiAgent = createAiAgent(account.id, account.createdAt);
        if (account.basicQuestionnaire) syncAgentProfile(account, new Date().toISOString());
        migrated = true;
      } else if (account.aiAgent.modelAssignment.strategy === 'dedicated-account-model') {
        account.aiAgent.modelAssignment.strategy = 'shared-base-model-account-agent';
        account.aiAgent.updatedAt = new Date().toISOString();
        migrated = true;
      }
      if (!account.passwordKdf) {
        account.passwordKdf = PASSWORD_KDF;
        migrated = true;
      }
      if (migrated) this.writeDatabase(database);
      return toPublicUser(account);
    });
  }

  async completeBasicQuestionnaire(accountId: string, input: BasicQuestionnaire): Promise<PublicUser> {
    return this.serialized(() => {
      const database = this.readDatabase();
      const account = database.accounts.find((candidate) => candidate.id === accountId);
      if (!account) throw new Error('账户不存在，请重新登录。');

      if (account.basicQuestionnaireCompletedAt) throw new Error('个人资料已完成首次保存，之后只能补充未填写的内容。');

      account.basicQuestionnaire = normalizeQuestionnaire(input);
      account.basicQuestionnaireCompletedAt = new Date().toISOString();
      syncAgentProfile(account, account.basicQuestionnaireCompletedAt);
      this.writeDatabase(database);
      return toPublicUser(account);
    });
  }

  async supplementProfile(accountId: string, input: BasicQuestionnaire): Promise<PublicUser> {
    return this.serialized(() => {
      const database = this.readDatabase();
      const account = database.accounts.find((candidate) => candidate.id === accountId);
      if (!account) throw new Error('账户不存在，请重新登录。');
      if (!account.basicQuestionnaire || !account.basicQuestionnaireCompletedAt) throw new Error('请先完成首次个人资料。');

      account.basicQuestionnaire = mergeProfileSupplement(account.basicQuestionnaire, input);
      syncAgentProfile(account, new Date().toISOString());
      this.writeDatabase(database);
      return toPublicUser(account);
    });
  }
}
