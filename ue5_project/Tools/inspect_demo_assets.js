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
  const assets = 'editor_toolset.toolsets.asset.AssetTools';
  const paths = [
    '/Game/Mannequins/Meshes/SKM_Manny_Simple',
    '/Game/Mannequins/Meshes/SKM_Quinn_Simple',
    '/Game/Mannequins/Anims/Unarmed/MM_Idle',
    '/Game/Ophiopogon_japonicus_Nanite_Free/Geometries/SM_Free_Ophiopogon_japonicus_3DGardenPlants',
    '/Game/Megaplant_Library/Tree_Norway_Spruce/Tree_Norway_Spruce_01/Tree_Norway_Spruce_01_A',
    '/Game/Megaplant_Library/Tree_Norway_Spruce/Tree_Norway_Spruce_01/PVE_Norway_Spruce_01',
    '/Game/Scifi_desert_city/Meshes/Console/SM_console',
    '/Game/Scifi_desert_city/Meshes/Crates/SM_circular_crate',
    '/Game/Scifi_desert_city/Meshes/Lamps/SM_lamp_02',
    '/Game/Scifi_desert_city/Meshes/Round_buildings/SM_small_roof_module_01',
  ];
  const output = {};
  for (const path of paths) {
    output[path] = await call(assets, 'get_asset_class', { asset_path: path });
  }
  process.stdout.write(JSON.stringify(output, null, 2));
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});
