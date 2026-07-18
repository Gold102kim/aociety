import os

import unreal


ANIMATIONS = (
    (
        r"E:\Aociety-NEW\SourceAssets\Characters\Player_Ecy\Animations\A_Ecy_Idle.fbx",
        "/Game/Aociety/Characters/Ecy/SK_Ecy_Skeleton",
        "/Game/Aociety/Characters/Ecy/Animations",
        "A_Ecy_Idle",
    ),
    (
        r"E:\Aociety-NEW\SourceAssets\Characters\Player_Ecy\Animations\A_Ecy_Walk.fbx",
        "/Game/Aociety/Characters/Ecy/SK_Ecy_Skeleton",
        "/Game/Aociety/Characters/Ecy/Animations",
        "A_Ecy_Walk",
    ),
    (
        r"E:\Aociety-NEW\SourceAssets\Characters\NPC_Cute\Animations\A_Alicia_Idle.fbx",
        "/Game/Aociety/Characters/NPC_Cute/AliciaSolid/SK_AliciaSolid_Skeleton",
        "/Game/Aociety/Characters/NPC_Cute/AliciaSolid/Animations",
        "A_AliciaSolid_Idle",
    ),
    (
        r"E:\Aociety-NEW\SourceAssets\Characters\NPC_Cute\Animations\A_Alicia_Walk.fbx",
        "/Game/Aociety/Characters/NPC_Cute/AliciaSolid/SK_AliciaSolid_Skeleton",
        "/Game/Aociety/Characters/NPC_Cute/AliciaSolid/Animations",
        "A_AliciaSolid_Walk",
    ),
    (
        r"E:\Aociety-NEW\SourceAssets\Characters\NPC_Cute\Animations\A_Alicia_Idle.fbx",
        "/Game/Aociety/Characters/NPC_Cute/AliciaSakura/SK_AliciaSakura_Skeleton",
        "/Game/Aociety/Characters/NPC_Cute/AliciaSakura/Animations",
        "A_AliciaSakura_Idle",
    ),
    (
        r"E:\Aociety-NEW\SourceAssets\Characters\NPC_Cute\Animations\A_Alicia_Walk.fbx",
        "/Game/Aociety/Characters/NPC_Cute/AliciaSakura/SK_AliciaSakura_Skeleton",
        "/Game/Aociety/Characters/NPC_Cute/AliciaSakura/Animations",
        "A_AliciaSakura_Walk",
    ),
)


def make_options(skeleton):
    options = unreal.FbxImportUI()
    options.set_editor_property("import_mesh", False)
    options.set_editor_property("import_as_skeletal", True)
    options.set_editor_property("import_animations", True)
    options.set_editor_property("import_materials", False)
    options.set_editor_property("import_textures", False)
    options.set_editor_property("skeleton", skeleton)
    options.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_ANIMATION)

    animation_data = options.get_editor_property("anim_sequence_import_data")
    animation_data.set_editor_property("animation_length", unreal.FBXAnimationLengthImportType.FBXALIT_EXPORTED_TIME)
    animation_data.set_editor_property("import_bone_tracks", True)
    animation_data.set_editor_property("remove_redundant_keys", False)
    animation_data.set_editor_property("convert_scene", True)
    animation_data.set_editor_property("force_front_x_axis", False)
    return options


tasks = []
for fbx_path, skeleton_path, destination, name in ANIMATIONS:
    if not os.path.isfile(fbx_path):
        raise RuntimeError(f"Missing animation FBX: {fbx_path}")
    skeleton = unreal.load_asset(skeleton_path)
    if not skeleton:
        raise RuntimeError(f"Missing target skeleton: {skeleton_path}")
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", fbx_path)
    task.set_editor_property("destination_path", destination)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("save", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("replace_existing_settings", True)
    task.set_editor_property("options", make_options(skeleton))
    tasks.append(task)

unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
for task in tasks:
    paths = list(task.get_editor_property("imported_object_paths"))
    if not paths:
        raise RuntimeError(f"Animation import failed: {task.get_editor_property('filename')}")
    print(f"[AocietyAnimationImport] {paths}")

unreal.EditorAssetLibrary.save_directory(
    "/Game/Aociety/Characters", only_if_is_dirty=False, recursive=True
)
print("[AocietyAnimationImport] Ecy=2 AliciaSolid=2 AliciaSakura=2")
