// Isolated IPC and renderer-lifetime checks; never loaded by the product.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { expect } = require('playwright/test');

async function checkTemporaryPrivacy({ page, application, screenshots }) {
  const originalUrl = page.url();
  const item = { kind: 'draft', title: '临时边界隔离测试标题', content: '临时边界隔离测试正文，不发送给模型。' };
  const requestCount = () => application.evaluate(() => global.__representativeRequests.length);
  const read = () => page.evaluate(() => window.launcher.representative.getState());
  const same = (actual, expected, message) => assert.equal(JSON.stringify(actual) === JSON.stringify(expected), true, message);
  const success = (result) => {
    assert.equal(result.ok, true, 'The isolated account must have readable private state.');
    return result;
  };
  const projected = (result) => {
    success(result);
    assert.equal(result.temporary, true, 'Main-process temporary metadata must be authoritative.');
    assert.equal(result.state.memories.length, 0, 'Temporary IPC responses contain no memory records.');
    assert.equal(result.state.continuations.length, 0, 'Temporary IPC responses contain no saved content.');
    const serialized = JSON.stringify(result);
    assert.equal(['爵士乐', item.title, item.content].some((text) => serialized.includes(text)), false, 'Temporary IPC responses must not leak stored plaintext.');
    return result;
  };
  const temporarySwitch = () => page.getByRole('checkbox', { name: '临时对话', exact: true });
  const toggle = async (enabled) => {
    await expect(temporarySwitch()).toBeEnabled();
    if (await temporarySwitch().isChecked() !== enabled) await temporarySwitch().click();
    if (enabled) await expect(temporarySwitch()).toBeChecked();
    else await expect(temporarySwitch()).not.toBeChecked();
    await expect(temporarySwitch()).toBeEnabled();
    await expect.poll(async () => (await read()).temporary).toBe(enabled);
  };
  const capture = async (name) => {
    await page.waitForTimeout(180);
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'Privacy captures must have no horizontal overflow.');
    const frame = () => application.evaluate(async () => {
      const image = await global.__representativeWindow.webContents.capturePage(undefined, { stayHidden: true, stayAwake: true });
      if (image.isEmpty()) throw new Error('Hidden-window privacy capture was empty.');
      return image.toPNG().toString('base64');
    });
    const png = await frame().catch(async (error) => {
      if (!String(error).includes('UnknownVizError')) throw error;
      await page.waitForTimeout(100);
      return frame();
    });
    fs.writeFileSync(path.join(screenshots, `${name}.png`), Buffer.from(png, 'base64'));
  };
  const login = async () => {
    await page.getByLabel('邮箱地址（必填）').fill('learning-pause@example.local');
    await page.getByLabel('密码（必填）', { exact: true }).fill('IsolatedPause2026!');
    await page.getByRole('button', { name: '进入平台', exact: true }).click();
    await expect(page.getByRole('heading', { name: '记忆与隐私', exact: true })).toBeVisible();
    await expect(temporarySwitch()).toBeEnabled();
  };

  const initial = structuredClone(success(await read()));
  const original = initial.state;
  assert.equal(initial.temporary, false, 'This fixture starts outside temporary mode.');
  assert.equal(original.cloudConsent, false, 'Cloud consent must remain revoked throughout this fixture.');
  assert.equal(original.learningMode, 'learn');
  assert.equal(original.memories.some((memory) => memory.value === '爵士乐'), true, 'The isolated learning fixture provides one known preference.');
  assert.ok(original.continuations.length < 3, 'The fixture needs one free saved-content slot.');
  const requestsBefore = await requestCount();
  let createdId;
  let failure;
  try {
    const saved = success(await page.evaluate(({ value, revision }) => window.launcher.representative.continuation({
      kind: 'save', item: value, expectedRevision: revision,
    }), { value: item, revision: original.revision }));
    const created = saved.state.continuations.find((entry) => entry.title === item.title && entry.content === item.content);
    assert.equal(Boolean(created), true, 'Explicitly saved fake content must persist before temporary mode.');
    createdId = created.id;
    const savedContinuations = structuredClone(saved.state.continuations);
    same(saved.state.memories, original.memories, 'Saving fake content must not change existing memories.');
    assert.equal(saved.state.privacyEpoch, original.privacyEpoch, 'Saving content does not change privacy authorization.');

    await toggle(true);
    let temporary = projected(await read());
    await expect(page.getByText('临时对话中不显示、保存或恢复待续内容。', { exact: true })).toBeVisible();
    assert.equal(await page.locator('.continuity-item').count(), 0, 'The temporary UI must unmount saved-content rows.');
    assert.equal(await page.getByText(item.title, { exact: true }).count(), 0, 'The temporary UI must not retain a saved title.');

    // A same-value mode update exercises the other successful IPC response path.
    temporary = projected(await page.evaluate((revision) => window.launcher.representative.update({
      kind: 'mode', mode: 'learn', expectedRevision: revision,
    }), temporary.state.revision));
    const expectedPrivacyEpoch = original.privacyEpoch + 1;
    assert.equal(temporary.state.privacyEpoch, expectedPrivacyEpoch, 'The deliberate same-value mode update has the normal privacy epoch increment.');
    const denied = await page.evaluate(async ({ id, value }) => {
      const current = await window.launcher.representative.getState();
      if (!current.ok) throw new Error('Isolated temporary state was unavailable.');
      const save = await window.launcher.representative.continuation({ kind: 'save', item: value, expectedRevision: current.state.revision });
      const resume = await window.launcher.representative.continuation({ kind: 'resume', id, expectedRevision: current.state.revision });
      return { save, resume };
    }, { id: createdId, value: item });
    assert.equal(denied.save.ok, false, 'Direct IPC cannot save in temporary mode.');
    assert.equal(denied.resume.ok, false, 'Direct IPC cannot resume in temporary mode.');
    assert.equal(['爵士乐', item.title, item.content].some((text) => JSON.stringify(denied).includes(text)), false, 'Rejected continuation responses cannot leak stored plaintext.');

    await page.evaluate(() => window.launcher.ai.cancel());
    const afterCancel = projected(await read());
    assert.equal(afterCancel.learningPaused, temporary.learningPaused, 'Pure cancellation must preserve the learning safety flag.');
    await page.evaluate(() => {
      window.__temporaryPrivacyMarker = true;
      location.hash = 'temporary-privacy-same-document';
    });
    await page.waitForURL((url) => url.hash === '#temporary-privacy-same-document');
    assert.equal(await page.evaluate(() => window.__temporaryPrivacyMarker), true, 'Hash navigation retains the existing renderer.');
    projected(await read());
    await expect(page.getByRole('heading', { name: '记忆与隐私', exact: true })).toBeVisible();
    await expect(temporarySwitch()).toBeChecked();
    await page.evaluate((url) => history.replaceState(null, '', url), originalUrl);
    await capture('33-temp-privacy');

    await page.reload();
    await expect(page.getByRole('button', { name: '进入平台', exact: true })).toBeVisible();
    assert.equal((await read()).ok, false, 'A full renderer reload must require a fresh login.');
    assert.equal(await requestCount(), requestsBefore, 'Reload and privacy operations do not issue model requests.');
    await capture('34-reload-logged-out');
    await login();
    let restored = success(await read());
    assert.equal(restored.temporary, false, 'A new authenticated session defaults to regular mode.');
    await expect(temporarySwitch()).not.toBeChecked();
    same(restored.state.memories, original.memories, 'Reload preserves encrypted preferences without modifying their evidence.');
    same(restored.state.continuations, savedContinuations, 'Reload preserves the complete explicitly saved content.');
    assert.equal(restored.state.cloudConsent, false, 'Reload must not regrant cloud consent.');
    assert.equal(restored.state.learningMode, original.learningMode, 'Reload preserves the chosen learning mode.');
    assert.equal(restored.state.privacyEpoch, expectedPrivacyEpoch, 'Reload does not mutate persistent privacy settings.');
    await expect(page.locator('.continuity-item').filter({ hasText: item.title })).toBeVisible();
    await capture('35-relogin-restored');

    await toggle(true);
    projected(await read());
    await toggle(false);
    restored = success(await read());
    assert.equal(restored.temporary, false);
    same(restored.state.memories, original.memories, 'Explicitly leaving temporary mode restores the complete memory projection.');
    same(restored.state.continuations, savedContinuations, 'Explicitly leaving temporary mode restores the complete saved-content projection.');
    await expect(page.locator('.continuity-item').filter({ hasText: item.title })).toBeVisible();
    const removed = success(await page.evaluate(({ id, revision }) => window.launcher.representative.continuation({
      kind: 'remove', id, expectedRevision: revision,
    }), { id: createdId, revision: restored.state.revision }));
    createdId = undefined;
    same(removed.state.memories, original.memories, 'Fixture cleanup leaves the original memories unchanged.');
    same(removed.state.continuations, original.continuations, 'Fixture cleanup removes only its own fake saved content.');
    assert.equal(removed.state.cloudConsent, false);
    assert.equal(removed.state.learningMode, original.learningMode);
    assert.equal(removed.state.privacyEpoch, expectedPrivacyEpoch, 'Continuation cleanup does not change privacy authorization.');
    // Refresh the visible projection after the direct cleanup IPC.
    await toggle(true);
    await toggle(false);
    assert.equal(await requestCount(), requestsBefore, 'This entire fixture must make zero model requests.');
    return { passed: true, ipcPlaintextProjection: true, temporaryCancelPreserved: true, sameDocumentSessionPreserved: true,
      fullReloadLoggedOut: true, reloginRestored: true, explicitExitRestored: true, originalMemoriesPreserved: true,
      fakeContinuationRemoved: true, modelRequestsAdded: 0, screenshots: 3 };
  } catch (error) {
    failure = error;
    throw error;
  } finally {
    try {
      await page.evaluate((url) => history.replaceState(null, '', url), originalUrl);
      if (createdId) {
        let current = await read();
        if (!current.ok) { await login(); current = await read(); }
        success(current);
        if (current.temporary) {
          await page.evaluate(() => window.launcher.ai.cancel(false));
          current = success(await read());
        }
        success(await page.evaluate(({ id, revision }) => window.launcher.representative.continuation({
          kind: 'remove', id, expectedRevision: revision,
        }), { id: createdId, revision: current.state.revision }));
      }
    } catch {
      if (!failure) throw new Error('Isolated temporary-privacy fixture cleanup failed.');
      console.warn('Temporary privacy fixture cleanup incomplete; isolated account directory teardown remains responsible for removal.');
    }
  }
}

module.exports = { checkTemporaryPrivacy };
