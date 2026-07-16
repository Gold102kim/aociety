import unreal


level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_subsystem.save_current_level()
unreal.EditorAssetLibrary.save_directory(
    "/Game/Aociety", only_if_is_dirty=False, recursive=True
)
print("[AocietyEditor] saved before native rebuild")
unreal.SystemLibrary.quit_editor()
