process.env.UE_MCP_PORT = process.env.UE_MCP_PORT || '8181';

const { initialize, callToolset, firstText } = require('./ue_mcp_client');

const BP = 'editor_toolset.toolsets.blueprint.BlueprintTools';

async function call(tool, args = {}) {
  const result = await callToolset(BP, tool, args);
  const raw = firstText(result);
  if (!raw) return result;
  try { return JSON.parse(raw); } catch (_) { return { text: raw }; }
}

async function main() {
  await initialize();
  const blueprint = await call('create', {
    folder_path: '/Game/Aociety/Blueprints',
    asset_name: 'BP_AocietyGLMBridge',
    asset_type: { refPath: '/Script/Engine.Actor' },
  });
  const bpRef = blueprint.returnValue || {
    refPath: '/Game/Aociety/Blueprints/BP_AocietyGLMBridge.BP_AocietyGLMBridge',
  };
  const graphResult = await call('get_graph', {
    blueprint: bpRef,
    graph_name: 'EventGraph',
  });
  const graph = graphResult.returnValue;
  const filters = [
    'Http',
    'Json',
    'PrintString',
    'SetText',
    'SetTimerbyFunctionName',
  ];
  const found = {};
  for (const filter of filters) {
    found[filter] = await call('find_node_types', {
      graph,
      type_id_filter: filter,
      context_pins: [],
    });
  }
  process.stdout.write(JSON.stringify({ blueprint: bpRef, graph, found }, null, 2));
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});
