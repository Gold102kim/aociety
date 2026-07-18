import unreal


MESHES = (
    "/Game/Aociety/Characters/Ecy/SK_Ecy",
    "/Game/Aociety/Characters/NPC_Cute/AliciaSolid/SK_AliciaSolid",
    "/Game/Aociety/Characters/NPC_Cute/AliciaSakura/SK_AliciaSakura",
)

ANIMATIONS = (
    ("/Game/Aociety/Characters/Ecy/Animations/A_Ecy_Idle", ("root_218", "hips_217", "hips")),
    ("/Game/Aociety/Characters/Ecy/Animations/A_Ecy_Walk", ("root_218", "hips_217", "hips")),
    ("/Game/Aociety/Characters/NPC_Cute/AliciaSolid/Animations/A_AliciaSolid_Idle", ("hips",)),
    ("/Game/Aociety/Characters/NPC_Cute/AliciaSolid/Animations/A_AliciaSolid_Walk", ("hips",)),
    ("/Game/Aociety/Characters/NPC_Cute/AliciaSakura/Animations/A_AliciaSakura_Idle", ("hips",)),
    ("/Game/Aociety/Characters/NPC_Cute/AliciaSakura/Animations/A_AliciaSakura_Walk", ("hips",)),
)


def vector_tuple(value):
    return tuple(round(float(part), 5) for part in (value.x, value.y, value.z))


for path in MESHES:
    mesh = unreal.load_asset(path)
    if not mesh:
        print(f"[CharacterAudit] missing_mesh={path}")
        continue
    bounds = mesh.get_bounds()
    try:
        skeleton = mesh.get_editor_property("skeleton")
    except Exception:
        skeleton = None
    materials = []
    for index, slot in enumerate(mesh.get_editor_property("materials")):
        interface = slot.get_editor_property("material_interface")
        materials.append(
            (
                index,
                str(slot.get_editor_property("material_slot_name")),
                interface.get_path_name() if interface else "None",
            )
        )
    import_data = mesh.get_editor_property("asset_import_data")
    source = import_data.get_first_filename() if import_data else ""
    print(
        f"[CharacterAudit] mesh={path} skeleton={skeleton.get_path_name() if skeleton else None} "
        f"bounds_origin={vector_tuple(bounds.origin)} bounds_extent={vector_tuple(bounds.box_extent)} "
        f"radius={round(bounds.sphere_radius, 5)} source={source} materials={materials}"
    )

for path, preferred_roots in ANIMATIONS:
    animation = unreal.load_asset(path)
    if not animation:
        print(f"[CharacterAudit] missing_animation={path}")
        continue
    skeleton = animation.get_editor_property("skeleton")
    tracks = [str(name) for name in unreal.AnimationLibrary.get_animation_track_names(animation)]
    frame_count = unreal.AnimationLibrary.get_num_frames(animation)
    sample_frames = sorted(set((0, max(0, frame_count // 4), max(0, frame_count // 2), max(0, frame_count - 1))))
    root_name = next((name for name in preferred_roots if name in tracks), tracks[0] if tracks else "")
    bad_scales = []
    for bone in tracks:
        pose = unreal.AnimationLibrary.get_bone_pose_for_frame(animation, bone, 0, False)
        scale = vector_tuple(pose.scale3d)
        if min(scale) < 0.5 or max(scale) > 2.0:
            bad_scales.append((bone, scale))
    root_samples = []
    if root_name:
        for frame in sample_frames:
            pose = unreal.AnimationLibrary.get_bone_pose_for_frame(animation, root_name, frame, False)
            root_samples.append(
                (frame, vector_tuple(pose.translation), vector_tuple(pose.scale3d))
            )
    selected_pose_samples = []
    for token in ("hips", "upper_leg_l", "upper_leg_r", "leftupleg", "rightupleg"):
        bone = next((track for track in tracks if token in track.lower()), None)
        if bone:
            pose = unreal.AnimationLibrary.get_bone_pose_for_frame(animation, bone, 0, False)
            selected_pose_samples.append(
                (bone, vector_tuple(pose.translation), vector_tuple(pose.scale3d))
            )
    animated_bones = []
    for bone in tracks:
        first = unreal.AnimationLibrary.get_bone_pose_for_frame(animation, bone, 0, False)
        comparisons = [
            unreal.AnimationLibrary.get_bone_pose_for_frame(animation, bone, frame, False)
            for frame in sample_frames[1:]
        ]
        rotation_delta = max(
            (first.rotation.angular_distance(other.rotation) for other in comparisons),
            default=0.0,
        )
        translation_delta = max(
            ((first.translation - other.translation).length() for other in comparisons),
            default=0.0,
        )
        if rotation_delta > 0.002 or translation_delta > 0.002:
            animated_bones.append((bone, round(rotation_delta, 5), round(translation_delta, 5)))
    print(
        f"[CharacterAudit] animation={path} skeleton={skeleton.get_path_name() if skeleton else None} "
        f"frames={frame_count} tracks={len(tracks)} root={root_name} root_samples={root_samples} "
        f"selected_pose_samples={selected_pose_samples} bad_scales={bad_scales} "
        f"animated_bones={animated_bones[:24]}"
    )

print("[CharacterAudit] complete")
