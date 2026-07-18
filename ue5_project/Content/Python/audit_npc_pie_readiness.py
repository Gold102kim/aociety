import math

import unreal


MAP_PATH = "/Game/Aociety/Maps/Aociety_ForestSnowTown"
ANIMATIONS = (
    ("/Game/Aociety/Characters/NPC_Cute/AliciaSolid/Animations/A_AliciaSolid_Idle", 60),
    ("/Game/Aociety/Characters/NPC_Cute/AliciaSolid/Animations/A_AliciaSolid_Walk", 32),
    ("/Game/Aociety/Characters/NPC_Cute/AliciaSakura/Animations/A_AliciaSakura_Idle", 60),
    ("/Game/Aociety/Characters/NPC_Cute/AliciaSakura/Animations/A_AliciaSakura_Walk", 32),
)


def quaternion_delta_degrees(a, b):
    dot = abs(a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w)
    return math.degrees(2.0 * math.acos(max(-1.0, min(1.0, dot))))


level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not level_subsystem.load_level(MAP_PATH):
    raise RuntimeError(f"Could not load {MAP_PATH}")

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
npcs = [
    actor
    for actor in actor_subsystem.get_all_level_actors()
    if actor.get_actor_label().startswith("Aociety_AI_NPC_")
]
player_starts = [
    actor
    for actor in actor_subsystem.get_all_level_actors()
    if isinstance(actor, unreal.PlayerStart)
]
dialogue_triggers = [
    actor
    for actor in actor_subsystem.get_all_level_actors()
    if "AocietyDialogueTrigger"
    in {str(tag) for tag in actor.get_editor_property("tags")}
]

for actor in npcs:
    component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
    mesh = component.get_skinned_asset() if component else None
    print(
        "[NPCReadiness] actor=%s actor_scale=%s mesh_scale=%s mesh=%s idle=%s walk=%s"
        % (
            actor.get_actor_label(),
            actor.get_actor_scale3d(),
            component.get_relative_scale3d() if component else None,
            mesh.get_path_name() if mesh else None,
            actor.get_editor_property("idle_animation").get_path_name(),
            actor.get_editor_property("walk_animation").get_path_name(),
        )
    )

for path, last_frame in ANIMATIONS:
    animation = unreal.load_asset(path)
    if not animation:
        raise RuntimeError(f"Missing animation: {path}")

    max_leg_rotation = 0.0
    max_leg_translation = 0.0
    leg_tracks = []
    bad_scales = []
    for bone in unreal.AnimationLibrary.get_animation_track_names(animation):
        bone_name = str(bone)
        lower_name = bone_name.lower()
        pose_start = unreal.AnimationLibrary.get_bone_pose_for_frame(
            animation, bone, 0, False
        )
        is_leg_track = any(
            token in lower_name
            for token in ("leg", "thigh", "knee", "calf", "foot")
        )
        if is_leg_track:
            leg_tracks.append(bone_name)

        for frame in range(last_frame + 1):
            pose = unreal.AnimationLibrary.get_bone_pose_for_frame(
                animation, bone, frame, False
            )
            scale = pose.scale3d
            if min(scale.x, scale.y, scale.z) < 0.5 or max(
                scale.x, scale.y, scale.z
            ) > 2.0:
                bad_scales.append((bone_name, scale))
                break
            if is_leg_track:
                max_leg_rotation = max(
                    max_leg_rotation,
                    quaternion_delta_degrees(pose_start.rotation, pose.rotation),
                )
                max_leg_translation = max(
                    max_leg_translation,
                    (pose.translation - pose_start.translation).length(),
                )

    print(
        "[NPCReadiness] animation=%s leg_tracks=%d max_leg_rotation_deg=%.3f "
        "max_leg_translation=%.3f bad_scales=%s"
        % (
            path,
            len(leg_tracks),
            max_leg_rotation,
            max_leg_translation,
            bad_scales,
        )
    )

for actor in player_starts:
    print(
        f"[NPCReadiness] player_start={actor.get_actor_label()} "
        f"location={actor.get_actor_location()}"
    )
for actor in dialogue_triggers:
    print(
        f"[NPCReadiness] dialogue_trigger={actor.get_actor_label()} "
        f"location={actor.get_actor_location()} "
        f"tags={[str(tag) for tag in actor.get_editor_property('tags')]}"
    )

print(
    "[NPCReadiness] npc_count=%d player_start_count=%d dialogue_trigger_count=%d"
    % (len(npcs), len(player_starts), len(dialogue_triggers))
)
