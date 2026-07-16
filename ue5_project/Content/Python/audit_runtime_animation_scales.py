import unreal


ANIMATIONS = (
    "/Game/Aociety/Characters/Ecy/Animations/A_Ecy_Idle",
    "/Game/Aociety/Characters/Ecy/Animations/A_Ecy_Walk",
    "/Game/Aociety/Characters/NPC_Cute/AliciaSolid/Animations/A_AliciaSolid_Idle",
    "/Game/Aociety/Characters/NPC_Cute/AliciaSolid/Animations/A_AliciaSolid_Walk",
    "/Game/Aociety/Characters/NPC_Cute/AliciaSakura/Animations/A_AliciaSakura_Idle",
    "/Game/Aociety/Characters/NPC_Cute/AliciaSakura/Animations/A_AliciaSakura_Walk",
)

for path in ANIMATIONS:
    animation = unreal.load_asset(path)
    bad = []
    tracks = unreal.AnimationLibrary.get_animation_track_names(animation)
    for bone in tracks:
        pose = unreal.AnimationLibrary.get_bone_pose_for_frame(animation, bone, 0, False)
        scale = pose.scale3d
        if min(scale.x, scale.y, scale.z) < 0.5 or max(scale.x, scale.y, scale.z) > 2.0:
            bad.append((str(bone), (scale.x, scale.y, scale.z)))
    print(f"[RuntimeScaleAudit] animation={path} tracks={len(tracks)} bad={bad}")
