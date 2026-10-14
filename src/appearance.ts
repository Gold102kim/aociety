export const appearanceStorageKey = 'echoverse:appearance:reduce-transparency';
export const reducedTransparencyMediaQuery = '(prefers-reduced-transparency: reduce), (prefers-contrast: more), (forced-colors: active)';

type PreferenceStorage = Pick<Storage, 'getItem' | 'setItem'>;

export function readReducedTransparency(storage: PreferenceStorage): boolean {
  try { return storage.getItem(appearanceStorageKey) === 'true'; } catch { return false; }
}

export function saveReducedTransparency(storage: PreferenceStorage, reduced: boolean): void {
  try { storage.setItem(appearanceStorageKey, String(reduced)); } catch { /* Appearance remains usable when storage is blocked. */ }
}
