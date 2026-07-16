import unreal


MAP_PATH = "/Game/Aociety/Maps/Aociety_ForestSnowTown"
PREFIX = "Aociety_AI_"
WARM_LIGHT_PREFIX = "Aociety_Generated_WarmLight_"


def load(path):
    asset = unreal.load_asset(path)
    if not asset:
        raise RuntimeError(f"Missing asset: {path}")
    return asset


def spawn_skeletal_actor(
    actor_subsystem, mesh, label, location, yaw, scale, tags, preview_animation=None
):
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.SkeletalMeshActor,
        unreal.Vector(*location),
        unreal.Rotator(pitch=0.0, yaw=yaw, roll=0.0),
    )
    actor.set_actor_label(label)
    actor.set_actor_scale3d(unreal.Vector(scale, scale, scale))
    actor.set_editor_property("tags", [unreal.Name(tag) for tag in tags])
    component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
    component.set_skeletal_mesh(mesh)
    if preview_animation:
        component.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
        component.set_animation(preview_animation)
    component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    return actor


def spawn_label(actor_subsystem, text, label, location, color, world_size=34.0):
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.TextRenderActor,
        unreal.Vector(*location),
        unreal.Rotator(pitch=0.0, yaw=180.0, roll=0.0),
    )
    actor.set_actor_label(label)
    component = actor.get_component_by_class(unreal.TextRenderComponent)
    component.set_editor_property("text", text)
    component.set_editor_property("horizontal_alignment", unreal.HorizTextAligment.EHTA_CENTER)
    component.set_editor_property("world_size", world_size)
    component.set_editor_property("text_render_color", unreal.Color(*color))
    component.set_editor_property("cast_shadow", False)
    return actor


def spawn_dialogue_trigger(actor_subsystem, npc_id, location):
    trigger = actor_subsystem.spawn_actor_from_class(
        unreal.TriggerBox,
        unreal.Vector(*location),
        unreal.Rotator(),
    )
    trigger.set_actor_label(f"{PREFIX}DialogueTrigger_{npc_id}")
    trigger.set_editor_property(
        "tags",
        [unreal.Name("AocietyDialogueTrigger"), unreal.Name(npc_id)],
    )
    component = trigger.get_component_by_class(unreal.BoxComponent)
    component.set_box_extent(unreal.Vector(230.0, 230.0, 150.0), True)
    component.set_collision_enabled(unreal.CollisionEnabled.QUERY_ONLY)
    component.set_editor_property("generate_overlap_events", True)
    return trigger


def spawn_ai_npc(
    actor_subsystem, npc_class, mesh, idle_animation, walk_animation,
    npc_id, display_name, location, yaw
):
    actor = actor_subsystem.spawn_actor_from_class(
        npc_class,
        unreal.Vector(*location),
        unreal.Rotator(pitch=0.0, yaw=yaw, roll=0.0),
    )
    actor.set_actor_label(f"{PREFIX}NPC_{npc_id}_{display_name}")
    actor.set_editor_property(
        "tags",
        [unreal.Name("AocietyResident"), unreal.Name(npc_id), unreal.Name("GLM_5_2")],
    )
    actor.set_editor_property("npc_id", npc_id)
    actor.set_editor_property("display_name", display_name)
    actor.set_editor_property("wander_radius", 160.0)
    actor.set_editor_property("wander_speed", 105.0)
    actor.set_editor_property("enable_wander", True)
    actor.set_editor_property("idle_animation", idle_animation)
    actor.set_editor_property("walk_animation", walk_animation)
    component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
    component.set_skinned_asset_and_update(mesh)
    component.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
    component.set_animation(idle_animation)
    component.set_editor_property("relative_location", unreal.Vector(0.0, 0.0, -88.0))
    component.set_editor_property(
        "relative_rotation", unreal.Rotator(pitch=0.0, yaw=-90.0, roll=0.0)
    )
    return actor


level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not level_subsystem.load_level(MAP_PATH):
    raise RuntimeError(f"Could not load {MAP_PATH}")

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = actor_subsystem.get_all_level_actors()

# Replace this setup deterministically and remove the six oversized cabin lights.
replace = [
    actor
    for actor in actors
    if actor.get_actor_label().startswith(PREFIX)
    or actor.get_actor_label().startswith("Aociety_TownRefine_Resident_")
]
removed_lights = [
    actor for actor in actors
    if actor.get_actor_label().startswith(WARM_LIGHT_PREFIX)
]
if replace:
    actor_subsystem.destroy_actors(replace)
if removed_lights:
    actor_subsystem.destroy_actors(removed_lights)

ecy_mesh = load("/Game/Aociety/Characters/Ecy/SK_Ecy")
ecy_idle = load("/Game/Aociety/Characters/Ecy/Animations/A_Ecy_Idle")
npc_a_mesh = load("/Game/Aociety/Characters/NPC_Cute/AliciaSolid/SK_AliciaSolid")
npc_c_mesh = load("/Game/Aociety/Characters/NPC_Cute/AliciaSakura/SK_AliciaSakura")
npc_a_idle = load("/Game/Aociety/Characters/NPC_Cute/AliciaSolid/Animations/A_AliciaSolid_Idle")
npc_a_walk = load("/Game/Aociety/Characters/NPC_Cute/AliciaSolid/Animations/A_AliciaSolid_Walk")
npc_c_idle = load("/Game/Aociety/Characters/NPC_Cute/AliciaSakura/Animations/A_AliciaSakura_Idle")
npc_c_walk = load("/Game/Aociety/Characters/NPC_Cute/AliciaSakura/Animations/A_AliciaSakura_Walk")
npc_class = unreal.load_class(None, "/Script/Aociety.AocietyNPCCharacter")
if not npc_class:
    raise RuntimeError("AocietyNPCCharacter native class is not loaded")

player_start = actor_subsystem.spawn_actor_from_class(
    unreal.PlayerStart,
    unreal.Vector(-650.0, 1250.0, 228.0),
    unreal.Rotator(pitch=0.0, yaw=90.0, roll=0.0),
)
player_start.set_actor_label(f"{PREFIX}PlayerStart")

npc_specs = (
    ("npc_01", "林汐", npc_a_mesh, npc_a_idle, npc_a_walk, (-260.0, 790.0, 228.0), 215.0),
    ("npc_02", "小樱", npc_c_mesh, npc_c_idle, npc_c_walk, (-1030.0, 900.0, 228.0), 325.0),
)

for npc_id, display_name, mesh, idle, walk, location, yaw in npc_specs:
    spawn_ai_npc(
        actor_subsystem, npc_class, mesh, idle, walk,
        npc_id, display_name, location, yaw
    )
    spawn_dialogue_trigger(
        actor_subsystem,
        npc_id,
        location,
    )

spawn_label(
    actor_subsystem,
    "AOCIETY AI 森林小镇\n居民由 GLM 5.2 驱动",
    f"{PREFIX}Village_AI_Sign",
    (-650.0, 600.0, 360.0),
    (255, 220, 120, 255),
    42.0,
)

level_subsystem.save_current_level()
unreal.EditorAssetLibrary.save_directory(
    "/Game/Aociety", only_if_is_dirty=False, recursive=True
)
print(
    "[AocietyAISetup] player=Ecy npcs=2 triggers=2 removed_warm_lights=%d"
    % len(removed_lights)
)
