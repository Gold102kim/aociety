process.env.UE_MCP_PORT = process.env.UE_MCP_PORT || '8000';

const { initialize, callToolset, firstText } = require('./ue_mcp_client');

const program = String.raw`
import json

SCENE = "editor_toolset.toolsets.scene.SceneTools"
ACTOR = "editor_toolset.toolsets.actor.ActorTools"
OBJECT = "editor_toolset.toolsets.object.ObjectTools"
ASSET = "editor_toolset.toolsets.asset.AssetTools"

def call(name, args):
    return execute_tool(name, json.dumps(args))

def record_error(errors, label, exc):
    errors.append(label + ": " + str(exc)[:240])

def decorate(actor, folder, errors):
    try:
        call(ACTOR + ".add_tag", {"actor": actor, "tag": "AocietyDemo"})
        call(SCENE + ".set_actor_folder", {"actor": actor, "folder_path": folder})
    except Exception as exc:
        record_error(errors, "decorate", exc)

def add_asset(path, name, loc, rot, scale, folder, errors, snap=False):
    result = call(SCENE + ".add_to_scene_from_asset", {
        "asset_path": path,
        "name": name,
        "xform": {
            "location": {"x": loc[0], "y": loc[1], "z": loc[2]},
            "rotation": {"pitch": rot[0], "yaw": rot[1], "roll": rot[2]},
            "scale": {"x": scale[0], "y": scale[1], "z": scale[2]}
        },
        "snap_to_ground": snap
    })
    actor = result.get("returnValue")
    if actor:
        decorate(actor, folder, errors)
    return actor

def add_class(path, name, loc, rot, scale, folder, errors, snap=False):
    result = call(SCENE + ".add_to_scene_from_class", {
        "actor_type": {"refPath": path},
        "name": name,
        "xform": {
            "location": {"x": loc[0], "y": loc[1], "z": loc[2]},
            "rotation": {"pitch": rot[0], "yaw": rot[1], "roll": rot[2]},
            "scale": {"x": scale[0], "y": scale[1], "z": scale[2]}
        },
        "snap_to_ground": snap
    })
    actor = result.get("returnValue")
    if actor:
        decorate(actor, folder, errors)
    return actor

def components(actor, class_path):
    result = call(ACTOR + ".get_components", {
        "actor": actor,
        "component_type": {"refPath": class_path}
    })
    return result.get("returnValue") or []

def set_props(instance, values):
    return call(OBJECT + ".set_properties", {
        "instance": instance,
        "values": json.dumps(values)
    })

def configure_idle(actor, errors):
    try:
        comps = components(actor, "/Script/Engine.SkeletalMeshComponent")
        if comps:
            set_props(comps[0], {
                "AnimationMode": "AnimationSingleNode",
                "AnimationData": {
                    "AnimToPlay": {"refPath": "/Game/Mannequins/Anims/Unarmed/MM_Idle.MM_Idle"},
                    "bSavedLooping": True,
                    "bSavedPlaying": True,
                    "SavedPosition": 0.0,
                    "SavedPlayRate": 1.0
                }
            })
    except Exception as exc:
        record_error(errors, "idle", exc)

def add_text(name, text, loc, color, size, errors):
    actor = add_class(
        "/Script/Engine.TextRenderActor", name, loc, (0, -18, 0), (1, 1, 1),
        "Aociety/Experience/UI", errors, False
    )
    if not actor:
        return None
    try:
        comps = components(actor, "/Script/Engine.TextRenderComponent")
        if comps:
            set_props(comps[0], {
                "Text": text,
                "WorldSize": size,
                "HorizontalAlignment": "EHTA_Center",
                "VerticalAlignment": "EVRTA_TextCenter",
                "TextRenderColor": {"r": color[0], "g": color[1], "b": color[2], "a": 1}
            })
    except Exception as exc:
        record_error(errors, "text " + name, exc)
    return actor

def add_point_light(name, loc, color, intensity, radius, errors):
    actor = add_class(
        "/Script/Engine.PointLight", name, loc, (0, 0, 0), (1, 1, 1),
        "Aociety/Lighting", errors, False
    )
    if not actor:
        return None
    try:
        comps = components(actor, "/Script/Engine.PointLightComponent")
        if comps:
            set_props(comps[0], {
                "Intensity": intensity,
                "AttenuationRadius": radius,
                "SourceRadius": 18.0,
                "LightColor": {"r": color[0], "g": color[1], "b": color[2], "a": 255}
            })
    except Exception as exc:
        record_error(errors, "light " + name, exc)
    return actor

def run():
    errors = []
    created = []

    try:
        existing = call(SCENE + ".find_actors", {
            "name": "",
            "tag": "AocietyDemo",
            "collision_channels": []
        }).get("returnValue") or []
        for actor in existing:
            try:
                call(SCENE + ".remove_from_scene", {"actor": actor})
            except Exception as exc:
                record_error(errors, "cleanup", exc)
    except Exception as exc:
        record_error(errors, "find existing", exc)

    pedestal = add_asset(
        "/Game/Scifi_desert_city/Meshes/Crates/SM_circular_crate",
        "AOC_EmotionOasis_Pedestal", (1450, 1250, 100), (0, 0, 0), (1.8, 1.8, 0.65),
        "Aociety/Experience/EmotionOasis", errors, True
    )
    if pedestal: created.append(pedestal)

    hero = add_asset(
        "/Game/Mannequins/Meshes/SKM_Quinn_Simple",
        "AOC_DigitalTwin_Astra", (1450, 1250, 205), (0, 138, 0), (1.05, 1.05, 1.05),
        "Aociety/Characters/DigitalTwin", errors, False
    )
    if hero:
        created.append(hero)

    npc_a = add_asset(
        "/Game/Mannequins/Meshes/SKM_Manny_Simple",
        "AOC_Agent_Rin", (1125, 1540, 100), (0, -42, 0), (1.0, 1.0, 1.0),
        "Aociety/Characters/AutonomousAgents", errors, False
    )
    if npc_a:
        created.append(npc_a)

    npc_b = add_asset(
        "/Game/Mannequins/Meshes/SKM_Quinn_Simple",
        "AOC_Agent_Mira", (1510, 1745, 102), (0, -118, 0), (0.98, 0.98, 0.98),
        "Aociety/Characters/AutonomousAgents", errors, False
    )
    if npc_b:
        created.append(npc_b)

    if hero and npc_a:
        try: call(ACTOR + ".look_at", {"actor": npc_a, "target": {"x": 1450, "y": 1250, "z": 250}})
        except Exception as exc: record_error(errors, "look_at Rin", exc)
    if hero and npc_b:
        try: call(ACTOR + ".look_at", {"actor": npc_b, "target": {"x": 1450, "y": 1250, "z": 250}})
        except Exception as exc: record_error(errors, "look_at Mira", exc)

    console = add_asset(
        "/Game/Scifi_desert_city/Meshes/Console/SM_console",
        "AOC_MemoryBridgeConsole", (1280, 1150, 101), (0, 38, 0), (1.35, 1.35, 1.35),
        "Aociety/Experience/GameMemoryBridge", errors, True
    )
    if console: created.append(console)

    lamp_positions = [
        (1320, 1320, 102, 15),
        (1575, 1320, 103, 165),
        (1430, 1510, 101, -90)
    ]
    for index, item in enumerate(lamp_positions):
        actor = add_asset(
            "/Game/Scifi_desert_city/Meshes/Lamps/SM_lamp_02",
            "AOC_ResonanceBeacon_" + str(index + 1),
            (item[0], item[1], item[2]), (0, item[3], 0), (0.9, 0.9, 0.9),
            "Aociety/Experience/ResonanceBeacons", errors, True
        )
        if actor: created.append(actor)

    grass_path = "/Game/Ophiopogon_japonicus_Nanite_Free/Geometries/SM_Free_Ophiopogon_japonicus_3DGardenPlants"
    grass_positions = [
        (1680, 1370, 112, 0, 0.30),
        (1785, 1425, 114, 35, 0.34),
        (1885, 1495, 116, 75, 0.31),
        (1720, 1540, 108, 115, 0.28),
        (1860, 1630, 110, 155, 0.33),
        (1990, 1510, 118, 210, 0.27),
        (1650, 1660, 104, 260, 0.29),
        (1980, 1710, 112, 310, 0.32)
    ]
    for index, item in enumerate(grass_positions):
        actor = add_asset(
            grass_path, "AOC_NaniteOasisGrass_" + str(index + 1),
            (item[0], item[1], item[2]), (0, item[3], 0), (item[4], item[4], item[4]),
            "Aociety/Environment/NaniteOasis", errors, True
        )
        if actor: created.append(actor)

    tree = add_asset(
        "/Game/Megaplant_Library/Tree_Norway_Spruce/Tree_Norway_Spruce_01/Tree_Norway_Spruce_01_A",
        "AOC_MemoryTree", (2010, 1825, 115), (0, -30, 0), (0.32, 0.32, 0.32),
        "Aociety/Environment/MemoryTree", errors, True
    )
    if tree: created.append(tree)

    add_text("AOC_Title", "AOCIETY // DIGITAL TWIN", (1450, 1250, 445), (0.08, 0.8, 1.0), 34, errors)
    add_text("AOC_State", "GLM-5.2 WORLD BRAIN ONLINE", (1450, 1250, 397), (1.0, 0.55, 0.08), 22, errors)
    add_text("AOC_Resonance", "AGENT RESONANCE 87%", (1315, 1480, 335), (0.15, 1.0, 0.62), 24, errors)
    add_text("AOC_MemorySync", "GAME MEMORY EXPORTED", (1775, 1390, 330), (0.08, 0.65, 1.0), 23, errors)
    add_text("AOC_Oasis", "SHARED MEMORY OASIS", (1850, 1570, 285), (0.25, 1.0, 0.45), 23, errors)

    for name, loc, color, intensity, radius in [
        ("AOC_HoloKey", (1450, 1250, 275), (0.05, 0.55, 1.0), 18, 520),
        ("AOC_ResonanceGlow", (1325, 1490, 245), (0.08, 1.0, 0.55), 10, 430),
        ("AOC_MemoryBridgeGlow", (1780, 1430, 230), (0.05, 0.45, 1.0), 12, 460),
        ("AOC_WarmAnchor", (1280, 1130, 230), (1.0, 0.25, 0.04), 8, 390)
    ]:
        light = add_point_light(name, loc, color, intensity, radius, errors)
        if light: created.append(light)

    camera_a = add_class(
        "/Script/CinematicCamera.CineCameraActor", "AOC_Cine_AutonomyObserver",
        (2736, 820, 804), (12, 162.4, 0), (1, 1, 1),
        "Aociety/Cameras", errors, False
    )
    if camera_a: created.append(camera_a)
    camera_b = add_class(
        "/Script/CinematicCamera.CineCameraActor", "AOC_Cine_MemoryBridgeCloseup",
        (2180, 980, 420), (5, 150, 0), (1, 1, 1),
        "Aociety/Cameras", errors, False
    )
    if camera_b: created.append(camera_b)

    player_start = add_class(
        "/Script/Engine.PlayerStart", "AOC_PlayerTakeoverStart",
        (1580, 1050, 105), (0, 145, 0), (1, 1, 1),
        "Aociety/Gameplay", errors, True
    )
    if player_start: created.append(player_start)

    saved = call(ASSET + ".save_assets", {
        "asset_paths": ["/Game/Aociety/Maps/Aociety_Demo"]
    })

    return {
        "created": len(created),
        "errors": errors,
        "saved": saved,
        "hero": hero,
        "npcA": npc_a,
        "npcB": npc_b
    }
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
