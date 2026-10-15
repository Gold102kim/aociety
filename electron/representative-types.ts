export type LearningMode = 'off' | 'read_only' | 'learn';
export type MemoryKey = 'replyStyle' | 'musicGenre';
export const memoryChoices: Record<MemoryKey, readonly string[]> = {
  replyStyle: ['简短', '详细'],
  musicGenre: ['爵士乐', '摇滚乐', '古典音乐', '电子音乐', '流行音乐'],
};

export type RepresentativeMemory = {
  id: string;
  key: MemoryKey;
  value: string;
  source: string;
  sourceId: string;
  sourceKind: 'explicit_message' | 'user_correction';
  updatedAt: string;
};

export const continuationLimit = 3;
export type SavedContinuation = {
  id: string;
  kind: 'topic' | 'draft';
  title: string;
  content: string;
  createdAt: string;
};
export type ContinuationAction =
  | { kind: 'save'; item: Pick<SavedContinuation, 'kind' | 'title' | 'content'>; expectedRevision: number }
  | { kind: 'resume' | 'complete' | 'remove'; id: string; expectedRevision: number };

export type RepresentativeState = {
  schemaVersion: 1;
  accountId: string;
  revision: number;
  privacyEpoch: number;
  cloudConsent: boolean;
  learningMode: LearningMode;
  memories: RepresentativeMemory[];
  continuations: SavedContinuation[];
  storage: 'encrypted' | 'session';
};

export type RepresentativeAction =
  | { kind: 'consent'; enabled: boolean; expectedRevision: number }
  | { kind: 'mode'; mode: LearningMode; expectedRevision: number }
  | { kind: 'forget'; id: string; expectedRevision: number }
  | { kind: 'correct'; id: string; value: string; expectedRevision: number }
  | { kind: 'reset'; expectedRevision: number };

export type RepresentativeResult =
  | { ok: true; state: RepresentativeState; learningPaused: boolean; temporary: boolean; resumed?: SavedContinuation }
  | { ok: false; message: string };

export type RepresentativeChange = 'saved' | 'failed' | 'paused';

export type RepresentativeApi = {
  getState: () => Promise<RepresentativeResult>;
  update: (input: RepresentativeAction) => Promise<RepresentativeResult>;
  continuation: (input: ContinuationAction) => Promise<RepresentativeResult>;
  onChanged: (listener: (status: RepresentativeChange) => void) => () => void;
};
