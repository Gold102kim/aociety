import unreal


for path in (
    "/Game/Aociety/Characters/Ecy/Animations/A_Ecy_Idle",
    "/Game/Aociety/Characters/Ecy/Animations/A_Ecy_Walk",
):
    animation = unreal.load_asset(path)
    bad = []
    for bone in unreal.AnimationLibrary.get_animation_track_names(animation):
        pose = unreal.AnimationLibrary.get_bone_pose_for_frame(
            animation, bone, 0, False
        )
        scale = pose.scale3d
        values = (scale.x, scale.y, scale.z)
        if min(values) < 0.5 or max(values) > 2.0:
            bad.append((str(bone), values))
    print(f"[EcyBadScales] animation={path} count={len(bad)} bad={bad}")
