import math

import unreal


RESIDENT_TAG = unreal.Name("AocietyResident")
DIALOGUE_TRIGGER_TAG = unreal.Name("AocietyDialogueTrigger")
EXPECTED_NPC_IDS = {"npc_01", "npc_02"}


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


def camera_metrics(camera, actor):
    if not camera:
        return None, None, None
    origin = camera.get_world_location()
    target = actor.get_actor_location()
    delta = target - origin
    distance = delta.length()
    if distance <= 0.001:
        return distance, 0.0, True
    forward = camera.get_forward_vector()
    dot = (
        forward.x * delta.x + forward.y * delta.y + forward.z * delta.z
    ) / distance
    dot = max(-1.0, min(1.0, dot))
    return distance, math.degrees(math.acos(dot)), dot > 0.0


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if not world:
    raise RuntimeError("No PIE game world")

npcs = unreal.GameplayStatics.get_all_actors_with_tag(world, RESIDENT_TAG)
triggers = unreal.GameplayStatics.get_all_actors_with_tag(
    world, DIALOGUE_TRIGGER_TAG
)
player_starts = unreal.GameplayStatics.get_all_actors_of_class(
    world, unreal.PlayerStart
)
player = unreal.GameplayStatics.get_player_pawn(world, 0)
player_camera = None

print(
    "[AIPIEAudit] counts npcs=%d triggers=%d player_starts=%d player=%s"
    % (
        len(npcs),
        len(triggers),
        len(player_starts),
        player.get_name() if player else None,
    )
)

if player:
    controller = unreal.GameplayStatics.get_player_controller(world, 0)
    print(
        "[AIPIEAudit] player_state location=%s rotation=%s velocity=%s "
        "scale=%s control_rotation=%s"
        % (
            player.get_actor_location(),
            player.get_actor_rotation(),
            player.get_velocity(),
            player.get_actor_scale3d(),
            controller.get_control_rotation() if controller else None,
        )
    )
    for component in player.get_components_by_class(unreal.SkeletalMeshComponent):
        mesh_path = asset_path(component.get_skinned_asset())
        anim_instance = component.get_anim_instance()
        print(
            "[AIPIEAudit] player_mesh component=%s mesh=%s relative_location=%s "
            "relative_rotation=%s relative_scale=%s visible=%s hidden_in_game=%s "
            "anim_instance=%s bounds=%s"
            % (
                component.get_name(),
                mesh_path,
                safe_property(component, "relative_location"),
                safe_property(component, "relative_rotation"),
                safe_property(component, "relative_scale3d"),
                component.is_visible(),
                safe_property(component, "hidden_in_game"),
                anim_instance.get_class().get_name() if anim_instance else None,
                unreal.SystemLibrary.get_component_bounds(component),
            )
        )
        if mesh_path and "/Aociety/Characters/Ecy/" in mesh_path:
            try:
                bone_count = component.get_num_bones()
                bone_names = [
                    str(component.get_bone_name(index))
                    for index in range(bone_count)
                ]
                sampled_bones = [bone_names[0]] if bone_names else []
                for expected_bone in (
                    "root_218",
                    "hips_217",
                    "spine_141",
                    "chest_140",
                    "foot_L_143",
                    "foot_R_150",
                    "upper_leg_L_145",
                    "upper_leg_R_148",
                    "shoulder_L_116",
                    "shoulder_R_125",
                    "head_77",
                ):
                    if expected_bone in bone_names:
                        sampled_bones.append(expected_bone)
                for bone_name in sampled_bones:
                    print(
                        "[AIPIEAudit] ecy_bone name=%s world_location=%s"
                        % (bone_name, component.get_socket_location(bone_name))
                    )
            except Exception as exception:
                print(f"[AIPIEAudit] ecy_bone_probe_error={exception}")
    for component in player.get_components_by_class(unreal.CameraComponent):
        if component.is_active() and player_camera is None:
            player_camera = component
        print(
            "[AIPIEAudit] player_camera component=%s world_location=%s "
            "world_rotation=%s active=%s"
            % (
                component.get_name(),
                component.get_world_location(),
                component.get_world_rotation(),
                component.is_active(),
            )
        )

errors = []
if len(npcs) != 2:
    errors.append(f"expected 2 NPCs, got {len(npcs)}")
if len(triggers) != 2:
    errors.append(f"expected 2 dialogue triggers, got {len(triggers)}")
if len(player_starts) != 1:
    errors.append(f"expected 1 PlayerStart, got {len(player_starts)}")

seen_npc_ids = set()
for actor in npcs:
    npc_id = actor.get_editor_property("npc_id")
    idle = actor.get_editor_property("idle_animation")
    walk = actor.get_editor_property("walk_animation")
    component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
    widget = actor.get_component_by_class(unreal.WidgetComponent)
    animation = active_animation(component) if component else None
    velocity = actor.get_velocity()
    speed = (velocity.x * velocity.x + velocity.y * velocity.y) ** 0.5
    visible = component.is_visible() if component else None
    hidden_in_game = safe_property(component, "hidden_in_game")
    owner_no_see = safe_property(component, "owner_no_see")
    only_owner_see = safe_property(component, "only_owner_see")
    bounds_scale = safe_property(component, "bounds_scale")
    min_draw_distance = safe_property(component, "min_draw_distance")
    max_draw_distance = safe_property(component, "ld_max_draw_distance")
    local_bounds = safe_call(component, "get_local_bounds") if component else None
    materials = material_paths(component)
    camera_distance, camera_angle, camera_in_front = camera_metrics(
        player_camera, actor
    )

    print(
        "[AIPIEAudit] npc id=%s actor=%s location=%s velocity=%s speed=%.2f "
        "actor_hidden=%s actor_scale=%s mesh_location=%s mesh_rotation=%s "
        "mesh_scale=%s mesh=%s mode=%s active=%s playing=%s visible=%s "
        "hidden_in_game=%s owner_no_see=%s only_owner_see=%s "
        "bounds_scale=%s local_bounds=%s min_draw_distance=%s "
        "max_draw_distance=%s materials=%s idle=%s walk=%s "
        "widget_scale=%s widget_visible=%s camera_distance=%s "
        "camera_angle=%s camera_in_front=%s"
        % (
            npc_id,
            actor.get_name(),
            actor.get_actor_location(),
            actor.get_velocity(),
            speed,
            safe_call(actor, "is_hidden"),
            actor.get_actor_scale3d(),
            component.get_world_location() if component else None,
            component.get_world_rotation() if component else None,
            component.get_editor_property("relative_scale3d") if component else None,
            asset_path(component.get_skinned_asset()) if component else None,
            component.get_animation_mode() if component else None,
            asset_path(animation),
            component.is_playing() if component else None,
            visible,
            hidden_in_game,
            owner_no_see,
            only_owner_see,
            bounds_scale,
            local_bounds,
            min_draw_distance,
            max_draw_distance,
            materials,
            asset_path(idle),
            asset_path(walk),
            widget.get_editor_property("relative_scale3d") if widget else None,
            widget.is_visible() if widget else None,
            "%.1f" % camera_distance if camera_distance is not None else None,
            "%.1f" % camera_angle if camera_angle is not None else None,
            camera_in_front,
        )
    )

    if npc_id in seen_npc_ids:
        errors.append(f"duplicate NPC id {npc_id}")
    seen_npc_ids.add(npc_id)
    if npc_id not in EXPECTED_NPC_IDS:
        errors.append(f"unexpected NPC id {npc_id}")
    if not is_unit_scale(actor.get_actor_scale3d()):
        errors.append(f"{npc_id} actor scale is {actor.get_actor_scale3d()}")
    if not component:
        errors.append(f"{npc_id} has no skeletal mesh component")
        continue
    component_scale = component.get_editor_property("relative_scale3d")
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
    if not idle or not walk:
        errors.append(f"{npc_id} is missing idle or walk animation")
    if not component.is_playing():
        errors.append(f"{npc_id} animation is not playing")
    if not widget:
        errors.append(f"{npc_id} has no dialogue widget component")

if seen_npc_ids != EXPECTED_NPC_IDS:
    errors.append(f"NPC ids are {sorted(seen_npc_ids)}")

trigger_ids = set()
for actor in triggers:
    tags = actor_tags(actor)
    ids = tags.intersection(EXPECTED_NPC_IDS)
    print(
        f"[AIPIEAudit] trigger actor={actor.get_name()} "
        f"location={actor.get_actor_location()} scale={actor.get_actor_scale3d()} "
        f"tags={sorted(tags)}"
    )
    if len(ids) != 1:
        errors.append(f"{actor.get_name()} must have exactly one resident id tag")
    else:
        trigger_ids.add(next(iter(ids)))
    if not is_unit_scale(actor.get_actor_scale3d()):
        errors.append(f"{actor.get_name()} trigger scale is {actor.get_actor_scale3d()}")

if trigger_ids != EXPECTED_NPC_IDS:
    errors.append(f"trigger ids are {sorted(trigger_ids)}")

for actor in player_starts:
    print(
        f"[AIPIEAudit] player_start actor={actor.get_name()} "
        f"location={actor.get_actor_location()} scale={actor.get_actor_scale3d()}"
    )

if errors:
    for error in errors:
        print(f"[AIPIEAudit] ERROR {error}")
    raise RuntimeError("AI PIE audit failed with %d error(s)" % len(errors))

print("[AIPIEAudit] PASS")
