process.env.UE_MCP_PORT = process.env.UE_MCP_PORT || '8000';

const { initialize, callToolset, firstText } = require('./ue_mcp_client');

async function main() {
  await initialize();
  await callToolset(
    'EditorToolset.EditorAppToolset',
    'SelectActors',
    { actors: [] },
  );
  const result = await callToolset(
    'EditorToolset.EditorAppToolset',
    'SetCameraTransform',
    {
      transform: {
        location: { x: 2736.56, y: 820.42, z: 803.69 },
        rotation: { pitch: -8.0, yaw: 161.5, roll: 0 },
        scale: { x: 1, y: 1, z: 1 },
      },
    },
  );
  process.stdout.write(firstText(result) || JSON.stringify(result, null, 2));
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});
