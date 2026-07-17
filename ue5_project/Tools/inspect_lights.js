process.env.UE_MCP_PORT = process.env.UE_MCP_PORT || '8000';

const { initialize, callToolset, firstText } = require('./ue_mcp_client');

const program = String.raw`
import json

def call(name, args):
    return execute_tool(name, json.dumps(args))

def inspect_actor(actor, component_class, property_names):
    label = call("editor_toolset.toolsets.actor.ActorTools.get_label", {"actor": actor}).get("returnValue")
    comps = call("editor_toolset.toolsets.actor.ActorTools.get_components", {
        "actor": actor,
        "component_type": {"refPath": component_class}
    }).get("returnValue") or []
    values = []
    for comp in comps:
        try:
            cls = call("editor_toolset.toolsets.object.ObjectTools.get_class", {"instance": comp}).get("returnValue")
            props = call("editor_toolset.toolsets.object.ObjectTools.get_properties", {
                "instance": comp,
                "properties": property_names
            }).get("returnValue")
            values.append({"component": comp, "class": cls, "props": props})
        except Exception:
            pass
    return {"label": label, "values": values}

def run():
    output = []
    for query, component_class, property_names in [
        ("AOC_HoloKey", "/Script/Engine.PointLightComponent", ["Intensity", "AttenuationRadius", "LightColor", "IntensityUnits", "SourceRadius"]),
        ("AOC_ResonanceGlow", "/Script/Engine.PointLightComponent", ["Intensity", "AttenuationRadius", "LightColor", "IntensityUnits", "SourceRadius"]),
        ("RectLight13", "/Script/Engine.RectLightComponent", ["Intensity", "AttenuationRadius", "LightColor", "IntensityUnits", "SourceWidth", "SourceHeight"])
    ]:
        actors = call("editor_toolset.toolsets.scene.SceneTools.find_actors", {
            "name": query, "tag": "", "collision_channels": []
        }).get("returnValue") or []
        for actor in actors[:3]:
            output.append(inspect_actor(actor, component_class, property_names))
    return {"lights": output}
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
