const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const runtimePython = process.env.AOCIETY_PYTHON_PATH
  || path.resolve(root, '..', 'runtime', 'aociety-python', 'Scripts', 'python.exe');
const unrealCandidates = [
  process.env.UE_EDITOR_PATH,
  'D:\\UE_5.8\\Engine\\Binaries\\Win64\\UnrealEditor.exe',
  'C:\\Program Files\\Epic Games\\UE_5.8\\Engine\\Binaries\\Win64\\UnrealEditor.exe',
].filter(Boolean);
const unrealEditor = unrealCandidates.find((candidate) => fs.existsSync(candidate));
const projectFile = path.join(root, 'ue5_project', 'Aociety.uproject');
const launcherDirectory = path.join(process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming'), 'echoverse-launcher');
const launcherAiPath = path.join(launcherDirectory, 'ai.json');

function assertFile(filePath, label) {
  if (!filePath || !fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
    throw new Error(`${label}不存在：${filePath || '(未配置)'}`);
  }
}

function writeAtomic(filePath, content, mode = 0o600) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const temporaryPath = `${filePath}.${process.pid}.tmp`;
  fs.writeFileSync(temporaryPath, content, { encoding: 'utf8', mode });
  fs.renameSync(temporaryPath, filePath);
}

assertFile(runtimePython, 'Aociety Python 运行时');
assertFile(unrealEditor, 'UnrealEditor.exe');
assertFile(projectFile, 'Aociety.uproject');
assertFile(launcherAiPath, '启动器 AI 配置');

const ai = JSON.parse(fs.readFileSync(launcherAiPath, 'utf8'));
const apiKey = String(ai.apiKey || ai.key || '').trim();
const baseUrl = String(ai.baseUrl || ai.endpoint || 'https://api.deepseek.com').trim();
const model = String(ai.model || 'deepseek-v4-flash').trim();
if (String(ai.provider || '').toLowerCase() !== 'deepseek' || apiKey.length < 16) {
  throw new Error('启动器中没有可用的 DeepSeek 本地配置。');
}

const envText = [
  `DEEPSEEK_API_KEY=${apiKey}`,
  `DEEPSEEK_BASE_URL=${baseUrl}`,
  `DEEPSEEK_MODEL=${model}`,
  'DEEPSEEK_TIMEOUT_SECONDS=8.0',
  'DEEPSEEK_HARD_TIMEOUT_SECONDS=10.0',
  'DEEPSEEK_FAILURE_COOLDOWN_SECONDS=15',
  'AOCIETY_PORT=8000',
  'HARDWARE_CARE_PORT=8010',
  'R1_OMNI_PORT=8001',
  'AROUSAL_PORT=8002',
  '',
].join('\n');
writeAtomic(path.join(root, '.env'), envText);

const gameConfig = {
  contractVersion: '1.0',
  executablePath: unrealEditor,
  workingDirectory: path.dirname(unrealEditor),
  channel: 'development-editor',
  authExchangeUrl: '',
  additionalArgs: [
    projectFile,
    '-game',
    '-log',
    '-windowed',
    '-ResX=1280',
    '-ResY=720',
  ],
  services: [
    {
      name: 'forest-residents',
      executablePath: runtimePython,
      workingDirectory: root,
      args: [
        '-m', 'uvicorn', 'services.app:app',
        '--host', '127.0.0.1',
        '--port', '8000',
        '--log-level', 'info',
      ],
      healthUrl: 'http://127.0.0.1:8000/health',
      startupTimeoutMs: 30_000,
    },
  ],
};
const configText = `${JSON.stringify(gameConfig, null, 2)}\n`;
writeAtomic(path.join(root, 'config', 'game.local.json'), configText);
writeAtomic(path.join(launcherDirectory, 'game.json'), configText);

console.log(`Local game configuration written for ${path.basename(unrealEditor)}.`);
console.log(`Project: ${projectFile}`);
console.log(`Resident service: ${gameConfig.services[0].healthUrl}`);
