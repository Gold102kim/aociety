import unreal


mesh = unreal.load_asset("/Game/Aociety/Characters/Ecy/SK_Ecy")
skeleton = mesh.get_editor_property("skeleton")
reference_pose = skeleton.get_reference_pose()
reference_names = [str(name) for name in reference_pose.get_bone_names()]

for animation_path in (
    "/Game/Aociety/Characters/Ecy/Animations/A_Ecy_Idle",
    "/Game/Aociety/Characters/Ecy/Animations/A_Ecy_Walk",
):
    animation = unreal.load_asset(animation_path)
    tracks = [str(name) for name in unreal.AnimationLibrary.get_animation_track_names(animation)]
    print(
        f"[EcyTrackInspect] animation={animation_path} tracks={len(tracks)} ref={len(reference_names)}"
    )
    for target in ("root_218", "hips_217", "upper_leg_l_145", "lower_leg_l_144"):
        if target not in tracks:
            print(f"[EcyTrackInspect] missing={target}")
            continue
        index = tracks.index(target)
        positions, rotations, scales = unreal.AnimationLibrary.get_raw_track_data(
            animation, target
        )
        positions = list(positions)
        rotations = list(rotations)
        scales = list(scales)
        print(
            f"[EcyTrackInspect] bone={target} index={index} ref={reference_pose.get_ref_bone_pose(target)} "
            f"positions={positions[:3]} rotations={rotations[:3]} scales={scales[:2]} "
            f"pose0={unreal.AnimationLibrary.get_bone_pose_for_frame(animation, target, 0, False)} "
            f"pose10={unreal.AnimationLibrary.get_bone_pose_for_frame(animation, target, 10, False)}"
        )
