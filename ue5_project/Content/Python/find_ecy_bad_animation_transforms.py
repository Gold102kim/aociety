import math

import unreal


skeleton = unreal.load_asset("/Game/Aociety/Characters/Ecy/SK_Ecy_Skeleton")
reference = skeleton.get_reference_pose()

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
        ref = reference.get_ref_bone_pose(bone)
        delta = pose.translation - ref.translation
        distance = math.sqrt(delta.x * delta.x + delta.y * delta.y + delta.z * delta.z)
        if distance > 0.25:
            bad.append(
                (
                    str(bone),
                    round(distance, 4),
                    (round(pose.translation.x, 4), round(pose.translation.y, 4), round(pose.translation.z, 4)),
                    (round(ref.translation.x, 4), round(ref.translation.y, 4), round(ref.translation.z, 4)),
                )
            )
    bad.sort(key=lambda item: item[1], reverse=True)
    print(f"[EcyBadTransforms] animation={path} count={len(bad)} bad={bad[:40]}")
