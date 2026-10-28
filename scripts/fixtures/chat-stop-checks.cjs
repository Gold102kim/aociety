// Isolated UI cancellation checks; never loaded by the product or included in ASAR.
const assert = require('node:assert/strict');
const { expect } = require('playwright/test');

async function checkChatStop({ page, application, capture }) {
  const stopped = '已停止生成。已发送的消息和输入草稿保留；已发送到云端的内容无法撤回。';
  const blocked = '无法确认请求已停止，已暂停发送。请重试停止，或清空本次对话。';
  const composer = page.getByRole('textbox', { name: '发送给数字分身的消息', exact: true });
  const temporarySwitch = page.getByRole('checkbox', { name: '临时对话', exact: true });
  const messages = () => page.locator('.chat-messages .chat-message:not(.typing) p').allTextContents();
  const requests = () => application.evaluate(() => global.__representativeRequests.length);
  const read = async () => {
    const result = await page.evaluate(() => window.launcher.representative.getState());
    assert.equal(result.ok, true, 'The isolated chat-stop account must remain readable.');
    return result;
  };
  const settleRenderer = () => page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const startDelayedReply = async () => {
    await application.evaluate(() => { delete global.__releaseRepresentativeReply; delete global.__rejectRepresentativeReply; });
    await composer.fill('延迟回复测试');
    await page.getByRole('button', { name: '发送消息', exact: true }).click();
    await expect.poll(() => application.evaluate(() => typeof global.__releaseRepresentativeReply)).toBe('function');
    await expect(page.getByRole('button', { name: '停止生成', exact: true })).toBeEnabled();
  };
  const settleDelayedReply = async (fail) => {
    const completed = await application.evaluate(() => global.__chatStopControls.completed);
    await application.evaluate((reject) => {
      if (reject) global.__rejectRepresentativeReply(new Error('隔离测试：停止后晚到失败。'));
      else global.__releaseRepresentativeReply();
    }, fail);
    await expect.poll(() => application.evaluate(() => global.__chatStopControls.completed)).toBe(completed + 1);
    await settleRenderer();
    await expect(page.getByText('不应显示的晚到回复', { exact: true })).toHaveCount(0);
    await expect(page.getByText('隔离测试：停止后晚到失败。', { exact: true })).toHaveCount(0);
  };
  const tryBlockedSubmit = async () => {
    const before = await requests();
    await composer.press('Control+Enter');
    await composer.evaluate((element) => element.form.requestSubmit());
    await settleRenderer();
    assert.equal(await requests(), before, 'A pending or failed stop must block both keyboard and form submission.');
    await expect(page.getByRole('button', { name: '发送消息', exact: true })).toHaveCount(0);
    await expect(page.getByRole('button', { name: '保存到下次', exact: true })).toBeDisabled();
  };
  const resumeSending = async (draft) => {
    const before = await requests();
    const replies = page.locator('.chat-messages .chat-message.assistant p').filter({ hasText: '这是隔离测试回复，不是真实模型输出。' });
    const replyCount = await replies.count();
    await expect(composer).toHaveValue(draft);
    await page.getByRole('button', { name: '发送消息', exact: true }).click();
    await expect(replies).toHaveCount(replyCount + 1);
    assert.equal(await requests(), before + 1, 'After confirmed cancellation, an explicit send makes exactly one mock request.');
    await expect(page.getByText(stopped, { exact: true })).toHaveCount(0);
  };

  const initial = await read();
  assert.equal(initial.temporary, false);
  assert.equal(initial.state.cloudConsent, false);
  assert.equal(initial.state.learningMode, 'off');
  assert.equal(initial.state.memories.length, 0, 'This fixture follows the isolated reset test.');
  assert.equal(initial.state.continuations.length, 0);
  const beforeRequests = await requests();
  let instrumented = false;
  let failure;
  try {
    await application.evaluate(({ ipcMain }) => {
      const handlers = ipcMain._invokeHandlers;
      if (!(handlers instanceof Map) || typeof handlers.get('ai:cancel') !== 'function' || typeof handlers.get('ai:chat') !== 'function') {
        throw new Error('The isolated chat-stop IPC instrumentation no longer matches Electron.');
      }
      const originalCancel = handlers.get('ai:cancel');
      const originalChat = handlers.get('ai:chat');
      const control = { originalCancel, originalChat, completed: 0, pureCancelCalls: 0, failNextCancel: false, holdCancel: false };
      global.__chatStopControls = control;
      ipcMain.removeHandler('ai:cancel');
      ipcMain.handle('ai:cancel', async (event, ...args) => {
        // The preload forwards an omitted mode as one undefined IPC argument.
        if (args[0] === undefined) {
          control.pureCancelCalls += 1;
          if (control.failNextCancel) { control.failNextCancel = false; throw new Error('隔离测试：取消确认失败。'); }
          if (control.holdCancel) await new Promise((resolve) => { control.releaseCancel = resolve; });
        }
        return originalCancel(event, ...args);
      });
      ipcMain.removeHandler('ai:chat');
      ipcMain.handle('ai:chat', async (...args) => {
        try { return await originalChat(...args); }
        finally { control.completed += 1; }
      });
    });
    instrumented = true;
    await page.getByRole('checkbox', { name: /同意 DeepSeek/ }).click();
    await expect(page.getByRole('checkbox', { name: /同意 DeepSeek/ })).toBeChecked();
    await expect(page.getByRole('checkbox', { name: /同意 DeepSeek/ })).toBeEnabled();
    await page.getByLabel('如何使用我的画像').selectOption('learn');
    await expect(page.getByText('低风险偏好学习中', { exact: true })).toBeVisible();
    await composer.fill('角色扮演：失败回复测试');
    await page.getByRole('button', { name: '发送消息', exact: true }).click();
    await expect(page.getByRole('alert').getByText('隔离测试：对话服务暂不可用。', { exact: true })).toBeVisible();
    await expect(page.getByText('本次对话 · 暂停偏好学习', { exact: true })).toBeVisible();

    await startDelayedReply();
    const regularDraft = '停止后仍须保留的输入草稿';
    await composer.fill(regularDraft);
    const regularMessages = await messages();
    const regularState = await read();
    assert.equal(regularState.learningPaused, true);
    await application.evaluate(() => { global.__chatStopControls.holdCancel = true; });
    await page.getByRole('button', { name: '停止生成', exact: true }).click();
    await expect(page.getByRole('button', { name: '正在停止…', exact: true })).toBeDisabled();
    await expect(page.getByText('正在确认停止，输入草稿仍可编辑。', { exact: true })).toBeVisible();
    await expect.poll(() => application.evaluate(() => typeof global.__chatStopControls.releaseCancel)).toBe('function');
    await tryBlockedSubmit();
    await settleDelayedReply(false);
    await expect(page.getByText(stopped, { exact: true })).toHaveCount(0);
    assert.deepEqual(await messages(), regularMessages, 'Stopping must not clear the transcript or append a late success.');
    await expect(composer).toHaveValue(regularDraft);
    await application.evaluate(() => { global.__chatStopControls.holdCancel = false; global.__chatStopControls.releaseCancel(); });
    await expect(page.getByText(stopped, { exact: true })).toBeVisible();
    assert.deepEqual(await read(), regularState, 'Pure cancellation preserves regular privacy, paused learning and stored content.');
    await expect(page.getByText('本次对话 · 暂停偏好学习', { exact: true })).toBeVisible();
    await capture('37-chat-stopped');
    await resumeSending(regularDraft);

    await temporarySwitch.click();
    await expect(temporarySwitch).toBeChecked();
    await expect(temporarySwitch).toBeEnabled();
    await startDelayedReply();
    const temporaryDraft = '临时停止后仍须保留的输入草稿';
    await composer.fill(temporaryDraft);
    const temporaryMessages = await messages();
    const temporaryState = await read();
    assert.equal(temporaryState.temporary, true);
    await application.evaluate(() => { global.__chatStopControls.failNextCancel = true; });
    await page.getByRole('button', { name: '停止生成', exact: true }).click();
    await expect(page.getByRole('alert').getByText(blocked, { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: '重试停止', exact: true })).toBeEnabled();
    await expect(page.getByText(stopped, { exact: true })).toHaveCount(0);
    await tryBlockedSubmit();
    await settleDelayedReply(true);
    await expect(page.getByRole('alert').getByText(blocked, { exact: true })).toBeVisible();
    assert.deepEqual(await messages(), temporaryMessages, 'A late failure must not clear the transcript or replace the stop failure.');
    await expect(composer).toHaveValue(temporaryDraft);
    await application.evaluate(() => global.__representativeWindow.setSize(1120, 720));
    await capture('38-chat-stop-retry');
    await application.evaluate(() => global.__representativeWindow.setSize(1440, 900));
    await page.getByRole('button', { name: '重试停止', exact: true }).click();
    await expect(page.getByText(stopped, { exact: true })).toBeVisible();
    await expect(page.getByRole('alert').getByText(blocked, { exact: true })).toHaveCount(0);
    assert.deepEqual(await read(), temporaryState, 'Retrying pure cancellation cannot leave temporary mode or alter its privacy state.');
    await expect(temporarySwitch).toBeChecked();
    await resumeSending(temporaryDraft);
    const mockRequestsAdded = await requests() - beforeRequests;
    assert.equal(mockRequestsAdded, 5, 'Only the five explicit fixture messages may reach the mock transport.');
    assert.equal(await application.evaluate(() => global.__chatStopControls.pureCancelCalls), 3);
    return { passed: true, regularTranscriptAndDraftPreserved: true, learningPausePreserved: true, temporaryModePreserved: true,
      pendingAndFailedStopBlockSend: true, lateSuccessAndFailureIgnored: true, failureRetryPassed: true, sendingResumed: true,
      mockRequestsAdded, screenshots: 2, scope: 'Isolated actual renderer and IPC; runtime-only cancellation fault injection, no paid or external model requests.' };
  } catch (error) {
    failure = error;
    throw error;
  } finally {
    try {
      if (instrumented) await application.evaluate(({ ipcMain }) => {
        const control = global.__chatStopControls;
        control.holdCancel = false;
        control.releaseCancel?.();
        global.__releaseRepresentativeReply?.();
        ipcMain.removeHandler('ai:cancel'); ipcMain.handle('ai:cancel', control.originalCancel);
        ipcMain.removeHandler('ai:chat'); ipcMain.handle('ai:chat', control.originalChat);
        delete global.__chatStopControls;
        delete global.__releaseRepresentativeReply;
        delete global.__rejectRepresentativeReply;
        global.__representativeWindow.setSize(1440, 900);
      });
      await page.evaluate(async () => {
        await window.launcher.ai.cancel(false);
        const current = await window.launcher.representative.getState();
        if (!current.ok) throw new Error('Isolated chat-stop cleanup could not read settings.');
        const reset = await window.launcher.representative.update({ kind: 'reset', expectedRevision: current.state.revision });
        if (!reset.ok || reset.state.cloudConsent || reset.state.learningMode !== 'off') throw new Error('Isolated chat-stop cleanup could not reset its test settings.');
      });
    } catch {
      if (!failure) throw new Error('Isolated chat-stop fixture cleanup failed.');
      console.warn('Chat-stop cleanup incomplete; isolated application teardown remains responsible for removal.');
    }
  }
}

module.exports = { checkChatStop };
