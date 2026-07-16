import os

import unreal


SOURCE = r"E:\Aociety-NEW\SourceAssets\UI\speech_bubble_ivory.png"
DESTINATION = "/Game/Aociety/UI"
NAME = "T_SpeechBubble_Ivory"

if not os.path.isfile(SOURCE):
    raise RuntimeError(f"Missing dialogue UI source: {SOURCE}")

task = unreal.AssetImportTask()
task.set_editor_property("filename", SOURCE)
task.set_editor_property("destination_path", DESTINATION)
task.set_editor_property("destination_name", NAME)
task.set_editor_property("automated", True)
task.set_editor_property("save", True)
task.set_editor_property("replace_existing", True)

unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
texture = unreal.load_asset(f"{DESTINATION}/{NAME}")
if not texture:
    raise RuntimeError("Dialogue UI texture import failed")
texture.set_editor_property("srgb", True)
texture.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_EDITOR_ICON)
texture.set_editor_property("filter", unreal.TextureFilter.TF_TRILINEAR)
texture.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
texture.set_editor_property("never_stream", True)
texture.set_editor_property("address_x", unreal.TextureAddress.TA_CLAMP)
texture.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
unreal.EditorAssetLibrary.save_loaded_asset(texture, only_if_is_dirty=False)
print(f"[DialogueUIImport] {texture.get_path_name()}")
