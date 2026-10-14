const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8');

const example = JSON.parse(read('config/game.example.json'));
assert.equal(example.contractVersion, '1.0');
assert.ok(Array.isArray(example.additionalArgs) && example.additionalArgs.includes('-game'));
assert.ok(example.additionalArgs.includes('/Engine/Maps/Entry'));
assert.ok(example.additionalArgs.includes('-DisablePython'));
assert.ok(example.additionalArgs.includes('-DisablePlugins=AIAssistant,MCPClientToolset,ModelContextProtocol'));
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
assert.equal((client.match(/->ProcessRequest\(\)/g) || []).length, 1, 'All HTTP requests must go through the lifecycle helper.');
assert.ok(client.includes('if (!Request->ProcessRequest())'), 'Rejected HTTP requests must complete with failure.');
assert.ok(client.includes('Request->SetTimeout('), 'HTTP requests require a bounded timeout.');
assert.ok(client.includes('EHttpRequestDelegateThreadPolicy::CompleteOnGameThread'));
assert.ok(client.includes('Self->ActiveRequests.Remove(Completed) == 0'), 'Transport completion must be idempotent.');
assert.ok(client.indexOf('Request->OnProcessRequestComplete().Unbind();') < client.indexOf('Request->CancelRequest();'));
assert.ok(client.includes('Self->bShuttingDown'), 'Shutdown must not deliver stale replies.');
assert.ok(!client.includes('FString::Printf(TEXT("{'), 'JSON payloads must not be hand-assembled.');
assert.ok(client.includes('Body->SetStringField(TEXT("player_input"), PlayerInput)'));
assert.ok(client.includes('PayloadJson->SetStringField(Pair.Key, Pair.Value)'));
assert.ok(client.includes('response_routing_mismatch'));
assert.ok(client.includes('invalid_response_metadata'));
assert.ok(client.includes('AocietyDialogueValidation::TryReadMetadata(Json, Metadata, Payload)'));
assert.ok(client.includes('AocietyDialogueValidation::IsVerifiedLLM(Metadata)'));
const dialogueMetadata = read('ue5_project/Source/Aociety/Private/AocietyDialogueValidation.h');
for (const field of ['npc_id', 'source', 'model', 'provider', 'mode', 'counterpart_id']) {
  assert.ok(dialogueMetadata.includes(`TryGetStringField(TEXT("${field}"`), `${field} must be explicit string metadata.`);
}
const dialogueCallback = client.slice(client.indexOf('void UAocietyClientSubsystem::OnDialogueHttpDone('), client.indexOf('void UAocietyClientSubsystem::OnHttpDone('));
assert.ok(!dialogueCallback.includes('Dialogue.Model = TEXT("deepseek-v4-flash")'));
assert.ok(!dialogueCallback.includes('Dialogue.Provider = TEXT("deepseek")'));
assert.ok(!dialogueCallback.includes('ApplyFields(Json)'), 'Missing nested metadata must not be merged from top-level values.');
assert.ok(client.includes('AocietyConversationScope::GetNamespace(AccountId, AgentId)'));
assert.ok(client.includes('TEXT("Conversations"), ConversationNamespace, TEXT("ConversationHistory.json")'));
assert.ok(!client.includes('const FString Path = FPaths::Combine(\n        FPaths::ProjectSavedDir(), TEXT("Aociety"),\n        TEXT("ConversationHistory.json")'));
const conversationScope = read('ue5_project/Source/Aociety/Private/AocietyConversationScope.h');
assert.match(conversationScope, /#if UE_BUILD_SHIPPING\s+return \{\};\s+#else\s+return TEXT\("development-local"\);/);
assert.ok(conversationScope.includes('FTCHARToUTF8 Bytes'), 'Unicode identifiers must not collapse through an ANSI conversion.');

const gameInstance = read('ue5_project/Source/Aociety/Private/AocietyGameInstance.cpp');
for (const argument of ['LauncherSessionFile=', 'LauncherContractVersion=', 'LauncherLaunchId=']) {
  assert.ok(gameInstance.includes(argument), `UE must parse ${argument}`);
}
assert.ok(gameInstance.includes('SessionArgumentMismatch'));
assert.ok(gameInstance.includes('SessionExpired'));
assert.ok(gameInstance.includes('Client->ConfigureConversationScope('));
assert.match(gameInstance, /#if UE_BUILD_SHIPPING\s+LauncherSessionError = TEXT\("ServerTicketExchangeUnavailable"\);\s+return false;/,
  'Shipping must reject all local tickets until a trusted exchange exists.');

const engineConfig = read('ue5_project/Config/DefaultEngine.ini');
assert.ok(engineConfig.includes('bRemoteExecution=False'));
assert.ok(engineConfig.includes('bAllowNetworkConnection=False'));
assert.match(engineConfig, /^SecurityToken=\s*$/m, 'A static device token must not be committed.');
const editorDefaults = read('ue5_project/Config/DefaultEditorPerProjectUserSettings.ini');
assert.ok(editorDefaults.includes('bAutoStartServer=False'), 'Remote editor tooling must require explicit developer opt-in.');
const micCapture = read('ue5_project/Source/Aociety/Private/MicCaptureComponent.cpp');
assert.ok(!micCapture.includes('SetNumZeroed'), 'Unimplemented microphone capture must not emit fake silent recordings.');
assert.ok(micCapture.includes('capture unavailable'));

const player = read('ue5_project/Source/Aociety/Private/AocietyPlayerCharacter.cpp');
assert.ok(player.includes('bRuntimeAuditEnabled && MotionEvidenceAccumulator >= 1.0f'), 'Animation diagnostics must not synchronously query proxies during normal play.');

const mainMenuMode = read('ue5_project/Source/Aociety/Private/AocietyMainMenuGameMode.cpp');
assert.ok(mainMenuMode.includes('[AocietyMainMenu] ready'));
assert.ok(mainMenuMode.includes('/Game/Aociety/Maps/Aociety_ForestSnowTown'));
assert.ok(mainMenuMode.includes('game=/Script/Aociety.AocietyGameMode'));

const gameMode = read('ue5_project/Source/Aociety/Private/AocietyGameMode.cpp');
assert.ok(gameMode.includes('[AocietyEnvironment] initialized'));
assert.ok(gameMode.includes('[AocietyScene] ready'));
assert.ok(gameMode.includes('[AocietyExpansion] player relocated to city approach'));
assert.ok(gameMode.includes('AAocietyWorldBoundary'));
assert.ok(!/UE_LOG\([\s\S]*?TEXT\("\[Aociety\]\[NPC\][^;]+\*Dialogue\.Message/.test(gameMode),
  'Residents chat text must not be written to diagnostic logs.');

const launcher = read('electron/main.ts');
assert.ok(launcher.includes('startGameServices(config)'));
assert.ok(launcher.includes('game.service_started'));
assert.ok(launcher.indexOf('...(config.additionalArgs ?? [])') < launcher.indexOf('`-LauncherSessionFile=${sessionPath}`'));

const hardwareBackend = read('backend/main.py');
assert.ok(hardwareBackend.includes('os.environ.get("HARDWARE_CARE_PORT", "8010")'));
const emotionPipeline = read('services/emotion_pipeline.py');
assert.ok(emotionPipeline.includes('http://127.0.0.1:8010'));

console.log('Game integration alignment tests passed.');
