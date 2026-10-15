import type { PublicUser } from './auth-service';
import type { AiChatService, AiChatMessage } from './ai-service';
import type { RepresentativeStore } from './representative-store';
import type { RepresentativeChange } from './representative-types';
import { simulationModes, simulationPromptVersion, type SimulationInput, type SimulationReply } from './simulation-types';

export type RepresentativeChatInput = {
  message: string;
  history: AiChatMessage[];
  temporary: boolean;
  privacyEpoch: number;
  savedContent?: boolean;
};

export async function runRepresentativeChat(
  store: RepresentativeStore,
  ai: AiChatService,
  user: PublicUser,
  input: RepresentativeChatInput,
  isCurrent: () => boolean,
  onLearned: (status: RepresentativeChange) => void,
) {
  if (!input || typeof input.message !== 'string' || !input.message.trim() || input.message.length > 2000
    || typeof input.temporary !== 'boolean' || !Number.isSafeInteger(input.privacyEpoch)
    || (input.savedContent !== undefined && typeof input.savedContent !== 'boolean')
    || !Array.isArray(input.history) || input.history.length > 12
    || !input.history.every((item) => item && ['user', 'assistant'].includes(item.role)
      && typeof item.content === 'string' && item.content.length <= 2000)) throw new Error('消息参数无效。');
  const readState = async () => {
    try { return await store.getState(user.id, isCurrent); }
    catch { throw new Error('无法安全读取当前隐私设置，请重试或检查系统加密服务。'); }
  };
  const state = await readState();
  if (!isCurrent()) throw new Error('账户会话已改变，请重新操作。');
  if (store.isTemporary(user.id) !== input.temporary) throw new Error('对话模式已改变，请切换模式后重新发送。');
  if (!state.cloudConsent) throw new Error('请先明确同意云端处理，当前没有发送任何模型请求。');
  if (ai.getStatus().provider !== 'deepseek') throw new Error('数字代表当前仅支持 DeepSeek，请先检查模型配置。');
  if (state.privacyEpoch !== input.privacyEpoch) throw new Error('隐私设置已改变，请刷新后重新发送。');
  const wasPaused = store.isLearningPaused(user.id);
  store.observeContext(user.id, input.message);
  if (input.savedContent) store.observeSavedContent(user.id);
  // Report the safety pause before the request: even a failed reply may have
  // established non-personal context for the rest of this conversation.
  if (!wasPaused && !input.temporary && state.learningMode === 'learn' && store.isLearningPaused(user.id)) onLearned('paused');
  const facts = input.temporary || state.learningMode === 'off'
    ? {} : Object.fromEntries(state.memories.map((memory) => [memory.key, memory.value]));
  const result = await ai.chat(user, input.message, input.history, facts);
  const current = await readState();
  if (!isCurrent() || current.privacyEpoch !== state.privacyEpoch) throw new Error('隐私设置或账户会话已改变，本次回复已丢弃。');
  if (!input.temporary) {
    // Learning never delays a successful reply. Only the current input is a
    // source; renderer-provided history and assistant output are not evidence.
    void store.learn(user.id, input.message, state, isCurrent).then((learned) => {
      if (learned && isCurrent()) onLearned('saved');
    }).catch(() => { if (isCurrent()) onLearned('failed'); });
  }
  return result;
}

export async function runPrivateSimulation(
  store: RepresentativeStore,
  ai: AiChatService,
  user: PublicUser,
  input: SimulationInput,
  isCurrent: () => boolean,
): Promise<SimulationReply> {
  if (!input || typeof input.scenario !== 'string' || !input.scenario.trim() || input.scenario.length > 2000
    || !simulationModes.includes(input.mode) || typeof input.temporary !== 'boolean'
    || !Number.isSafeInteger(input.privacyEpoch) || input.privacyEpoch < 0
    || !Number.isSafeInteger(input.expectedRevision) || input.expectedRevision < 0) throw new Error('模拟参数无效，请填写最多2000字的情境。');
  const readState = async () => {
    try { return await store.getState(user.id, isCurrent); }
    catch { throw new Error('无法安全读取当前隐私设置，请重试或检查系统加密服务。'); }
  };
  const state = await readState();
  if (!isCurrent()) throw new Error('账户会话已改变，请重新操作。');
  if (store.isTemporary(user.id) !== input.temporary) throw new Error('对话模式已改变，请切换模式后重新生成。');
  if (!state.cloudConsent) throw new Error('请先明确同意 DeepSeek 云端处理，当前没有发送任何模型请求。');
  if (ai.getStatus().provider !== 'deepseek') throw new Error('私密模拟当前仅支持 DeepSeek，请先检查模型配置。');
  if (state.privacyEpoch !== input.privacyEpoch || state.revision !== input.expectedRevision) throw new Error('资料或隐私版本已改变，请刷新后重新生成。');
  if (input.mode !== 'generic' && (input.temporary || state.learningMode === 'off' || state.storage !== 'encrypted')) {
    throw new Error('当前模式不允许使用画像，请选择通用回复或调整隐私设置。');
  }
  const memories = input.mode === 'generic' ? [] : state.memories.filter((memory) => input.mode === 'with_memories' || memory.sourceKind === 'user_correction');
  const started = Date.now();
  // No history, saved drafts, reference answers or feedback enter this request.
  // Simulation never calls learn(), including when its scenario is a whitelist phrase.
  const result = await ai.chat(user, input.scenario.trim(), [], Object.fromEntries(memories.map((memory) => [memory.key, memory.value])), 'private_simulation');
  const current = await readState();
  if (!isCurrent() || current.privacyEpoch !== state.privacyEpoch || current.revision !== state.revision) {
    throw new Error('资料、隐私设置或账户会话已改变，本次试答已丢弃。');
  }
  return { text: result.text, model: result.model, mode: input.mode, profileRevision: state.revision,
    usedMemoryKeys: memories.map((memory) => memory.key), createdAt: new Date().toISOString(), durationMs: Math.max(0, Date.now() - started), promptVersion: simulationPromptVersion };
}
