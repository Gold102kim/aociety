process.env.UE_MCP_PORT = process.env.UE_MCP_PORT || '8000';

const { initialize, callToolset, firstText } = require('./ue_mcp_client');

async function main() {
  await initialize();
  const script = `
import json

def run():
    value = execute_tool(
        "editor_toolset.toolsets.scene.SceneTools.get_current_level",
        json.dumps({})
    )
    return {"value": value, "type": str(type(value))}
`.trim();
  const result = await callToolset(
    'editor_toolset.toolsets.programmatic.ProgrammaticToolset',
    'execute_tool_script',
    { script },
  );
  process.stdout.write(firstText(result) || JSON.stringify(result, null, 2));
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});
