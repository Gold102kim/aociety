import fs from 'node:fs/promises';
import { renameSync, openSync, writeFileSync, fsyncSync, closeSync } from 'node:fs';
import path from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import { continuationLimit, memoryChoices, type ContinuationAction, type RepresentativeAction, type RepresentativeMemory, type RepresentativeState, type SavedContinuation } from './representative-types';

type Guard = () => boolean;
type Cipher = {
  available: () => Promise<boolean>;
  encrypt: (value: string) => Promise<Buffer>;
  decrypt: (value: Buffer) => Promise<string>;
};
type PrivacyFence = Pick<RepresentativeState, 'revision' | 'privacyEpoch' | 'cloudConsent' | 'learningMode'> & { sources: string[]; continuationIds?: string[] };
const stale = () => new Error('隐私设置或账户会话已改变，请重新操作。');

export function extractExplicitPreference(message: unknown): Pick<RepresentativeMemory, 'key' | 'value' | 'source'> | null {
  if (typeof message !== 'string' || message.length > 80) return null;
  const text = message.trim().replace(/[。！!]$/, '');
  // Only whole-message, unambiguous whitelist phrases qualify. Quotes, roleplay,
  // mixed sentences and guesses must never become the user's own facts.
  if (/^(?:请(?:用)?|回答请|以后请)(?:简短|简短一些|简短一点)(?:回答)?$/.test(text)) {
    return { key: 'replyStyle', value: '简短', source: message.trim() };
  }
  if (/^(?:请(?:用)?|回答请|以后请)(?:详细|详细一些|详细一点)(?:回答)?$/.test(text)) {
    return { key: 'replyStyle', value: '详细', source: message.trim() };
  }
  const music = /^我喜欢(爵士乐|摇滚乐|古典音乐|电子音乐|流行音乐)$/.exec(text);
  return music ? { key: 'musicGenre', value: music[1], source: message.trim() } : null;
}

function initialState(accountId: string, storage: RepresentativeState['storage']): RepresentativeState {
  return { schemaVersion: 1, accountId, revision: 0, privacyEpoch: 0, cloudConsent: false, learningMode: 'off', memories: [], continuations: [], storage };
}

function validateState(value: unknown, accountId: string): RepresentativeState {
  if (!value || typeof value !== 'object') throw new Error('数字代表数据格式无效。');
  const state = value as RepresentativeState;
  // Version-one files predate explicit bookmarks; missing means empty, not a
  // migration from the legacy questionnaire or an inferred conversation.
  const continuations = state.continuations ?? [];
  const validContinuation = (item: SavedContinuation) => item && typeof item === 'object'
    && typeof item.id === 'string' && /^[\da-f-]{36}$/.test(item.id)
    && ['topic', 'draft'].includes(item.kind)
    && typeof item.title === 'string' && Boolean(item.title.trim()) && item.title.length <= 60
    && typeof item.content === 'string' && Boolean(item.content.trim()) && item.content.length <= 2000
    && typeof item.createdAt === 'string' && Number.isFinite(Date.parse(item.createdAt));
  const validMemory = (memory: RepresentativeMemory) => memory && typeof memory === 'object'
    && typeof memory.id === 'string' && /^[\da-f-]{36}$/.test(memory.id)
    && Object.hasOwn(memoryChoices, memory.key) && memoryChoices[memory.key].includes(memory.value)
    && typeof memory.source === 'string' && memory.source.length <= 80
    && typeof memory.sourceId === 'string' && /^[\da-f-]{36}$/.test(memory.sourceId)
    && ['explicit_message', 'user_correction'].includes(memory.sourceKind)
    && typeof memory.updatedAt === 'string' && Number.isFinite(Date.parse(memory.updatedAt));
  if (state.schemaVersion !== 1 || state.accountId !== accountId
    || !Number.isSafeInteger(state.revision) || state.revision < 0
    || !Number.isSafeInteger(state.privacyEpoch) || state.privacyEpoch < 0
    || typeof state.cloudConsent !== 'boolean' || !['off', 'read_only', 'learn'].includes(state.learningMode)
    || !Array.isArray(state.memories) || state.memories.length > 2 || !state.memories.every(validMemory)
    || new Set(state.memories.map((memory) => memory.key)).size !== state.memories.length
    || !Array.isArray(continuations) || continuations.length > continuationLimit || !continuations.every(validContinuation)
    || new Set(continuations.map((item) => item.id)).size !== continuations.length) {
    throw new Error('数字代表数据格式无效，未覆盖原文件。');
  }
  return { ...state, continuations, storage: 'encrypted' };
}

export class RepresentativeStore {
  private queue: Promise<unknown> = Promise.resolve();
  private pending = 0;
  private generation = 0;
  private sessionStates = new Map<string, RepresentativeState>();
  private deniedCloud = new Set<string>();
  private nonPersonalContext = new Set<string>();
  private temporaryAccounts = new Set<string>();

  constructor(private readonly directory: string, private readonly cipher: Cipher) {}

  clearSession() {
    this.generation += 1;
    this.sessionStates.clear();
    this.nonPersonalContext.clear();
    this.temporaryAccounts.clear();
  }

  cancelPendingLearning(preserveContext = false) {
    this.generation += 1;
    if (!preserveContext) this.nonPersonalContext.clear();
  }

  beginConversation(accountId: string, temporary: boolean) {
    this.cancelPendingLearning();
    if (temporary) this.temporaryAccounts.add(accountId);
    else this.temporaryAccounts.delete(accountId);
  }

  isTemporary(accountId: string) { return this.temporaryAccounts.has(accountId); }

  isLearningPaused(accountId: string) { return this.nonPersonalContext.has(accountId); }

  observeSavedContent(accountId: string) { this.nonPersonalContext.add(accountId); }

  denyRequests(accountId: string) { this.deniedCloud.add(accountId); this.generation += 1; }

  observeContext(accountId: string, message: string) {
    // A temporary safety flag is not an evidence record or retained transcript.
    // Once a conversation contains a non-personal scenario, do not infer that
    // later first-person lines are autobiographical.
    if (/角色扮演|假如|假设|模拟|翻译|引用|小说|剧本|台词|复述|讲故事|role.?play|translate|hypothetical/i.test(message)) {
      this.nonPersonalContext.add(accountId);
    }
  }

  private filePath(accountId: string) {
    if (typeof accountId !== 'string' || !accountId || accountId.length > 128) throw new Error('账户标识无效。');
    return path.join(this.directory, `${createHash('sha256').update(accountId).digest('hex')}.bin`);
  }

  private async readFence(file: string): Promise<PrivacyFence | null> {
    try {
      if ((await fs.stat(`${file}.privacy`)).size > 4096) throw new Error('隐私账本超出限制。');
      const value = JSON.parse(await fs.readFile(`${file}.privacy`, 'utf8')) as PrivacyFence;
      if (!Number.isSafeInteger(value.revision) || value.revision < 0 || !Number.isSafeInteger(value.privacyEpoch) || value.privacyEpoch < 0
        || typeof value.cloudConsent !== 'boolean' || !['off', 'read_only', 'learn'].includes(value.learningMode)
        || !Array.isArray(value.sources) || value.sources.length > 2 || !value.sources.every((id) => typeof id === 'string' && /^[\da-f-]{36}$/.test(id))
        || (value.continuationIds !== undefined && (!Array.isArray(value.continuationIds) || value.continuationIds.length > continuationLimit
          || !value.continuationIds.every((id) => typeof id === 'string' && /^[\da-f-]{36}$/.test(id))))) throw new Error('隐私账本无效。');
      return value;
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return null;
      throw new Error('隐私账本无法读取，已停止使用画像。');
    }
  }

  private writeFence(file: string, fence: PrivacyFence) {
    const temporary = `${file}.privacy.tmp`;
    const handle = openSync(temporary, 'w', 0o600);
    try { writeFileSync(handle, JSON.stringify(fence)); fsyncSync(handle); } finally { closeSync(handle); }
    renameSync(temporary, `${file}.privacy`);
  }

  private async serialized<T>(work: () => Promise<T>): Promise<T> {
    if (this.pending >= 32) throw new Error('记忆服务繁忙，请稍后重试。');
    this.pending += 1;
    const result = this.queue.then(work);
    this.queue = result.catch(() => undefined);
    try { return await result; } finally { this.pending -= 1; }
  }

  private async read(accountId: string, guard: Guard) {
    if (!guard()) throw stale();
    const file = this.filePath(accountId);
    const fence = await this.readFence(file);
    const available = await this.cipher.available();
    if (!guard()) throw stale();
    if (!available) {
      const state = structuredClone(this.sessionStates.get(accountId) ?? initialState(accountId, 'session'));
      if (fence && state.revision < fence.revision) Object.assign(state, { revision: fence.revision, privacyEpoch: fence.privacyEpoch });
      if (this.deniedCloud.has(accountId)) state.cloudConsent = false;
      return state;
    }
    // No backup contains older memories. Uncommitted encrypted temporaries are
    // never recovered, so a restart cannot resurrect a forgotten preference.
    await fs.rm(`${file}.tmp`, { force: true });
    await fs.rm(`${file}.privacy.tmp`, { force: true });
    let state: RepresentativeState;
    try {
      if ((await fs.stat(file)).size > 32_768) throw new Error('数字代表数据超出限制。');
      const plaintext = await this.cipher.decrypt(await fs.readFile(file));
      if (!guard()) throw stale();
      state = validateState(JSON.parse(plaintext), accountId);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') state = initialState(accountId, 'encrypted');
      else {
        if (!guard()) throw stale();
        throw new Error('数字代表数据无法读取，未覆盖原文件。请重试或检查系统加密服务。');
      }
    }
    const needsRepair = Boolean(fence && (state.revision < fence.revision
      || state.continuations.some((item) => !fence.continuationIds?.includes(item.id))));
    if (fence) {
      if (state.revision > fence.revision || state.privacyEpoch > fence.privacyEpoch) throw new Error('隐私版本不一致，已停止使用画像。');
      state.memories = state.memories.filter((memory) => fence.sources.includes(memory.sourceId));
      state.continuations = state.continuations.filter((item) => fence.continuationIds?.includes(item.id));
      Object.assign(state, { revision: fence.revision, privacyEpoch: fence.privacyEpoch, cloudConsent: fence.cloudConsent, learningMode: fence.learningMode });
    } else if (state.revision > 0) throw new Error('隐私账本缺失，已停止使用画像。');
    if (this.deniedCloud.has(accountId)) state.cloudConsent = false;
    if (needsRepair) await this.write(state, guard, this.generation);
    return state;
  }

  private async write(state: RepresentativeState, guard: Guard, generation: number, privacyFirst = false) {
    const valid = () => guard() && this.generation === generation;
    if (!valid()) throw stale();
    if (state.storage === 'session') {
      if (state.learningMode !== 'off' || state.memories.length || state.continuations.length) throw new Error('系统加密不可用，不能保存或使用长期画像。');
      if (!state.cloudConsent) {
        const file = this.filePath(state.accountId);
        const fence = await this.readFence(file);
        await fs.mkdir(this.directory, { recursive: true });
        if (!valid()) throw stale();
        this.writeFence(file, { revision: state.revision, privacyEpoch: state.privacyEpoch, cloudConsent: false, learningMode: 'off', sources: fence?.sources ?? [], continuationIds: fence?.continuationIds ?? [] });
      }
      if (!valid()) throw stale();
      this.sessionStates.set(state.accountId, structuredClone(state));
      return;
    }
    const file = this.filePath(state.accountId);
    const fence: PrivacyFence = { revision: state.revision, privacyEpoch: state.privacyEpoch, cloudConsent: state.cloudConsent,
      learningMode: state.learningMode, sources: state.memories.map((memory) => memory.sourceId), continuationIds: state.continuations.map((item) => item.id) };
    if (privacyFirst) {
      await fs.mkdir(this.directory, { recursive: true });
      if (!valid()) throw stale();
      // Persist revocations/redactions before asynchronous encryption. On a
      // crash or encryption failure, startup must obey this newer policy.
      this.writeFence(file, fence);
    }
    const encrypted = await this.cipher.encrypt(JSON.stringify(state));
    if (!valid()) throw stale();
    await fs.mkdir(this.directory, { recursive: true });
    const temporary = `${file}.tmp`;
    try {
      const handle = await fs.open(temporary, 'wx', 0o600);
      try { await handle.writeFile(encrypted); await handle.sync(); } finally { await handle.close(); }
      if (!valid()) throw stale();
      // The rename is synchronous only at this final commit point: no event may
      // revoke consent between the final guard and replacing the encrypted file.
      if (!privacyFirst) this.writeFence(file, fence);
      renameSync(temporary, file);
    } finally { await fs.rm(temporary, { force: true }); }
  }

  getState(accountId: string, guard: Guard = () => true) {
    return this.serialized(async () => {
      const state = await this.read(accountId, guard);
      if (!guard()) throw stale();
      return state;
    });
  }

  update(accountId: string, input: RepresentativeAction, guard: Guard = () => true) {
    if (!input || typeof input !== 'object' || !Number.isSafeInteger(input.expectedRevision) || input.expectedRevision < 0) {
      return Promise.reject(new Error('操作参数无效。'));
    }
    const generation = ++this.generation;
    this.nonPersonalContext.clear();
    if (input.kind === 'reset' || (input.kind === 'consent' && input.enabled === false)) this.deniedCloud.add(accountId);
    return this.serialized(async () => {
      const state = await this.read(accountId, guard);
      if (state.revision !== input.expectedRevision) throw new Error('内容已有变化，请刷新后重试。');
      switch (input.kind) {
        case 'consent':
          if (typeof input.enabled !== 'boolean') throw new Error('授权参数无效。');
          state.cloudConsent = input.enabled;
          break;
        case 'mode':
          if (!['off', 'read_only', 'learn'].includes(input.mode)) throw new Error('学习模式无效。');
          if (state.storage !== 'encrypted' && input.mode !== 'off') throw new Error('系统加密不可用，学习功能已停用。');
          state.learningMode = input.mode;
          break;
        case 'forget':
        case 'correct': {
          const memory = state.memories.find((entry) => entry.id === input.id);
          if (!memory) throw new Error('这条记忆已不存在，请刷新。');
          if (input.kind === 'forget') state.memories = state.memories.filter((entry) => entry.id !== input.id);
          else {
            if (!memoryChoices[memory.key].includes(input.value)) throw new Error('请选择受支持的偏好。');
            Object.assign(memory, { value: input.value, source: '用户在记忆面板中明确修正', sourceKind: 'user_correction', sourceId: randomUUID(), updatedAt: new Date().toISOString() });
          }
          break;
        }
        case 'reset':
          if (state.storage !== 'encrypted') throw new Error('系统加密不可用，请恢复加密服务后重置长期画像。');
          state.memories = [];
          state.continuations = [];
          state.learningMode = 'off';
          state.cloudConsent = false;
          break;
        default: throw new Error('不支持的记忆操作。');
      }
      state.revision += 1;
      state.privacyEpoch += 1;
      await this.write(state, guard, generation, true);
      if (!guard() || this.generation !== generation) throw stale();
      if (input.kind === 'consent' && input.enabled) this.deniedCloud.delete(accountId);
      return state;
    });
  }

  continuation(accountId: string, input: ContinuationAction, guard: Guard = () => true) {
    if (!input || typeof input !== 'object' || !Number.isSafeInteger(input.expectedRevision) || input.expectedRevision < 0
      || !['save', 'resume', 'complete', 'remove'].includes(input.kind)) return Promise.reject(new Error('操作参数无效。'));
    const generation = input.kind === 'resume' ? ++this.generation : this.generation;
    const valid = () => guard() && generation === this.generation && !this.isTemporary(accountId);
    return this.serialized(async () => {
      if (this.isTemporary(accountId)) throw new Error('临时对话不能保存或恢复话题，请先关闭临时对话。');
      const state = await this.read(accountId, valid);
      if (state.storage !== 'encrypted') throw new Error('系统加密不可用，未保存或恢复内容。');
      if (state.revision !== input.expectedRevision) throw new Error('内容已有变化，请刷新后重试。');
      if (input.kind === 'save') {
        const item = input.item;
        if (!item || !['topic', 'draft'].includes(item.kind) || typeof item.title !== 'string' || !item.title.trim() || item.title.length > 60
          || typeof item.content !== 'string' || !item.content.trim() || item.content.length > 2000) throw new Error('请填写标题（最多60字）和内容（最多2000字）。');
        if (state.continuations.length >= continuationLimit) throw new Error('最多保留3条待续内容，请先完成或移除一条。');
        state.continuations.push({ id: randomUUID(), kind: item.kind, title: item.title.trim(), content: item.content.trim(), createdAt: new Date().toISOString() });
      } else {
        const item = state.continuations.find((entry) => entry.id === input.id);
        if (!item) throw new Error('这条待续内容已不存在，请刷新。');
        if (input.kind === 'resume') {
          if (!valid()) throw stale();
          // A saved draft may quote another person. Never treat a resumed
          // conversation as evidence about the account owner's preferences.
          this.nonPersonalContext.add(accountId);
          return { state, resumed: item };
        }
        // Completion is terminal: keep no completed-content archive.
        state.continuations = state.continuations.filter((entry) => entry.id !== input.id);
      }
      state.revision += 1;
      await this.write(state, valid, generation, input.kind !== 'save');
      if (!valid()) throw stale();
      return { state };
    });
  }

  learn(accountId: string, message: string, snapshot: RepresentativeState, guard: Guard) {
    const generation = this.generation;
    const candidate = extractExplicitPreference(message);
    if (!candidate || this.nonPersonalContext.has(accountId) || snapshot.learningMode !== 'learn' || !snapshot.cloudConsent || snapshot.storage !== 'encrypted') return Promise.resolve(null);
    return this.serialized(async () => {
      const valid = () => guard() && generation === this.generation;
      if (!valid() || this.nonPersonalContext.has(accountId)) return null;
      const state = await this.read(accountId, valid);
      if (!valid() || state.privacyEpoch !== snapshot.privacyEpoch || state.revision !== snapshot.revision
        || !state.cloudConsent || state.learningMode !== 'learn' || state.storage !== 'encrypted') return null;
      const existing = state.memories.find((entry) => entry.key === candidate.key);
      if (existing?.sourceKind === 'user_correction' || existing?.value === candidate.value) return null;
      const memory: RepresentativeMemory = {
        ...candidate, id: existing?.id ?? randomUUID(), sourceId: randomUUID(),
        sourceKind: 'explicit_message', updatedAt: new Date().toISOString(),
      };
      state.memories = state.memories.filter((entry) => entry.key !== memory.key).concat(memory);
      state.revision += 1;
      await this.write(state, valid, generation);
      return valid() ? state : null;
    });
  }
}
