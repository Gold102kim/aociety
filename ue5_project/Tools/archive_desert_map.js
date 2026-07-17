process.env.UE_MCP_PORT = process.env.UE_MCP_PORT || '8181';

const { initialize, callToolset, firstText } = require('./ue_mcp_client');

async function main() {
  await initialize();
  const assets = 'editor_toolset.toolsets.asset.AssetTools';
  const source = '/Game/Aociety/Maps/Aociety_Demo';
  const archive = '/Game/Aociety/Maps/Archive/Aociety_Desert_20260714';
  const exists = await callToolset(assets, 'exists', { path: archive });
  const existsText = firstText(exists);
  const parsed = existsText ? JSON.parse(existsText) : {};
  let result = parsed.returnValue
    ? { returnValue: true, alreadyArchived: true }
    : JSON.parse(firstText(await callToolset(assets, 'duplicate', {
        path: source,
        new_path: archive,
      })));
  await callToolset(assets, 'save_assets', { asset_paths: [archive] });
  process.stdout.write(JSON.stringify({ source, archive, result }, null, 2));
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});
