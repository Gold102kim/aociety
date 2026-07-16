import os

import unreal


FBX_PATH = r"E:\Aociety-NEW\SourceAssets\Characters\Player_Ecy\Export\SK_Ecy.fbx"
DESTINATION = "/Game/Aociety/Characters/Ecy"


if not os.path.isfile(FBX_PATH):
    raise RuntimeError(f"Missing Ecy FBX: {FBX_PATH}")

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
task = unreal.AssetImportTask()
task.set_editor_property("filename", FBX_PATH)
task.set_editor_property("destination_path", DESTINATION)
task.set_editor_property("destination_name", "SK_Ecy")
task.set_editor_property("automated", True)
task.set_editor_property("save", True)
task.set_editor_property("replace_existing", True)
task.set_editor_property("replace_existing_settings", True)

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
skeletal_data.set_editor_property("import_mesh_lods", False)
skeletal_data.set_editor_property("use_t0_as_ref_pose", True)
skeletal_data.set_editor_property("preserve_smoothing_groups", True)
skeletal_data.set_editor_property("import_morph_targets", True)
skeletal_data.set_editor_property("convert_scene", True)
skeletal_data.set_editor_property("force_front_x_axis", False)

task.set_editor_property("options", options)
asset_tools.import_asset_tasks([task])

imported_paths = list(task.get_editor_property("imported_object_paths"))
if not imported_paths:
    raise RuntimeError("Ecy import completed without creating any assets")

unreal.EditorAssetLibrary.save_directory(DESTINATION, only_if_is_dirty=False, recursive=True)
print(f"[AocietyEcyImport] imported={len(imported_paths)}")
for path in imported_paths:
    print(f"[AocietyEcyImport] {path}")
