process.env.UE_MCP_PORT = process.env.UE_MCP_PORT || '8000';

const { initialize, callToolset, firstText } = require('./ue_mcp_client');

const program = String.raw`
import json

def call(name, args):
    return execute_tool(name, json.dumps(args))

def run():
    actors = call(
        "editor_toolset.toolsets.scene.SceneTools.find_actors",
        {"name": "", "tag": "AocietyDemo", "collision_channels": []}
    ).get("returnValue") or []
    output = []
    for actor in actors:
        label = call("editor_toolset.toolsets.actor.ActorTools.get_label", {"actor": actor}).get("returnValue")
        xform = call("editor_toolset.toolsets.actor.ActorTools.get_actor_transform", {"actor": actor}).get("returnValue")
        screen = None
        if xform:
            try:
                screen = call("EditorToolset.EditorAppToolset.WorldPosToScreenCoords", {
                    "position": xform.get("location")
                }).get("returnValue")
            except Exception:
                screen = None
        output.append({"label": label, "actor": actor, "xform": xform, "screen": screen})
    return {"actors": output}
`;

async function main() {
  await initialize();
  const result = await callToolset(
    'editor_toolset.toolsets.programmatic.ProgrammaticToolset',
    'execute_tool_script',
    { script: program },
  );
  process.stdout.write(firstText(result) || JSON.stringify(result, null, 2));
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});
