process.env.UE_MCP_PORT = process.env.UE_MCP_PORT || '8000';

const { initialize, callToolset, firstText } = require('./ue_mcp_client');

async function call(toolset, tool, args = {}) {
  const result = await callToolset(toolset, tool, args);
  const text = firstText(result);
  if (!text) return result;
  try { return JSON.parse(text); } catch (_) { return { text }; }
}

async function main() {
  await initialize();
  const editor = 'EditorToolset.EditorAppToolset';
  const points = [
    ['far_center', 0.50, 0.46],
    ['mid_center', 0.50, 0.58],
    ['near_center', 0.50, 0.75],
    ['mid_left', 0.36, 0.63],
    ['mid_right', 0.65, 0.63],
    ['right_door', 0.78, 0.62],
  ];
  const output = {};
  for (const [name, x, y] of points) {
    output[name] = await call(editor, 'ScreenCoordsToWorld', {
      coords: { x, y },
      traceDistance: 100000,
    });
  }
  const scene = 'editor_toolset.toolsets.scene.SceneTools';
  const candidates = [
    ['hero', 1450, 1250],
    ['npc_left', 1150, 1550],
    ['npc_right', 1500, 1750],
    ['oasis', 1850, 1450],
    ['holo_pedestal', 850, 1300],
  ];
  output.verticalTraces = {};
  for (const [name, x, y] of candidates) {
    output.verticalTraces[name] = await call(scene, 'trace_world', {
      start: { x, y, z: 10000 },
      end: { x, y, z: -10000 },
    });
  }
  process.stdout.write(JSON.stringify(output, null, 2));
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});
