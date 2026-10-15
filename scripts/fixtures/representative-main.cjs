// Isolated UI test entry. Never loaded by the shipped application.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { app, BrowserWindow } = require('electron');
const Module = require('node:module');
const root = process.env.ECHO_REPRESENTATIVE_TEST_ROOT;
if (!root || path.dirname(root) !== os.tmpdir() || !path.basename(root).startsWith('echoverse-representative-ui-')) {
  throw new Error('This fixture requires its own generated temporary directory.');
}
app.setPath('appData', root);
app.disableHardwareAcceleration();
app.on('browser-window-created', (_event, window) => window.webContents.setBackgroundThrottling(false));
BrowserWindow.prototype.show = function () {};
BrowserWindow.prototype.focus = function () {};
class TestWindow extends BrowserWindow {
  constructor(options) {
    super({ ...options, show: false, webPreferences: { ...options.webPreferences, offscreen: true } });
    global.__representativeWindow = this;
  }
}
global.__representativeTestWindow = TestWindow;
const data = path.join(root, 'echoverse-launcher');
fs.mkdirSync(data, { recursive: true });
fs.writeFileSync(path.join(data, 'ai.json'), JSON.stringify({ provider: 'deepseek', apiKey: 'isolated-test-key-not-real', model: 'deepseek-test' }));
require('./representative-transport.cjs')();
const mainPath = path.resolve(__dirname, '../../dist-electron/main.js');
const source = fs.readFileSync(mainPath, 'utf8');
if (!source.includes('new electron_1.BrowserWindow({')) throw new Error('Window test instrumentation no longer matches the built application.');
const instrumented = new Module(mainPath, module);
instrumented.filename = mainPath;
instrumented.paths = module.paths;
instrumented._compile(source.replaceAll('new electron_1.BrowserWindow({', 'new global.__representativeTestWindow({'), mainPath);
