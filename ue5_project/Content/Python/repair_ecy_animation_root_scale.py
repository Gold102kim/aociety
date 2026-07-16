import unreal


ANIMATIONS = (
    ("/Game/Aociety/Characters/Ecy/Animations/A_Ecy_Idle", 61),
    ("/Game/Aociety/Characters/Ecy/Animations/A_Ecy_Walk", 33),
)

for path, frame_count in ANIMATIONS:
    animation = unreal.load_asset(path)
    if not animation:
        raise RuntimeError(f"Missing animation: {path}")

    positions = []
    rotations = []
    scales = []
    for frame in range(frame_count):
        pose = unreal.AnimationLibrary.get_bone_pose_for_frame(
            animation, "root_218", frame, False
        )
        positions.append(pose.translation)
        rotations.append(pose.rotation)
        scales.append(unreal.Vector(1.0, 1.0, 1.0))

    controller = animation.get_editor_property("controller")
    if not controller.set_bone_track_keys(
        "root_218", positions, rotations, scales, False
    ):
        raise RuntimeError(f"Could not repair root scale: {path}")

    unreal.AnimationLibrary.finalize_bone_animation(animation)
    unreal.EditorAssetLibrary.save_loaded_asset(animation, only_if_is_dirty=False)
    fixed = unreal.AnimationLibrary.get_bone_pose_for_frame(
        animation, "root_218", 0, False
    )
    print(f"[EcyAnimationRepair] animation={path} root_pose={fixed}")

print("[EcyAnimationRepair] complete")
