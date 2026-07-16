import unreal


ANIMATIONS = (
    ("/Game/Aociety/Characters/NPC_Cute/AliciaSolid/Animations/A_AliciaSolid_Idle", 61),
    ("/Game/Aociety/Characters/NPC_Cute/AliciaSolid/Animations/A_AliciaSolid_Walk", 33),
    ("/Game/Aociety/Characters/NPC_Cute/AliciaSakura/Animations/A_AliciaSakura_Idle", 61),
    ("/Game/Aociety/Characters/NPC_Cute/AliciaSakura/Animations/A_AliciaSakura_Walk", 33),
)

for path, frame_count in ANIMATIONS:
    backup_path = f"{path}_ImportedBackup"
    if not unreal.EditorAssetLibrary.does_asset_exist(backup_path):
        if not unreal.EditorAssetLibrary.duplicate_asset(path, backup_path):
            raise RuntimeError(f"Could not create backup: {backup_path}")

    animation = unreal.load_asset(path)
    positions = []
    rotations = []
    scales = []
    for frame in range(frame_count):
        pose = unreal.AnimationLibrary.get_bone_pose_for_frame(
            animation, "hips", frame, False
        )
        positions.append(pose.translation)
        rotations.append(pose.rotation)
        scales.append(unreal.Vector(1.0, 1.0, 1.0))

    controller = animation.get_editor_property("controller")
    if not controller.set_bone_track_keys(
        "hips", positions, rotations, scales, False
    ):
        raise RuntimeError(f"Could not repair hips scale: {path}")
    unreal.EditorAssetLibrary.save_loaded_asset(animation, only_if_is_dirty=False)
    fixed = unreal.AnimationLibrary.get_bone_pose_for_frame(
        animation, "hips", 0, False
    )
    print(f"[NPCAnimationRepair] animation={path} hips_pose={fixed}")

unreal.EditorAssetLibrary.save_directory(
    "/Game/Aociety/Characters/NPC_Cute", only_if_is_dirty=False, recursive=True
)
print("[NPCAnimationRepair] complete")
