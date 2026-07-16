import unreal


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
player = unreal.GameplayStatics.get_player_pawn(world, 0)
mesh = player.get_component_by_class(unreal.SkeletalMeshComponent)
mesh.set_animation_mode(unreal.AnimationMode.ANIMATION_BLUEPRINT)
mesh.set_visibility(True, True)
print("[PlayerPoseTest] animation blueprint mode without class")
