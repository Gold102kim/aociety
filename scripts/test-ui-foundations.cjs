const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { stripTypeScriptTypes } = require('node:module');

const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'src/theme.ts'), 'utf8')
  .replace(/^import .*;\r?\n/m, '').replace(/export (const|function)/g, '$1');
const api = {};
vm.runInNewContext(`${stripTypeScriptTypes(source)}\napi.options = colorOptions; api.theme = getThemeStyle;`, { api });
function luminance(hex) {
  const channels = [1, 3, 5].map((index) => {
    const channel = parseInt(hex.slice(index, index + 2), 16) / 255;
    return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
  });
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
}
for (const option of api.options) {
  const theme = api.theme(option.name);
  assert.equal(theme['--accent'], option.hex, 'Refresh must preserve favorite colors.');
  for (const background of [theme['--accent'], theme['--accent-hover']]) {
    const light = luminance(background);
    const dark = luminance(theme['--accent-contrast']);
    const contrast = (Math.max(light, dark) + 0.05) / (Math.min(light, dark) + 0.05);
    assert.ok(contrast >= 4.5, `${option.name} action text needs 4.5:1 contrast, got ${contrast.toFixed(2)}.`);
  }
}
assert.equal(api.theme('蓝色')['--accent'], '#66B8FF');
assert.equal(api.theme('')['--accent'], '#66E3CC');
const illustration = fs.readFileSync(path.join(root, 'public/illustrations/forest-town.svg'), 'utf8');
assert.ok(Buffer.byteLength(illustration) < 16 * 1024, 'Hero illustration should stay lightweight.');
assert.equal(/<image|<script|https?:\/\//.test(illustration.replace('http://www.w3.org/2000/svg', '')), false, 'Illustration must not depend on remote assets or scripts.');

const appearanceSource = fs.readFileSync(path.join(root, 'src/appearance.ts'), 'utf8')
  .replace(/export (const|function)/g, '$1');
const appearance = {};
vm.runInNewContext(`${stripTypeScriptTypes(appearanceSource)}\napi.key = appearanceStorageKey; api.read = readReducedTransparency; api.save = saveReducedTransparency;`, { api: appearance });
assert.equal(appearance.key, 'echoverse:appearance:reduce-transparency');
const preferenceValues = new Map([['unrelated:user-data', 'keep']]);
const preferenceReads = [];
const preferenceWrites = [];
const preferenceStorage = {
  getItem(key) {
    preferenceReads.push(key);
    return preferenceValues.get(key) ?? null;
  },
  setItem(key, value) {
    preferenceWrites.push([key, value]);
    preferenceValues.set(key, value);
  },
};
assert.equal(appearance.read(preferenceStorage), false, 'Missing appearance preference should keep glass enabled.');
assert.equal(preferenceWrites.length, 0, 'Reading preferences must not initialize or overwrite storage.');
appearance.save(preferenceStorage, true);
assert.equal(appearance.read(preferenceStorage), true, 'Reduced transparency must survive reading a saved preference.');
appearance.save(preferenceStorage, false);
assert.equal(appearance.read(preferenceStorage), false, 'Glass mode must survive reading a saved preference.');
assert.deepEqual(preferenceWrites, [[appearance.key, 'true'], [appearance.key, 'false']]);
assert.ok(preferenceReads.every((key) => key === appearance.key), 'Appearance must not read account or unrelated preferences.');
assert.deepEqual([...preferenceValues], [['unrelated:user-data', 'keep'], [appearance.key, 'false']], 'Saving appearance must preserve unrelated data.');
for (const invalidValue of ['', 'TRUE', '1', 'invalid']) {
  assert.equal(appearance.read({ getItem: () => invalidValue }), false, 'Only the explicit true value should enable reduced transparency.');
}
const blockedStorage = {
  getItem() { throw new Error('Storage access denied'); },
  setItem() { throw new Error('Storage access denied'); },
};
assert.doesNotThrow(() => assert.equal(appearance.read(blockedStorage), false), 'Blocked storage must not break reading preferences.');
assert.doesNotThrow(() => appearance.save(blockedStorage, true), 'Blocked storage must not break reduced mode.');
assert.doesNotThrow(() => appearance.save(blockedStorage, false), 'Blocked storage must not break glass mode.');

const glassCss = fs.readFileSync(path.join(root, 'src/glass-theme.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
for (const background of ['#172337', '#1b2a3f', '#344354']) {
  for (const foreground of ['#f3f6fc', '#b3c0d2']) {
    const ratio = (luminance(foreground) + .05) / (luminance(background) + .05);
    assert.ok(ratio >= 4.5, `Glass text pair needs 4.5:1, got ${ratio.toFixed(2)}.`);
  }
}
assert.match(glassCss, /input\[type="checkbox"\]\s*\{\s*appearance:\s*auto;/, 'Forced colors must restore native checkbox rendering.');
assert.match(glassCss, /\.chat-workspaces button\[aria-pressed="true"\]\s*\{\s*color:\s*CanvasText;\s*background:\s*Canvas;/, 'Forced-color selected text must not disappear into browser text backplates.');
assert.match(glassCss, /\.app\.ui-refresh\.ui-glass\.ui-glass-reduced\s*\{[^}]*--glass-filter:\s*none;[^}]*background-image:\s*none;/, 'Manual reduced transparency should disable blur and ambient decoration.');
assert.match(glassCss, /@media\s*\(prefers-reduced-transparency:\s*reduce\),\s*\(prefers-contrast:\s*more\)\s*\{\s*\.app\.ui-refresh\.ui-glass\s*\{[^}]*--glass-filter:\s*none;/, 'System transparency and contrast preferences need a no-blur fallback.');
assert.match(glassCss, /@supports\s+not\s*\(backdrop-filter:\s*blur\(1px\)\)\s*\{[^}]*--glass-filter:\s*none;/, 'Browsers without backdrop-filter need a fallback.');
assert.match(glassCss, /@media\s*\(forced-colors:\s*active\)\s*\{[^}]*--glass-filter:\s*none;[^}]*background:\s*Canvas;/, 'Forced colors need opaque system surfaces and no blur.');
assert.equal(/(?:^|[;{])\s*animation(?:-[\w-]+)?\s*:[^;{}]*\binfinite\b/m.test(glassCss), false, 'Glass styling must not introduce continuous animations.');
assert.equal(/(?:^|[;{])\s*(?:-webkit-)?filter\s*:/m.test(glassCss), false, 'Glass must not filter whole surfaces or canvases, including through universal selectors.');
assert.match(glassCss, /\.auth-card input/, 'Glass input styling must target the real account form markup.');
for (const [, selector, declarations] of glassCss.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
  if (/\bcanvas\b/.test(selector)) {
    assert.equal(/(?:^|;)\s*(?:-webkit-)?(?:backdrop-)?filter\s*:/m.test(declarations), false, 'Glass styling must not filter the 3D canvas.');
  }
}
const refreshCss = fs.readFileSync(path.join(root, 'src/ui-refresh.css'), 'utf8');
const liquidCss = fs.readFileSync(path.join(root, 'src/liquid-glass.css'), 'utf8');
assert.match(liquidCss, /\[data-liquid-glass\]::before\s*\{[^}]*backdrop-filter:\s*var\(--liquid-filter\)/, 'Lens distortion belongs on backdrop-only pseudo elements.');
assert.equal(/(?:^|[;{])\s*(?:-webkit-)?filter\s*:/m.test(liquidCss), false, 'Optical chrome must never distort foreground text or the avatar canvas.');
assert.equal(/animation[^;{}]*infinite/.test(liquidCss), false, 'Optical chrome must not introduce a continuous rendering loop.');
assert.match(liquidCss, /\.ui-glass-reduced \[data-liquid-glass\]::before[^}]*display:\s*none/, 'Clear mode must suppress the lens immediately.');
assert.match(liquidCss, /@media \(prefers-reduced-motion: reduce\)/, 'Optical feedback must honor reduced motion.');
assert.match(refreshCss, /\.ui-refresh\s+\.chat-content\[hidden\]\s*\{\s*display:\s*none;/, 'Retained inactive chat must remain hidden.');
assert.match(refreshCss, /\.ui-refresh\s+\.chat-window\s*\{[^}]*min-height:\s*0;[^}]*grid-template-rows:\s*auto\s+minmax\(0,\s*1fr\)\s+auto\s+auto;/, 'Chat should preserve its bounded scroll area.');
assert.match(refreshCss, /\.ui-refresh\s+\.chat-composer\s*\{[^}]*grid-row:\s*4;/, 'Chat composer must keep its fixed grid row.');
console.log('UI foundations passed: 9 accent colors, accessible action contrast, lightweight illustration, appearance storage, glass fallbacks and bounded chat layout.');
