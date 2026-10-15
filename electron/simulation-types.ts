import type { MemoryKey } from './representative-types';

export const simulationModes = ['generic', 'confirmed', 'with_memories'] as const;
export const simulationPromptVersion = 'private-simulation-v1';
export type SimulationMode = typeof simulationModes[number];
export const simulationLabels: Record<SimulationMode, string> = {
  generic: '通用回复',
  confirmed: '仅本人修正的偏好',
  with_memories: '本人修正＋对话偏好',
};
export type SimulationInput = {
  scenario: string;
  mode: SimulationMode;
  temporary: boolean;
  privacyEpoch: number;
  expectedRevision: number;
};
export type SimulationReply = {
  text: string;
  model: string;
  mode: SimulationMode;
  profileRevision: number;
  usedMemoryKeys: MemoryKey[];
  createdAt: string;
  durationMs: number;
  promptVersion: typeof simulationPromptVersion;
};
export type SimulationResult = { ok: true; reply: SimulationReply } | { ok: false; message: string };

export const evaluationDimensions = [
  { key: 'facts', label: '没有编造我的事实' },
  { key: 'style', label: '说话方式像我' },
  { key: 'choices', label: '选择倾向像我' },
  { key: 'usefulness', label: '对我有帮助' },
] as const;
export type EvaluationDimension = typeof evaluationDimensions[number]['key'];
export type EvaluationRating = '' | 'yes' | 'partly' | 'no' | 'unknown';
