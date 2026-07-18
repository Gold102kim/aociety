import os

import unreal


NPCS = (
    (
        "AliciaSolid",
        r"E:\Aociety-NEW\SourceAssets\Characters\NPC_Cute\Export\AliciaSolid\SK_AliciaSolid.fbx",
    ),
    (
        "AliciaSakura",
        r"E:\Aociety-NEW\SourceAssets\Characters\NPC_Cute\Export\AliciaSakura\SK_AliciaSakura.fbx",
    ),
)
ROOT_DESTINATION = "/Game/Aociety/Characters/NPC_Cute"


def make_options():
    options = unreal.FbxImportUI()
    options.set_editor_property("import_mesh", True)
    options.set_editor_property("import_as_skeletal", True)
    options.set_editor_property("import_animations", False)
    options.set_editor_property("import_materials", True)
    options.set_editor_property("import_textures", True)
    options.set_editor_property("create_physics_asset", True)
    options.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH)

    skeletal_data = options.get_editor_property("skeletal_mesh_import_data")
    skeletal_data.set_editor_property("import_content_type", unreal.FBXImportContentType.FBXICT_ALL)
    skeletal_data.set_editor_property("use_t0_as_ref_pose", True)
    skeletal_data.set_editor_property("preserve_smoothing_groups", True)
    skeletal_data.set_editor_property("import_morph_targets", True)
    skeletal_data.set_editor_property("convert_scene", True)
    skeletal_data.set_editor_property("force_front_x_axis", False)
    return options


tasks = []
for name, fbx_path in NPCS:
    if not os.path.isfile(fbx_path):
        raise RuntimeError(f"Missing cute NPC FBX: {fbx_path}")
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", fbx_path)
    task.set_editor_property("destination_path", f"{ROOT_DESTINATION}/{name}")
    task.set_editor_property("destination_name", f"SK_{name}")
    task.set_editor_property("automated", True)
    task.set_editor_property("save", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("replace_existing_settings", True)
    task.set_editor_property("options", make_options())
    tasks.append(task)

unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)

for task in tasks:
    imported_paths = list(task.get_editor_property("imported_object_paths"))
    if not imported_paths:
        raise RuntimeError(f"No assets created from {task.get_editor_property('filename')}")
    for path in imported_paths:
        print(f"[AocietyCuteNPCImport] {path}")

unreal.EditorAssetLibrary.save_directory(
    ROOT_DESTINATION, only_if_is_dirty=False, recursive=True
)
print("[AocietyCuteNPCImport] characters=2")
