const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const http = require('node:http');
const { EventEmitter, once } = require('node:events');
const { stripTypeScriptTypes } = require('node:module');
const { waitForServiceHealth } = require('../dist-electron/service-health.js');

function testRenderScheduler() {
  const source = fs.readFileSync(path.join(__dirname, '..', 'src', 'renderScheduler.ts'), 'utf8');
  const output = stripTypeScriptTypes(source.replace('export function', 'function'));
  const exports = {};
  vm.runInNewContext(`${output}\nexports.createRenderScheduler = createRenderScheduler;`, { exports });
  let now = 0;
  let nextId = 0;
  let visible = true;
  const frames = new Map();
  const timers = new Map();
  const rendered = [];
  const scheduler = exports.createRenderScheduler((timestamp) => {
    rendered.push(timestamp);
    scheduler.request();
  }, () => visible, {
    now: () => now,
    frame: (callback) => { frames.set(++nextId, callback); return nextId; },
    cancelFrame: (id) => frames.delete(id),
    timer: (callback, delay) => { timers.set(++nextId, { callback, due: now + delay }); return nextId; },
    cancelTimer: (id) => timers.delete(id),
  });
  function advanceTo(timestamp) {
    while (now < timestamp) {
      now += 1;
      for (const [id, timer] of [...timers]) {
        if (timer.due <= now) { timers.delete(id); timer.callback(); }
      }
      if (now % 8 === 0) {
        for (const [id, callback] of [...frames]) { frames.delete(id); callback(now); }
      }
    }
  }
  scheduler.request();
  scheduler.request();
  assert.equal(frames.size, 1, 'Duplicate resize/control events must coalesce.');
  advanceTo(1000);
  assert.ok(rendered.length <= 31 && rendered.length >= 20, `Frame budget exceeded: ${rendered.length}`);
  for (let i = 1; i < rendered.length; i++) assert.ok(rendered[i] - rendered[i - 1] >= 32);
  visible = false;
  scheduler.pause();
  const count = rendered.length;
  advanceTo(2000);
  scheduler.request();
  assert.equal(rendered.length, count, 'Hidden avatar must not render.');
  assert.equal(frames.size + timers.size, 0, 'Hidden avatar must not keep timers alive.');
  visible = true;
  scheduler.request();
  advanceTo(2016);
  assert.ok(rendered.length > count, 'Visible avatar must resume.');
  scheduler.dispose();
  scheduler.request();
  advanceTo(3000);
  assert.equal(frames.size + timers.size, 0, 'Unmount must cancel all callbacks.');
}

function testChatInteraction() {
  const source = fs.readFileSync(path.join(__dirname, '..', 'src', 'chatConversation.ts'), 'utf8');
  const output = stripTypeScriptTypes(source.replace(/export function/g, 'function'));
  const exports = {};
  vm.runInNewContext(`${output}\nexports.getRecentChatHistory = getRecentChatHistory; exports.isChatSendShortcut = isChatSendShortcut;`, { exports });
  const messages = [{ id: 'welcome', role: 'assistant', content: 'local greeting' },
    ...Array.from({ length: 40 }, (_, i) => ({ id: String(i), role: i % 2 ? 'assistant' : 'user', content: String(i) }))];
  const history = exports.getRecentChatHistory(messages);
  assert.equal(history.length, 12);
  assert.equal(history[0].id, '28');
  assert.equal(history[11].id, '39');
  assert.equal(messages.length, 41, 'Context trimming must preserve the visible conversation.');
  assert.equal(exports.getRecentChatHistory([messages[0]]).length, 0);
  const shortcut = { key: 'Enter', ctrlKey: true, metaKey: false, isComposing: false };
  assert.equal(exports.isChatSendShortcut(shortcut), true);
  assert.equal(exports.isChatSendShortcut({ ...shortcut, ctrlKey: false, metaKey: true }), true);
  assert.equal(exports.isChatSendShortcut({ ...shortcut, ctrlKey: false }), false, 'Plain Enter must keep adding a newline.');
  assert.equal(exports.isChatSendShortcut({ ...shortcut, isComposing: true }), false, 'IME input must not submit.');
}

async function testServiceHealth() {
  let healthy = false;
  const server = http.createServer((_request, response) => {
    if (healthy) { response.writeHead(200); response.end('ok'); }
    // Otherwise leave the probe hanging to verify that process exit aborts it.
  });
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const url = `http://127.0.0.1:${server.address().port}/health`;
  const child = () => Object.assign(new EventEmitter(), { exitCode: null, signalCode: null });
  try {
    const crashed = child();
    const start = performance.now();
    const pending = waitForServiceHealth(crashed, url, 30000);
    setTimeout(() => { crashed.exitCode = 1; crashed.emit('exit', 1); }, 25);
    await assert.rejects(pending, /服务进程已退出/);
    assert.ok(performance.now() - start < 1500, 'Child exit must interrupt a pending health fetch.');
    assert.equal(crashed.listenerCount('exit'), 0);
    const alreadyExited = child();
    alreadyExited.exitCode = 1;
    await assert.rejects(waitForServiceHealth(alreadyExited, url, 30000), /服务进程已退出/);
    const alive = child();
    const deadlineStart = performance.now();
    assert.equal(await waitForServiceHealth(alive, url, 100), false);
    assert.ok(performance.now() - deadlineStart < 1000, 'Startup deadline must bound a hanging health fetch.');
    assert.equal(alive.listenerCount('exit'), 0);
    healthy = true;
    assert.equal(await waitForServiceHealth(child(), url, 1000), true);
  } finally {
    server.closeAllConnections();
    await new Promise((resolve) => server.close(resolve));
  }
}

testRenderScheduler();
testChatInteraction();
testServiceHealth().then(() => console.log('Rendering budget, service startup and chat interaction regression tests passed.')).catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
