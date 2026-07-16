import unreal


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
player = unreal.GameplayStatics.get_player_pawn(world, 0)
mesh = player.get_component_by_class(unreal.SkeletalMeshComponent)
mesh.set_visibility(False, True)
print("[PlayerMeshTest] hidden")
