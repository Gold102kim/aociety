const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8');

const example = JSON.parse(read('config/game.example.json'));
assert.equal(example.contractVersion, '1.0');
assert.ok(Array.isArray(example.additionalArgs) && example.additionalArgs.includes('-game'));
assert.ok(Array.isArray(example.services) && example.services.length > 0);
assert.equal(example.services[0].healthUrl, 'http://127.0.0.1:8000/health');
assert.ok(example.services[0].args.includes('services.app:app'));

const client = read('ue5_project/Source/Aociety/Private/AocietyClientSubsystem.cpp');
for (const endpoint of [
  '/emotion/analyze',
  '/emotion/state',
  '/emotion/care_with_voice',
  '/tts/synthesize',
  '/assessment/start',
]) {
  assert.ok(client.includes(`CareBackendURL + TEXT("${endpoint}`), `${endpoint} must use CareBackendURL`);
}
assert.ok(client.includes('BackendURL + TEXT("/forest/resident_chat")'));
assert.ok(client.includes('BackendURL + TEXT("/world/state")'));

const gameInstance = read('ue5_project/Source/Aociety/Private/AocietyGameInstance.cpp');
for (const argument of ['LauncherSessionFile=', 'LauncherContractVersion=', 'LauncherLaunchId=']) {
  assert.ok(gameInstance.includes(argument), `UE must parse ${argument}`);
}
assert.ok(gameInstance.includes('SessionArgumentMismatch'));
assert.ok(gameInstance.includes('SessionExpired'));

const launcher = read('electron/main.ts');
assert.ok(launcher.includes('startGameServices(config)'));
assert.ok(launcher.includes('game.service_started'));
assert.ok(launcher.indexOf('...(config.additionalArgs ?? [])') < launcher.indexOf('`-LauncherSessionFile=${sessionPath}`'));

const hardwareBackend = read('backend/main.py');
assert.ok(hardwareBackend.includes('os.environ.get("HARDWARE_CARE_PORT", "8010")'));
const emotionPipeline = read('services/emotion_pipeline.py');
assert.ok(emotionPipeline.includes('http://127.0.0.1:8010'));

console.log('Game integration alignment tests passed.');
