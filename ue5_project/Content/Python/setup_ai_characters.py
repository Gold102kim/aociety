import unreal


MAP_PATH = "/Game/Aociety/Maps/Aociety_ForestSnowTown"
PREFIX = "Aociety_AI_"
WARM_LIGHT_PREFIX = "Aociety_Generated_WarmLight_"
PLAYER_START_LOCATION = (-650.0, 1130.0, 228.0)
PLAYER_START_YAW = -90.0
RESIDENT_TAG = "AocietyResident"
DIALOGUE_TRIGGER_TAG = "AocietyDialogueTrigger"
MODEL_TAG = "DEEPSEEK_V4_FLASH"
EXPECTED_NPC_IDS = {"npc_01", "npc_02"}


def load(path):
    asset = unreal.load_asset(path)
    if not asset:
        raise RuntimeError(f"Missing asset: {path}")
    return asset


def actor_tags(actor):
    return {str(tag) for tag in actor.get_editor_property("tags")}


def is_aociety_npc(actor):
    class_name = actor.get_class().get_name()
    tags = actor_tags(actor)
    return (
        class_name == "AocietyNPCCharacter"
        or actor.get_actor_label().startswith(f"{PREFIX}NPC_")
        or actor.get_actor_label().startswith("Aociety_TownRefine_Resident_")
        or RESIDENT_TAG in tags
    )


def is_dialogue_trigger(actor):
    return (
        actor.get_actor_label().startswith(f"{PREFIX}DialogueTrigger_")
        or DIALOGUE_TRIGGER_TAG in actor_tags(actor)
    )


def is_unit_scale(vector, tolerance=0.001):
    return (
        abs(vector.x - 1.0) <= tolerance
        and abs(vector.y - 1.0) <= tolerance
        and abs(vector.z - 1.0) <= tolerance
    )


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


def spawn_dialogue_trigger(actor_subsystem, npc_id, location):
    trigger = actor_subsystem.spawn_actor_from_class(
        unreal.TriggerBox,
        unreal.Vector(*location),
        unreal.Rotator(),
    )
    trigger.set_actor_label(f"{PREFIX}DialogueTrigger_{npc_id}")
    trigger.set_actor_scale3d(unreal.Vector(1.0, 1.0, 1.0))
    trigger.set_editor_property(
        "tags",
        [unreal.Name(DIALOGUE_TRIGGER_TAG), unreal.Name(npc_id)],
    )
    component = trigger.get_component_by_class(unreal.BoxComponent)
    component.set_box_extent(unreal.Vector(100.0, 100.0, 150.0), True)
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
    actor.set_actor_scale3d(unreal.Vector(1.0, 1.0, 1.0))
    actor.set_editor_property(
        "tags",
        [unreal.Name(RESIDENT_TAG), unreal.Name(npc_id), unreal.Name(MODEL_TAG)],
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
    component.set_editor_property("relative_location", unreal.Vector(0.0, 0.0, -46.0))
    component.set_editor_property("relative_scale3d", unreal.Vector(1.0, 1.0, 1.0))
    component.set_editor_property(
        "relative_rotation", unreal.Rotator(pitch=0.0, yaw=-90.0, roll=0.0)
    )
    return actor


level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not level_subsystem.load_level(MAP_PATH):
    raise RuntimeError(f"Could not load {MAP_PATH}")

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = actor_subsystem.get_all_level_actors()

# Replace only Aociety's resident setup deterministically. Character and Motion
# Matching assets are referenced but never edited or resaved by this script.
replace = [
    actor
    for actor in actors
    if isinstance(actor, unreal.PlayerStart)
    or actor.get_actor_label().startswith(f"{PREFIX}Village_AI_Sign")
    or is_aociety_npc(actor)
    or is_dialogue_trigger(actor)
]
removed_lights = [
    actor for actor in actors
    if actor.get_actor_label().startswith(WARM_LIGHT_PREFIX)
]
if replace:
    actor_subsystem.destroy_actors(replace)
if removed_lights:
    actor_subsystem.destroy_actors(removed_lights)

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
    unreal.Vector(*PLAYER_START_LOCATION),
    unreal.Rotator(pitch=0.0, yaw=PLAYER_START_YAW, roll=0.0),
)
player_start.set_actor_label(f"{PREFIX}PlayerStart")
player_start.set_actor_scale3d(unreal.Vector(1.0, 1.0, 1.0))

npc_specs = (
    ("npc_01", "林汐", npc_a_mesh, npc_a_idle, npc_a_walk, (-450.0, 980.0, 228.0), 215.0),
    ("npc_02", "小樱", npc_c_mesh, npc_c_idle, npc_c_walk, (-850.0, 980.0, 228.0), 325.0),
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

final_actors = actor_subsystem.get_all_level_actors()
final_npcs = [
    actor
    for actor in final_actors
    if RESIDENT_TAG in actor_tags(actor)
]
final_triggers = [
    actor
    for actor in final_actors
    if DIALOGUE_TRIGGER_TAG in actor_tags(actor)
]
final_player_starts = [
    actor for actor in final_actors if isinstance(actor, unreal.PlayerStart)
]
errors = []
if len(final_npcs) != 2:
    errors.append(f"expected 2 NPCs, got {len(final_npcs)}")
if len(final_triggers) != 2:
    errors.append(f"expected 2 dialogue triggers, got {len(final_triggers)}")
if len(final_player_starts) != 1:
    errors.append(f"expected 1 PlayerStart, got {len(final_player_starts)}")
for actor in final_player_starts:
    yaw = actor.get_actor_rotation().yaw
    if abs(yaw - PLAYER_START_YAW) > 0.1:
        errors.append(
            f"PlayerStart yaw is {yaw:.1f}, expected {PLAYER_START_YAW:.1f}"
        )

final_npc_ids = {
    actor.get_editor_property("npc_id")
    for actor in final_npcs
}
if final_npc_ids != EXPECTED_NPC_IDS:
    errors.append(f"unexpected NPC IDs: {sorted(final_npc_ids)}")

final_trigger_ids = {
    tag
    for actor in final_triggers
    for tag in actor_tags(actor)
    if tag in EXPECTED_NPC_IDS
}
if final_trigger_ids != EXPECTED_NPC_IDS:
    errors.append(f"unexpected dialogue trigger IDs: {sorted(final_trigger_ids)}")

for actor in final_npcs:
    component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
    if not is_unit_scale(actor.get_actor_scale3d()):
        errors.append(
            f"{actor.get_actor_label()} actor scale is {actor.get_actor_scale3d()}"
        )
    if not component:
        errors.append(f"{actor.get_actor_label()} has no skeletal mesh component")
        continue
    component_scale = component.get_editor_property("relative_scale3d")
    if not is_unit_scale(component_scale):
        errors.append(
            f"{actor.get_actor_label()} mesh scale is {component_scale}"
        )
    if not actor.get_editor_property("idle_animation"):
        errors.append(f"{actor.get_actor_label()} has no idle animation")
    if not actor.get_editor_property("walk_animation"):
        errors.append(f"{actor.get_actor_label()} has no walk animation")

if errors:
    raise RuntimeError("Aociety AI setup validation failed: " + "; ".join(errors))

level_subsystem.save_current_level()
print(
    "[AocietyAISetup] player=Ecy npcs=2 triggers=2 player_starts=1 "
    "provider=deepseek model=deepseek-v4-flash "
    "removed_legacy_ai=%d removed_warm_lights=%d"
    % (len(replace), len(removed_lights))
)
