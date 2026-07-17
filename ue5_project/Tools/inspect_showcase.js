process.env.UE_MCP_PORT = process.env.UE_MCP_PORT || '8000';

const fs = require('fs');
const { initialize, callToolset, firstText } = require('./ue_mcp_client');

function parseToolResult(result) {
  const text = firstText(result);
  if (!text) return result;
  try {
    return JSON.parse(text);
  } catch (_) {
    return { text };
  }
}

async function call(toolset, tool, args = {}) {
  return parseToolResult(await callToolset(toolset, tool, args));
}

async function main() {
  await initialize();

  const assets = 'editor_toolset.toolsets.asset.AssetTools';
  const scene = 'editor_toolset.toolsets.scene.SceneTools';
  const editor = 'EditorToolset.EditorAppToolset';
  const sourceMap = '/Game/Scifi_desert_city/Level/L_showcase_level';
  const targetMap = '/Game/Aociety/Maps/Aociety_Demo';

  const sourceExists = await call(assets, 'exists', { path: sourceMap });
  if (!sourceExists.returnValue) throw new Error(`Missing source map: ${sourceMap}`);

  const targetExists = await call(assets, 'exists', { path: targetMap });
  if (!targetExists.returnValue) {
    const duplicated = await call(assets, 'duplicate', { path: sourceMap, new_path: targetMap });
    if (!duplicated.returnValue) throw new Error(`Failed to duplicate ${sourceMap}`);
  }
  const savedTarget = await call(assets, 'save_assets', { asset_paths: [targetMap] });
  if (savedTarget.returnValue === false) throw new Error(`Failed to save ${targetMap}`);

  const loadResult = await call(scene, 'load_level', { level_path: targetMap });
  if (loadResult.text) throw new Error(loadResult.text);
  const current = await call(scene, 'get_current_level', {});

  const captureResult = await call(editor, 'CaptureViewport', { bShowUI: false });
  const capture = captureResult.returnValue;
  const outputPath = 'E:/Aociety-NEW/ue5_project/Saved/AocietyCaptures/showcase-baseline.png';
  fs.writeFileSync(outputPath, Buffer.from(capture.image.data, 'base64'));

  process.stdout.write(JSON.stringify({
    currentLevel: current.returnValue,
    outputPath,
    cameraLocation: capture.cameraLocation,
    cameraRotation: capture.cameraRotation,
    cameraFOV: capture.cameraFOV,
  }, null, 2));
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});
