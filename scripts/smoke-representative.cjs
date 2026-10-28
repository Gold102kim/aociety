// Optional desktop E2E: use the workspace-provided Playwright via NODE_PATH.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { _electron } = require('playwright');
const { expect } = require('playwright/test');
const installRepresentativeTransport = require('./fixtures/representative-transport.cjs');
const { checkLiquidGlass } = require('./fixtures/liquid-glass-checks.cjs');
const { checkLiquidGlassInteraction } = require('./fixtures/liquid-glass-interaction-checks.cjs');
const { checkTemporaryPrivacy } = require('./fixtures/temporary-privacy-checks.cjs');
const { checkChatStop } = require('./fixtures/chat-stop-checks.cjs');
const root = path.resolve(__dirname, '..');
const packageDirectory = process.env.ECHO_REPRESENTATIVE_PACKAGE_DIR ? path.resolve(process.env.ECHO_REPRESENTATIVE_PACKAGE_DIR) : null;
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'echoverse-representative-ui-'));
const screenshots = packageDirectory ? path.join(packageDirectory, 'screenshots') : path.join(root, 'artifacts', 'representative-20261015');
const state = (page) => page.evaluate(async () => {
  const result = await window.launcher.representative.getState();
  if (!result.ok) throw new Error(result.message);
  return result.state;
});
const env = { ...process.env, ECHO_REPRESENTATIVE_TEST_ROOT: temporary, ECHOVERSE_OPENAI_API_KEY: '', ECHO_SMOKE_AUTOLAUNCH: '0' };
delete env.ECHO_GAME_CONFIG;
delete env.GAME_EXECUTABLE_PATH;
delete env.ELECTRON_RUN_AS_NODE;
let application;
async function capture(page, name) {
  // Settle finite chrome transitions only for screenshots, never in product input.
  await page.waitForTimeout(180);
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true, 'No horizontal page overflow.');
  const captureFrame = () => application.evaluate(async () => {
    const image = await global.__representativeWindow.webContents.capturePage(undefined, { stayHidden: true, stayAwake: true });
    if (image.isEmpty()) throw new Error('Hidden-window capture was empty.');
    return image.toPNG().toString('base64');
  });
  // Offscreen Chromium may briefly reject a capture while resizing its surface.
  const png = await captureFrame().catch(async (error) => {
    if (!String(error).includes('UnknownVizError')) throw error;
    await page.waitForTimeout(100);
    return captureFrame();
  });
  fs.writeFileSync(path.join(screenshots, `${name}.png`), Buffer.from(png, 'base64'));
}
async function send(page, text) {
  await page.getByRole('textbox', { name: '发送给数字分身的消息' }).fill(text);
  await page.getByRole('button', { name: '发送消息', exact: true }).click();
  await expect(page.getByText('这是隔离测试回复，不是真实模型输出。', { exact: true })).toBeVisible();
}

(async () => {
  fs.mkdirSync(screenshots, { recursive: true });
  if (packageDirectory) {
    require('./audit-local-package.cjs').auditPackage(packageDirectory);
    const data = path.join(temporary, 'echoverse-launcher');
    fs.mkdirSync(data, { recursive: true });
    const { AccountStore } = require('../dist-electron/auth-service.js');
    await new AccountStore(path.join(data, 'accounts.json')).register({ displayName: '隔离启动校验', email: 'bootstrap@example.local', password: 'IsolatedBootstrap2026!' });
    fs.writeFileSync(path.join(data, 'ai.json'), JSON.stringify({ provider: 'deepseek', apiKey: 'isolated-test-key-not-real', model: 'deepseek-test' }));
    // The existing smoke switch owns an isolated userData directory. Its game
    // attempt has no configuration or fallback executable and must fail safely.
    Object.assign(env, { ECHO_SMOKE_AUTOLAUNCH: '1', ECHO_USER_DATA_DIR: data, ECHO_SMOKE_EMAIL: 'bootstrap@example.local', ECHO_SMOKE_PASSWORD: 'IsolatedBootstrap2026!', ECHO_SMOKE_RESULT_PATH: path.join(data, 'bootstrap-result.json'), ECHO_SMOKE_AUTOQUIT_MS: '120000' });
    application = await _electron.launch({ executablePath: path.join(packageDirectory, 'win-unpacked/EchoVerseLauncher.exe'), args: [], env });
    await application.firstWindow();
    const isolation = await application.evaluate(({ app, BrowserWindow }) => {
      global.__representativeWindow = BrowserWindow.getAllWindows()[0];
      global.__representativeWindow.hide();
      return { packaged: app.isPackaged, userData: app.getPath('userData'), appPath: app.getAppPath() };
    });
    assert.equal(isolation.packaged, true);
    assert.equal(path.resolve(isolation.userData), data);
    assert.equal(path.resolve(isolation.appPath), path.join(packageDirectory, 'win-unpacked/resources/app.asar'));
    await application.evaluate(installRepresentativeTransport);
    await expect.poll(() => fs.existsSync(path.join(data, 'bootstrap-result.json'))).toBe(true);
    assert.equal(JSON.parse(fs.readFileSync(path.join(data, 'bootstrap-result.json'), 'utf8')).ok, false, 'Game launch is intentionally disabled in this representative-only smoke.');
  } else application = await _electron.launch({ executablePath: path.join(root, 'node_modules/electron/dist/electron.exe'), args: [path.join(__dirname, 'fixtures/representative-main.cjs')], env });
  const page = await application.firstWindow();
  page.setDefaultTimeout(10_000);
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await capture(page, '00-account-glass');
  const entryButton = page.getByRole('button', { name: '进入平台', exact: true });
  const entryBounds = await entryButton.boundingBox();
  await page.mouse.move(entryBounds.x + entryBounds.width / 2, entryBounds.y + entryBounds.height / 2);
  await page.mouse.down();
  const pressMotion = await entryButton.evaluate((element) => {
    const animations = element.getAnimations().filter((animation) => animation.transitionProperty === 'scale');
    animations.forEach((animation) => animation.updatePlaybackRate(.1));
    return animations.length;
  });
  assert.equal(pressMotion, 1, 'Press has one finite, inspectable scale transition.');
  await page.waitForTimeout(100);
  assert.ok(await entryButton.evaluate((element) => { const scale = Number.parseFloat(getComputedStyle(element).scale); return scale >= .96 && scale < 1; }), 'Slow-motion presentation stays within the restrained press range.');
  await page.mouse.move(4, 100);
  await page.mouse.up();
  await page.getByRole('tab', { name: '创建账户' }).click();
  await page.getByLabel('玩家昵称（必填）').fill('界面测试');
  await page.getByLabel('邮箱地址（必填）').fill('representative-test@example.local');
  await page.getByLabel('密码（必填）', { exact: true }).fill('IsolatedTest2026!');
  await page.getByLabel('确认密码').fill('IsolatedTest2026!');
  await page.getByRole('button', { name: '创建账户并继续' }).click();
  await expect(page.getByRole('heading', { name: '从今天的想法开始' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '记忆与隐私' })).toBeVisible();
  let current = await state(page);
  assert.equal(current.learningMode, 'off');
  assert.equal(current.cloudConsent, false);
  assert.equal(current.storage, 'encrypted', 'Verify real Windows safeStorage, not a test cipher.');
  const db = JSON.parse(fs.readFileSync(path.join(temporary, 'echoverse-launcher/accounts.json'), 'utf8'));
  assert.equal(db.accounts[0].basicQuestionnaireCompletedAt, undefined, 'Fast start must not fake an empty questionnaire.');
  assert.equal(db.accounts[0].aiAgent.status, 'WAITING_FOR_PROFILE');
  const denied = await page.evaluate(async () => window.launcher.ai.chat({ message: '未授权测试', history: [], temporary: false, privacyEpoch: 0 }));
  assert.equal(denied.ok, false);
  const deniedSimulation = await page.evaluate(async () => window.launcher.ai.simulate({ scenario: '未授权的虚构情境', mode: 'generic', temporary: false, privacyEpoch: 0, expectedRevision: 0 }));
  assert.equal(deniedSimulation.ok, false);
  assert.equal(await application.evaluate(() => global.__representativeRequests.length), 0);
  await capture(page, '01-first-chat');
  const liquidGlass = await checkLiquidGlass({ page, application, screenshots });
  console.log(`Liquid Glass validation: ${JSON.stringify(liquidGlass)}`);
  const liquidGlassInteraction = await checkLiquidGlassInteraction({ page, application });
  fs.writeFileSync(path.join(screenshots, 'liquid-interaction.json'), `${JSON.stringify(liquidGlassInteraction, null, 2)}\n`);
  console.log(`Liquid Glass interaction: ${JSON.stringify(liquidGlassInteraction)}`);

  await expect(page.locator('.chat-window .chat-starters')).toBeVisible();
  await page.getByRole('button', { name: '帮我把一个想法整理清楚', exact: true }).click();
  await expect(page.getByRole('textbox', { name: '发送给数字分身的消息' })).toHaveValue('帮我把一个想法整理清楚');
  const policy = page.locator('.representative-policy-details');
  assert.equal(await policy.evaluate((element) => element.open), false, 'Long policy is disclosed progressively, not removed.');
  await policy.locator('summary').focus();
  await page.keyboard.press('Enter');
  await expect(policy.getByText(/完整聊天记录不落盘/)).toBeVisible();
  await page.keyboard.press('Enter');
  assert.equal(await policy.evaluate((element) => element.open), false);
  const consent = page.getByRole('checkbox', { name: /同意 DeepSeek/ });
  assert.equal(await consent.evaluate((element) => getComputedStyle(element).width), '42px');
  assert.ok(await consent.evaluate((element) => element.closest('label').getBoundingClientRect().height >= 44));
  await page.getByRole('button', { name: '减少透明效果', exact: true }).click();
  await expect(page.locator('.app')).toHaveClass(/ui-glass-reduced/);
  assert.equal(await page.locator('.sidebar').evaluate((element) => getComputedStyle(element).backdropFilter), 'none');
  await capture(page, '21-manual-clear-mode');
  await page.getByRole('button', { name: '减少透明效果', exact: true }).click();
  await page.emulateMedia({ forcedColors: 'active', reducedMotion: 'reduce' });
  assert.equal(await consent.evaluate((element) => getComputedStyle(element).appearance), 'auto', 'High contrast restores a native checkbox.');
  assert.ok(await page.locator('.nav-item.active').evaluate((element) => getComputedStyle(element).color !== getComputedStyle(element).backgroundColor), 'Selected high-contrast navigation keeps distinct text and background.');
  assert.ok(await page.getByRole('button', { name: '发送消息', exact: true }).evaluate((element) => getComputedStyle(element).transitionDuration.split(',').every((duration) => Number.parseFloat(duration) <= .00001)), 'Reduced motion removes perceptible control movement.');
  await capture(page, '22-system-high-contrast');
  await page.emulateMedia({ forcedColors: 'none', reducedMotion: 'no-preference' });
  for (const [navigation, name] of [['首页', '23-home-glass'], ['世界', '24-world-glass'], ['社交', '25-social-glass']]) {
    await page.getByRole('button', { name: navigation, exact: true }).click();
    await expect(page.locator(navigation === '首页' ? '.home-content' : navigation === '世界' ? '.world-content' : '.social-content')).toBeVisible();
    await capture(page, name);
  }
  await page.getByTitle('打开个人主页').click();
  await expect(page.locator('.profile-content')).toBeVisible();
  await capture(page, '26-profile-glass');
  await page.getByRole('navigation', { name: '主要导航', exact: true }).getByRole('button', { name: 'AI 对话', exact: true }).click();

  const composer = page.getByRole('textbox', { name: '发送给数字分身的消息' });
  const beforeAvatar = await state(page);
  await composer.fill('切换外观与重试后仍须保留的草稿');
  if (packageDirectory) {
    await page.getByRole('button', { name: '虚拟分身', exact: true }).click();
    await expect(page.locator('.avatar-content').getByRole('alert')).toContainText('外观暂不可用');
    await expect(page.locator('.avatar-state-badge')).toHaveText('外观暂不可用');
    await page.getByRole('button', { name: '继续文字对话', exact: true }).click();
    await expect(composer).toHaveValue('切换外观与重试后仍须保留的草稿');
  }
  await page.evaluate(() => {
    window.__avatarRetryMarker = 'same-renderer';
    window.__avatarTestMode = 'error';
    window.__avatarTestLoads = 0;
    window.__avatarOriginalFetch = window.fetch;
    window.fetch = async (...args) => {
      const url = typeof args[0] === 'string' ? args[0] : args[0].url;
      if (!url.includes('/models/ecy-avatar.glb')) return window.__avatarOriginalFetch(...args);
      window.__avatarTestLoads++;
      if (window.__avatarTestMode === 'error') throw new TypeError('Isolated test: missing model');
      // Original test geometry, not a redistributed character model.
      const positions = new Float32Array([-1, -1, 0, 1, -1, 0, 0, 1, 0]);
      const json = JSON.stringify({ asset: { version: '2.0' }, scene: 0, scenes: [{ nodes: [0] }],
        nodes: [{ mesh: 0 }], meshes: [{ primitives: [{ attributes: { POSITION: 0 }, mode: 4 }] }],
        buffers: [{ byteLength: 36 }],
        bufferViews: [{ buffer: 0, byteOffset: 0, byteLength: 36 }],
        accessors: [{ bufferView: 0, componentType: 5126, count: 3, type: 'VEC3', min: [-1, -1, 0], max: [1, 1, 0] }] });
      const bytes = new TextEncoder().encode(json.padEnd(Math.ceil(json.length / 4) * 4, ' '));
      const glb = new Uint8Array(28 + bytes.length + positions.byteLength);
      const view = new DataView(glb.buffer);
      [0x46546c67, 2, glb.length, bytes.length, 0x4e4f534a].forEach((value, index) => view.setUint32(index * 4, value, true));
      glb.set(bytes, 20);
      view.setUint32(20 + bytes.length, positions.byteLength, true);
      view.setUint32(24 + bytes.length, 0x004e4942, true);
      glb.set(new Uint8Array(positions.buffer), 28 + bytes.length);
      return new Response(glb, { headers: { 'Content-Type': 'model/gltf-binary' } });
    };
  });
  await page.getByRole('button', { name: '虚拟分身', exact: true }).click();
  const avatar = page.locator('.avatar-content');
  await expect(avatar.getByRole('alert')).toContainText('外观暂不可用');
  await expect(avatar.locator('.avatar-state-badge')).toHaveText('外观暂不可用');
  await expect(avatar.getByText('临时形象已载入', { exact: true })).toHaveCount(0);
  await expect(avatar.getByText('未填写（不影响对话）', { exact: true })).toBeVisible();
  await capture(page, '14-avatar-unavailable');
  await application.evaluate(() => global.__representativeWindow.setSize(1120, 720));
  await capture(page, '15-avatar-small');
  await application.evaluate(() => global.__representativeWindow.webContents.setZoomFactor(1.5));
  await page.emulateMedia({ reducedMotion: 'reduce', contrast: 'more' });
  await avatar.getByRole('button', { name: '重试外观', exact: true }).scrollIntoViewIfNeeded();
  await capture(page, '16-avatar-zoom');
  await avatar.getByRole('button', { name: '重试外观', exact: true }).click();
  await expect(avatar.getByRole('alert')).toContainText('外观暂不可用');
  assert.equal(await page.evaluate(() => window.__avatarRetryMarker), 'same-renderer', 'Retry must not reload the app.');
  assert.deepEqual(await state(page), beforeAvatar, 'Optional 3D must not mutate private state.');
  await application.evaluate(() => { global.__representativeWindow.webContents.setZoomFactor(1); global.__representativeWindow.setSize(1440, 900); });
  await page.emulateMedia({ reducedMotion: 'no-preference', contrast: 'no-preference' });
  await page.evaluate(() => { window.__avatarTestMode = 'fixture'; });
  await avatar.getByRole('button', { name: '重试外观', exact: true }).click();
  await expect(avatar.locator('.avatar-state-badge')).toHaveText('外观已载入');
  await expect(avatar.getByRole('alert')).toHaveCount(0);
  await expect(avatar.locator('canvas')).toHaveCount(1);
  assert.equal(await page.evaluate(() => window.__avatarTestLoads), 3, 'Each retry starts only one model load.');
  await capture(page, '17-avatar-test-geometry');
  await avatar.getByRole('button', { name: '继续文字对话', exact: true }).click();
  await expect(composer).toHaveValue('切换外观与重试后仍须保留的草稿');
  await page.evaluate(() => { window.fetch = window.__avatarOriginalFetch; delete window.__avatarOriginalFetch; });
  await composer.fill('我喜欢爵士乐');
  await page.getByRole('button', { name: '保存到下次', exact: true }).click();
  await page.getByLabel('标题', { exact: true }).fill('下次继续讨论的文字');
  await expect(page.getByRole('textbox', { name: '保存内容', exact: true })).toHaveValue('我喜欢爵士乐');
  await capture(page, '06-save-preview');
  await application.evaluate(() => global.__representativeWindow.setSize(1120, 720));
  await capture(page, '08-small-preview');
  await application.evaluate(() => global.__representativeWindow.webContents.setZoomFactor(1.5));
  await page.emulateMedia({ reducedMotion: 'reduce', contrast: 'more' });
  await page.getByRole('textbox', { name: '保存内容', exact: true }).scrollIntoViewIfNeeded();
  await capture(page, '09-zoom-preview');
  await application.evaluate(() => { global.__representativeWindow.webContents.setZoomFactor(1); global.__representativeWindow.setSize(1440, 900); });
  await page.emulateMedia({ reducedMotion: 'no-preference', contrast: 'no-preference' });
  await page.getByRole('button', { name: '确认加密保存', exact: true }).click();
  await expect.poll(async () => (await state(page)).continuations.length).toBe(1);
  assert.equal((await state(page)).cloudConsent, false);
  assert.equal(await application.evaluate(() => global.__representativeRequests.length), 0, 'Preview/save never contacts a model.');
  await expect(composer).toHaveValue('我喜欢爵士乐');
  await page.getByTitle('打开个人主页').click();
  await page.getByRole('button', { name: '账户安全', exact: true }).click();
  await page.getByRole('button', { name: '退出登录', exact: true }).click();
  await page.getByLabel('邮箱地址（必填）').fill('representative-test@example.local');
  await page.getByLabel('密码（必填）', { exact: true }).fill('IsolatedTest2026!');
  await page.getByRole('button', { name: '进入平台', exact: true }).click();
  await expect(page.getByRole('button', { name: '继续上次的话题或草稿', exact: true })).toHaveCount(1);
  await page.getByRole('button', { name: '继续上次的话题或草稿', exact: true }).click();
  await expect(composer).toHaveValue('我喜欢爵士乐');
  await expect(page.getByRole('button', { name: '放回输入框', exact: true })).toBeDisabled();
  assert.equal(await application.evaluate(() => global.__representativeRequests.length), 0, 'Resume only fills the composer.');
  await capture(page, '07-resumed-draft');

  await page.getByRole('checkbox', { name: /同意 DeepSeek/ }).click();
  await expect(page.getByRole('checkbox', { name: /同意 DeepSeek/ })).toBeChecked();
  await expect(page.getByRole('checkbox', { name: /同意 DeepSeek/ })).toBeEnabled();
  await page.getByLabel('如何使用我的画像').selectOption('learn');
  await expect(page.getByText('低风险偏好学习中', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '发送消息', exact: true }).click();
  await expect(page.getByText('这是隔离测试回复，不是真实模型输出。', { exact: true })).toBeVisible();
  assert.equal((await state(page)).memories.length, 0, 'A restored draft is not evidence, including after changing consent/mode.');
  await page.getByRole('button', { name: '标记完成', exact: true }).click();
  await page.getByRole('button', { name: '完成并移除', exact: true }).click();
  await expect.poll(async () => (await state(page)).continuations.length).toBe(0);
  await page.getByRole('button', { name: '清空本次对话', exact: true }).click();
  await page.getByRole('button', { name: '确认清空', exact: true }).click();
  await expect(page.getByRole('button', { name: '清空本次对话', exact: true })).toBeDisabled();
  await send(page, '我喜欢爵士乐');
  await expect.poll(async () => (await state(page)).memories.length).toBe(1);
  await expect(page.getByText('已记住一条明确偏好，可在下方查看、修正或忘记。')).toBeVisible();
  const legacy = await page.evaluate(async () => window.launcher.auth.completeQuestionnaire({
    fullName: '绝不能上传的旧姓名', gender: '', birthDate: '1991-01-01', residence: '绝不能上传的旧住址',
    occupation: '绝不能上传的旧职业', interests: ['绝不能上传的旧爱好'], mbti: 'INFP', favoriteColor: '',
    favoriteMusic: '', belief: '绝不能上传的旧信仰',
  }));
  assert.equal(legacy.ok, true);
  await page.getByText('查看与管理记忆（1）', { exact: true }).click();
  await capture(page, '02-memory');
  await page.getByLabel(/^明确自述/).selectOption('古典音乐');
  await expect(page.getByLabel(/^本人已修正/)).toHaveValue('古典音乐');

  const beforeSimulation = await state(page);
  const privateDirectory = path.join(temporary, 'echoverse-launcher/representative');
  const encryptedBeforeSimulation = Object.fromEntries(fs.readdirSync(privateDirectory).map((file) => [file, fs.readFileSync(path.join(privateDirectory, file)).toString('base64')]));
  await page.getByRole('button', { name: '私密试答', exact: true }).click();
  await expect(page.getByRole('heading', { name: '试试像不像我', exact: true })).toBeVisible();
  await capture(page, '13-private-start');
  await page.getByRole('textbox', { name: '测试情境', exact: true }).fill('我喜欢电子音乐');
  await page.getByText('先写下我会怎样回应（可选）', { exact: true }).click();
  await page.getByRole('textbox', { name: '我的对照答案', exact: true }).fill('仅在本窗对照：这不是我的真实音乐偏好。');
  for (const mode of ['generic', 'confirmed', 'with_memories']) {
    await page.getByRole('combobox', { name: '本次试答配置', exact: true }).selectOption(mode);
    const before = await application.evaluate(() => global.__representativeRequests.length);
    await page.getByRole('button', { name: '生成当前配置（1次请求）', exact: true }).click();
    await expect(page.getByRole('button', { name: '重新生成当前配置（1次请求）', exact: true })).toBeEnabled();
    assert.equal(await application.evaluate(() => global.__representativeRequests.length), before + 1, 'One click means exactly one request.');
    const request = await application.evaluate(() => global.__representativeRequests.at(-1));
    assert.equal(request.messages.length, 2);
    assert.equal(request.messages[1].content, '我喜欢电子音乐');
    assert.doesNotMatch(JSON.stringify(request), /仅在本窗对照|绝不能上传|这是隔离测试回复/);
    const facts = JSON.parse(request.messages[0].content.split('PERSONA_FACTS:\n')[1]);
    assert.deepEqual(facts.preferences, mode === 'generic' ? {} : { musicGenre: '古典音乐' });
  }
  for (const [dimension, value] of [['没有编造我的事实', 'yes'], ['说话方式像我', 'partly'], ['选择倾向像我', 'no'], ['对我有帮助', 'unknown']]) {
    await page.getByRole('combobox', { name: `通用回复 · ${dimension}`, exact: true }).selectOption(value);
  }
  await expect(page.getByText(/本轮已记录 4 项本人评价/)).toBeVisible();
  assert.deepEqual(await state(page), beforeSimulation, 'Scenarios, answers and feedback never become profile evidence.');
  assert.deepEqual(Object.fromEntries(fs.readdirSync(privateDirectory).map((file) => [file, fs.readFileSync(path.join(privateDirectory, file)).toString('base64')])), encryptedBeforeSimulation, 'Private trials do not write profile/draft/evaluation files.');
  await capture(page, '10-private-comparison');
  await application.evaluate(() => global.__representativeWindow.setSize(1120, 720));
  await capture(page, '11-private-small');
  await application.evaluate(() => global.__representativeWindow.webContents.setZoomFactor(1.5));
  await page.emulateMedia({ reducedMotion: 'reduce', contrast: 'more' });
  await page.getByRole('combobox', { name: '通用回复 · 说话方式像我', exact: true }).scrollIntoViewIfNeeded();
  await capture(page, '12-private-zoom');
  await application.evaluate(() => { global.__representativeWindow.webContents.setZoomFactor(1); global.__representativeWindow.setSize(1440, 900); });
  await page.emulateMedia({ reducedMotion: 'no-preference', contrast: 'no-preference' });
  await page.getByRole('button', { name: '日常对话', exact: true }).click();
  await page.getByRole('button', { name: '私密试答', exact: true }).click();
  await expect(page.getByRole('textbox', { name: '测试情境', exact: true })).toHaveValue('');
  await expect(page.getByRole('region', { name: '通用回复试答', exact: true })).toHaveCount(0);

  await application.evaluate(() => { delete global.__releaseRepresentativeReply; });
  await page.getByRole('textbox', { name: '测试情境', exact: true }).fill('延迟回复测试');
  await page.getByRole('button', { name: '生成当前配置（1次请求）', exact: true }).click();
  await expect.poll(() => application.evaluate(() => Boolean(global.__releaseRepresentativeReply))).toBe(true);
  await page.getByRole('button', { name: '停止生成', exact: true }).click();
  await expect(page.getByText('已停止本次生成，晚到结果不会显示。输入和其他配置的试答保留。')).toBeVisible();
  await application.evaluate(() => global.__releaseRepresentativeReply());
  await expect(page.getByText('不应显示的晚到回复', { exact: true })).toHaveCount(0);
  await expect(page.getByRole('textbox', { name: '测试情境', exact: true })).toHaveValue('延迟回复测试');

  await page.getByRole('textbox', { name: '测试情境', exact: true }).fill('失败试答测试');
  await page.getByRole('button', { name: '生成当前配置（1次请求）', exact: true }).click();
  await expect(page.getByRole('alert').getByText('隔离测试：模拟服务暂不可用。', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '生成当前配置（1次请求）', exact: true }).click();
  await expect(page.getByRole('region', { name: '通用回复试答', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '清空本轮', exact: true }).click();
  await application.evaluate(() => { delete global.__releaseRepresentativeReply; });
  await page.getByRole('textbox', { name: '测试情境', exact: true }).fill('延迟回复测试');
  await page.getByRole('button', { name: '生成当前配置（1次请求）', exact: true }).click();
  await expect.poll(() => application.evaluate(() => Boolean(global.__releaseRepresentativeReply))).toBe(true);
  await page.getByRole('checkbox', { name: /同意 DeepSeek/ }).click();
  await expect.poll(async () => (await state(page)).cloudConsent).toBe(false);
  await application.evaluate(() => global.__releaseRepresentativeReply());
  await expect(page.getByText('不应显示的晚到回复', { exact: true })).toHaveCount(0);
  await expect(page.getByRole('textbox', { name: '测试情境', exact: true })).toHaveValue('');
  await page.getByRole('checkbox', { name: /同意 DeepSeek/ }).click();
  await expect(page.getByRole('checkbox', { name: /同意 DeepSeek/ })).toBeChecked();
  await page.getByRole('button', { name: '日常对话', exact: true }).click();

  await page.getByLabel('如何使用我的画像').selectOption('read_only');
  await expect(page.getByLabel('如何使用我的画像')).toHaveValue('read_only');
  await send(page, '回答请简短一些');
  const request = await application.evaluate(() => global.__representativeRequests.at(-1));
  assert.match(request.messages[0].content, /古典音乐/);
  assert.doesNotMatch(JSON.stringify(request), /绝不能上传|1991-01-01|INFP/);
  assert.equal((await state(page)).memories.length, 1);

  await page.getByRole('checkbox', { name: '临时对话', exact: true }).click();
  await expect(page.getByRole('checkbox', { name: '临时对话', exact: true })).toBeChecked();
  await expect(page.getByRole('checkbox', { name: '临时对话', exact: true })).toBeEnabled();
  await expect(page.getByText('临时对话中不显示、保存或恢复待续内容。', { exact: true })).toBeVisible();
  const temporarySave = await page.evaluate(async () => window.launcher.representative.continuation({ kind: 'save', item: { kind: 'topic', title: '不应保存', content: '临时内容' }, expectedRevision: (await window.launcher.representative.getState()).state.revision }));
  assert.equal(temporarySave.ok, false, 'Main process rejects persistence during temporary chat.');
  await send(page, '我喜欢电子音乐');
  assert.doesNotMatch((await application.evaluate(() => global.__representativeRequests.at(-1))).messages[0].content, /古典音乐/);
  assert.equal((await state(page)).memories.length, 0, 'Temporary state must not disclose stored preferences.');

  await application.evaluate(() => global.__representativeWindow.setSize(1120, 720));
  await capture(page, '03-small-window');
  await application.evaluate(() => global.__representativeWindow.webContents.setZoomFactor(1.5));
  await page.emulateMedia({ reducedMotion: 'reduce', contrast: 'more' });
  await capture(page, '04-zoom-clear');
  await application.evaluate(() => { global.__representativeWindow.webContents.setZoomFactor(1); global.__representativeWindow.setSize(1440, 900); });
  await page.emulateMedia({ reducedMotion: 'no-preference', contrast: 'no-preference' });
  await page.getByRole('checkbox', { name: '临时对话', exact: true }).click();
  await expect(page.getByRole('checkbox', { name: '临时对话', exact: true })).not.toBeChecked();
  await expect(page.getByRole('checkbox', { name: '临时对话', exact: true })).toBeEnabled();
  assert.equal((await state(page)).memories[0].value, '古典音乐', 'Leaving temporary mode reveals the unchanged stored preference, not the temporary message.');
  await page.locator('.representative-memories summary').click();
  await page.getByRole('button', { name: '忘记这条偏好' }).click();
  await expect.poll(async () => (await state(page)).memories.length).toBe(0);
  await page.getByRole('textbox', { name: '发送给数字分身的消息' }).fill('延迟回复测试');
  await page.getByRole('button', { name: '发送消息', exact: true }).click();
  await expect.poll(() => application.evaluate(() => Boolean(global.__releaseRepresentativeReply))).toBe(true);
  await page.getByRole('checkbox', { name: /同意 DeepSeek/ }).click();
  await expect.poll(async () => (await state(page)).cloudConsent).toBe(false);
  await application.evaluate(() => global.__releaseRepresentativeReply());
  await expect(page.getByText('不应显示的晚到回复', { exact: true })).toHaveCount(0);
  await capture(page, '05-revoked');
  await expect(page.getByRole('checkbox', { name: '临时对话', exact: true })).not.toBeChecked();
  await expect(page.getByRole('checkbox', { name: '临时对话', exact: true })).toBeEnabled();
  const maximum = await page.evaluate(async () => {
    for (let index = 0; index < 3; index += 1) {
      const current = await window.launcher.representative.getState();
      if (!current.ok) throw new Error(current.message);
      const saved = await window.launcher.representative.continuation({ kind: 'save', item: { kind: 'draft', title: `容量验证${index}`, content: '测'.repeat(2000) }, expectedRevision: current.state.revision });
      if (!saved.ok) throw new Error(saved.message);
    }
    return window.launcher.representative.getState();
  });
  assert.equal(maximum.ok, true);
  assert.deepEqual(maximum.state.continuations.map((item) => item.content.length), [2000, 2000, 2000], 'Real OS encrypted maximum-size records must remain readable.');

  // A separate isolated account keeps the existing account's request quota intact.
  await page.getByTitle('打开个人主页').click();
  await page.getByRole('button', { name: '账户安全', exact: true }).click();
  await page.getByRole('button', { name: '退出登录', exact: true }).click();
  await page.getByRole('tab', { name: '创建账户' }).click();
  await page.getByLabel('玩家昵称（必填）').fill('暂停学习测试');
  await page.getByLabel('邮箱地址（必填）').fill('learning-pause@example.local');
  await page.getByLabel('密码（必填）', { exact: true }).fill('IsolatedPause2026!');
  await page.getByLabel('确认密码').fill('IsolatedPause2026!');
  await page.getByRole('button', { name: '创建账户并继续' }).click();
  await page.getByRole('checkbox', { name: /同意 DeepSeek/ }).click();
  await expect(page.getByRole('checkbox', { name: /同意 DeepSeek/ })).toBeChecked();
  await expect(page.getByRole('checkbox', { name: /同意 DeepSeek/ })).toBeEnabled();
  await page.getByLabel('如何使用我的画像').selectOption('learn');
  await expect(page.getByText('低风险偏好学习中', { exact: true })).toBeVisible();
  const beforePause = await state(page);
  const filesBeforePause = Object.fromEntries(fs.readdirSync(privateDirectory).map((file) => [file, fs.readFileSync(path.join(privateDirectory, file)).toString('base64')]));
  await composer.fill('角色扮演：失败回复测试');
  await page.getByRole('button', { name: '发送消息', exact: true }).click();
  await expect(page.getByRole('alert').getByText('隔离测试：对话服务暂不可用。', { exact: true })).toBeVisible();
  await expect(page.getByText('本次对话 · 暂停偏好学习', { exact: true })).toBeVisible();
  await expect(page.locator('.representative-mode')).toHaveText('本次对话已暂停偏好学习 · 0 条记忆');
  assert.equal((await page.evaluate(() => window.launcher.representative.getState())).learningPaused, true);
  assert.deepEqual(await state(page), beforePause);
  assert.deepEqual(Object.fromEntries(fs.readdirSync(privateDirectory).map((file) => [file, fs.readFileSync(path.join(privateDirectory, file)).toString('base64')])), filesBeforePause, 'A safety pause must not write profile, ledger or evidence files.');
  await composer.fill('清空本次对话后仍须保留的草稿');
  await capture(page, '18-learning-paused');
  await application.evaluate(() => global.__representativeWindow.setSize(1120, 720));
  await capture(page, '19-learning-paused-small');
  await application.evaluate(() => global.__representativeWindow.webContents.setZoomFactor(2));
  await page.emulateMedia({ reducedMotion: 'reduce', contrast: 'more' });
  await page.locator('.representative-mode').scrollIntoViewIfNeeded();
  await capture(page, '20-learning-paused-zoom');
  await application.evaluate(() => { global.__representativeWindow.webContents.setZoomFactor(1); global.__representativeWindow.setSize(1440, 900); });
  await page.emulateMedia({ reducedMotion: 'no-preference', contrast: 'no-preference' });
  await page.getByRole('button', { name: '清空本次对话', exact: true }).click();
  await page.getByRole('button', { name: '确认清空', exact: true }).click();
  await expect(page.getByText('低风险偏好学习中', { exact: true })).toBeVisible();
  await expect(composer).toHaveValue('清空本次对话后仍须保留的草稿');
  assert.equal((await page.evaluate(() => window.launcher.representative.getState())).learningPaused, false);
  await send(page, '我喜欢爵士乐');
  await expect.poll(async () => (await state(page)).memories.length).toBe(1);
  await page.getByRole('checkbox', { name: /同意 DeepSeek/ }).click();
  await expect(page.getByText('当前对话 · 云端处理未授权', { exact: true })).toBeVisible();
  await expect(page.getByText('低风险偏好学习中', { exact: true })).toHaveCount(0);

  const temporaryPrivacy = await checkTemporaryPrivacy({ page, application, screenshots });
  console.log(`Temporary privacy validation: ${JSON.stringify(temporaryPrivacy)}`);

  // A concurrent, valid edit makes the rendered reset revision stale without
  // replacing IPC handlers or manufacturing a successful deletion.
  await page.getByRole('button', { name: '重置对话画像与授权', exact: true }).click();
  const beforeFailedReset = await page.evaluate(async () => {
    const current = await window.launcher.representative.getState();
    if (!current.ok) throw new Error(current.message);
    const updated = await window.launcher.representative.update({ kind: 'mode', mode: current.state.learningMode, expectedRevision: current.state.revision });
    if (!updated.ok) throw new Error(updated.message);
    return updated.state;
  });
  await page.getByRole('button', { name: '确认重置', exact: true }).click();
  await expect(page.locator('.chat-error')).toContainText('内容已有变化');
  await expect(page.getByRole('button', { name: '确认重置', exact: true })).toBeEnabled();
  assert.deepEqual((await state(page)).memories, beforeFailedReset.memories, 'A rejected reset must not pretend to delete the saved preferences.');
  await application.evaluate(() => global.__representativeWindow.setSize(1120, 720));
  await page.locator('.chat-error').scrollIntoViewIfNeeded();
  await capture(page, '36-privacy-update-failed');
  await application.evaluate(() => global.__representativeWindow.setSize(1440, 900));
  await page.getByRole('button', { name: '确认重置', exact: true }).click();
  await expect(page.getByRole('button', { name: '重置对话画像与授权', exact: true })).toBeVisible();
  await expect(page.locator('.chat-error')).toHaveCount(0);
  assert.equal((await state(page)).memories.length, 0, 'Retrying with the recovered revision must complete the isolated reset.');
  console.log('Privacy mutation feedback passed: real revision conflict, persistent failure alert, preserved data and confirmation, successful retry; no added model request.');
  const chatStop = await checkChatStop({ page, application, capture: (name) => capture(page, name) });
  console.log(`Daily chat stop validation: ${JSON.stringify(chatStop)}`);
  assert.equal(errors.length, 0, errors.join('\n'));
  if (packageDirectory) {
    const { auditPackage } = require('./audit-local-package.cjs');
    const manifest = auditPackage(packageDirectory);
    fs.writeFileSync(path.join(packageDirectory, 'representative-smoke.json'), `${JSON.stringify({ passed: true, createdAt: new Date().toISOString(), asarSha256: manifest.asarSha256, liquidGlass, liquidGlassInteraction, temporaryPrivacy, chatStop,
      scope: 'Actual packaged executable and unchanged ASAR; isolated accounts and runtime-only mocks/geometry; glass and clear/forced-color modes, keyboard disclosures, synthesized press at 10% playback, loaded-page screenshots; avatar/privacy/continuations/private trials and pause/recovery; no paid requests, game startup or similarity evaluation.', screenshots: path.basename(screenshots) }, null, 2)}\n`);
    assert.equal(manifest.asarSha256, JSON.parse(fs.readFileSync(path.join(packageDirectory, 'acceptance-manifest.json'), 'utf8')).asarSha256);
  }
  console.log('Desktop E2E passed: glass/clear/forced-color modes, keyboard disclosures, constrained press at 10% playback, loaded-page captures; learning pause/recovery, avatar retry, private trials, continuations, temporary mode and real OS encryption. Screenshots at 1440x900, 1120x720, 150% and 200% zoom. No real model requests or subjective similarity claims.');
})().catch((error) => { console.error(error); process.exitCode = 1; }).finally(async () => {
  if (application) await application.close().catch(() => undefined);
  assert.equal(path.dirname(temporary), os.tmpdir());
  assert.ok(path.basename(temporary).startsWith('echoverse-representative-ui-'));
  fs.rmSync(temporary, { recursive: true, force: true, maxRetries: 4, retryDelay: 200 });
});
