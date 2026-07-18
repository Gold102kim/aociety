import unreal


MAP_PATH = "/Game/Aociety/Maps/Aociety_ForestSnowTown"
EXPECTED_PLAYER_START_YAW = -90.0
RESIDENT_TAG = "AocietyResident"
DIALOGUE_TRIGGER_TAG = "AocietyDialogueTrigger"
MODEL_TAG = "DEEPSEEK_V4_FLASH"
EXPECTED_NPCS = {
    "npc_01": {
        "mesh": "/Game/Aociety/Characters/Ecy/SK_Ecy.SK_Ecy",
        "idle": "/Game/Aociety/Characters/Ecy/Animations/A_Ecy_Idle.A_Ecy_Idle",
        "walk": "/Game/Aociety/Characters/Ecy/Animations/A_Ecy_Walk.A_Ecy_Walk",
    },
    "npc_02": {
        "mesh": "/Game/Aociety/Characters/Ecy/SK_Ecy.SK_Ecy",
        "idle": "/Game/Aociety/Characters/Ecy/Animations/A_Ecy_Idle.A_Ecy_Idle",
        "walk": "/Game/Aociety/Characters/Ecy/Animations/A_Ecy_Walk.A_Ecy_Walk",
    },
}


def actor_tags(actor):
    return {str(tag) for tag in actor.get_editor_property("tags")}


def asset_path(asset):
    return asset.get_path_name() if asset else None


def is_unit_scale(vector, tolerance=0.001):
    return (
        abs(vector.x - 1.0) <= tolerance
        and abs(vector.y - 1.0) <= tolerance
        and abs(vector.z - 1.0) <= tolerance
    )


def active_animation(component):
    try:
        data = component.get_editor_property("animation_data")
        return data.get_editor_property("anim_to_play")
    except Exception:
        return None


def safe_property(obj, name):
    try:
        return obj.get_editor_property(name)
    except Exception:
        return None


def safe_call(obj, name, *args):
    try:
        return getattr(obj, name)(*args)
    except Exception:
        return None


def material_paths(component):
    if not component:
        return []
    paths = []
    for index in range(component.get_num_materials()):
        paths.append(asset_path(component.get_material(index)))
    return paths


level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not level_subsystem.load_level(MAP_PATH):
    raise RuntimeError(f"Could not load {MAP_PATH}")

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = actor_subsystem.get_all_level_actors()
npcs = [actor for actor in actors if RESIDENT_TAG in actor_tags(actor)]
triggers = [
    actor for actor in actors if DIALOGUE_TRIGGER_TAG in actor_tags(actor)
]
player_starts = [
    actor for actor in actors if isinstance(actor, unreal.PlayerStart)
]
legacy_ai_signs = [
    actor
    for actor in actors
    if actor.get_actor_label().startswith("Aociety_AI_Village_AI_Sign")
]

print(
    "[AIMapAudit] counts npcs=%d triggers=%d player_starts=%d "
    "legacy_ai_signs=%d"
    % (len(npcs), len(triggers), len(player_starts), len(legacy_ai_signs))
)

errors = []
if len(npcs) != 2:
    errors.append(f"expected 2 NPCs, got {len(npcs)}")
if len(triggers) != 2:
    errors.append(f"expected 2 dialogue triggers, got {len(triggers)}")
if len(player_starts) != 1:
    errors.append(f"expected 1 PlayerStart, got {len(player_starts)}")
if legacy_ai_signs:
    errors.append(
        "legacy AI sign is still present: "
        + ", ".join(actor.get_actor_label() for actor in legacy_ai_signs)
    )

npcs_by_id = {}
for actor in npcs:
    npc_id = actor.get_editor_property("npc_id")
    display_name = actor.get_editor_property("display_name")
    idle = actor.get_editor_property("idle_animation")
    walk = actor.get_editor_property("walk_animation")
    component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
    mesh = component.get_skinned_asset() if component else None
    active = active_animation(component) if component else None
    component_scale = (
        component.get_editor_property("relative_scale3d")
        if component
        else None
    )
    tags = actor_tags(actor)
    visible = component.is_visible() if component else None
    hidden_in_game = safe_property(component, "hidden_in_game")
    owner_no_see = safe_property(component, "owner_no_see")
    only_owner_see = safe_property(component, "only_owner_see")
    bounds_scale = safe_property(component, "bounds_scale")
    min_draw_distance = safe_property(component, "min_draw_distance")
    max_draw_distance = safe_property(component, "ld_max_draw_distance")
    allow_cull_distance_volume = safe_property(
        component, "allow_cull_distance_volume"
    )
    materials = material_paths(component)

    print(
        "[AIMapAudit] npc id=%s name=%s label=%s location=%s rotation=%s "
        "actor_scale=%s "
        "mesh_scale=%s mesh=%s mode=%s active=%s idle=%s walk=%s "
        "actor_hidden=%s visible=%s hidden_in_game=%s owner_no_see=%s "
        "only_owner_see=%s bounds_scale=%s min_draw_distance=%s "
        "max_draw_distance=%s allow_cull_distance_volume=%s materials=%s "
        "wander=%s speed=%.1f tags=%s"
        % (
            npc_id,
            display_name,
            actor.get_actor_label(),
            actor.get_actor_location(),
            actor.get_actor_rotation(),
            actor.get_actor_scale3d(),
            component_scale,
            asset_path(mesh),
            component.get_animation_mode() if component else None,
            asset_path(active),
            asset_path(idle),
            asset_path(walk),
            safe_call(actor, "is_hidden"),
            visible,
            hidden_in_game,
            owner_no_see,
            only_owner_see,
            bounds_scale,
            min_draw_distance,
            max_draw_distance,
            allow_cull_distance_volume,
            materials,
            actor.get_editor_property("enable_wander"),
            actor.get_editor_property("wander_speed"),
            sorted(tags),
        )
    )

    if npc_id in npcs_by_id:
        errors.append(f"duplicate NPC id {npc_id}")
    npcs_by_id[npc_id] = actor
    expected = EXPECTED_NPCS.get(npc_id)
    if not expected:
        errors.append(f"unexpected NPC id {npc_id}")
        continue
    if MODEL_TAG not in tags:
        errors.append(f"{npc_id} is missing tag {MODEL_TAG}")
    if not is_unit_scale(actor.get_actor_scale3d()):
        errors.append(f"{npc_id} actor scale is {actor.get_actor_scale3d()}")
    if not component:
        errors.append(f"{npc_id} has no skeletal mesh component")
        continue
    if not is_unit_scale(component_scale):
        errors.append(f"{npc_id} mesh scale is {component_scale}")
    if visible is False:
        errors.append(f"{npc_id} mesh is not visible")
    if hidden_in_game is True:
        errors.append(f"{npc_id} mesh is hidden in game")
    if owner_no_see is True or only_owner_see is True:
        errors.append(f"{npc_id} has owner visibility filtering enabled")
    if not materials or any(material is None for material in materials):
        errors.append(f"{npc_id} has missing material slots: {materials}")
    if asset_path(mesh) != expected["mesh"]:
        errors.append(f"{npc_id} mesh is {asset_path(mesh)}")
    if asset_path(idle) != expected["idle"]:
        errors.append(f"{npc_id} idle animation is {asset_path(idle)}")
    if asset_path(walk) != expected["walk"]:
        errors.append(f"{npc_id} walk animation is {asset_path(walk)}")
    if not actor.get_editor_property("enable_wander"):
        errors.append(f"{npc_id} wandering is disabled")

if set(npcs_by_id) != set(EXPECTED_NPCS):
    errors.append(f"NPC ids are {sorted(npcs_by_id)}")

trigger_ids = set()
for actor in triggers:
    tags = actor_tags(actor)
    ids = tags.intersection(EXPECTED_NPCS)
    component = actor.get_component_by_class(unreal.BoxComponent)
    print(
        "[AIMapAudit] trigger label=%s location=%s actor_scale=%s tags=%s "
        "extent=%s overlap=%s"
        % (
            actor.get_actor_label(),
            actor.get_actor_location(),
            actor.get_actor_scale3d(),
            sorted(tags),
            component.get_unscaled_box_extent() if component else None,
            component.get_editor_property("generate_overlap_events")
            if component
            else None,
        )
    )
    if len(ids) != 1:
        errors.append(
            f"{actor.get_actor_label()} must have exactly one resident id tag"
        )
        continue
    npc_id = next(iter(ids))
    if npc_id in trigger_ids:
        errors.append(f"duplicate trigger for {npc_id}")
    trigger_ids.add(npc_id)
    if not component:
        errors.append(f"trigger for {npc_id} has no box component")
    if not is_unit_scale(actor.get_actor_scale3d()):
        errors.append(f"trigger for {npc_id} scale is {actor.get_actor_scale3d()}")
    npc = npcs_by_id.get(npc_id)
    if npc and (
        actor.get_actor_location() - npc.get_actor_location()
    ).length() > 1.0:
        errors.append(f"trigger for {npc_id} is not centered on its NPC")

if trigger_ids != set(EXPECTED_NPCS):
    errors.append(f"trigger ids are {sorted(trigger_ids)}")

for actor in player_starts:
    rotation = actor.get_actor_rotation()
    print(
        f"[AIMapAudit] player_start label={actor.get_actor_label()} "
        f"location={actor.get_actor_location()} rotation={rotation} "
        f"scale={actor.get_actor_scale3d()}"
    )
    if actor.get_actor_label() != "Aociety_AI_PlayerStart":
        errors.append(f"unexpected PlayerStart label {actor.get_actor_label()}")
    if not is_unit_scale(actor.get_actor_scale3d()):
        errors.append(f"PlayerStart scale is {actor.get_actor_scale3d()}")
    if abs(rotation.yaw - EXPECTED_PLAYER_START_YAW) > 0.1:
        errors.append(
            "PlayerStart faces away from the plaza: "
            f"yaw={rotation.yaw:.1f}, expected={EXPECTED_PLAYER_START_YAW:.1f}"
        )

if errors:
    for error in errors:
        print(f"[AIMapAudit] ERROR {error}")
    raise RuntimeError("AI map audit failed with %d error(s)" % len(errors))

print("[AIMapAudit] PASS")
