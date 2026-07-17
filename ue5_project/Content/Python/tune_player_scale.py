import unreal


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if not world:
    raise RuntimeError("No PIE game world")
player = unreal.GameplayStatics.get_player_pawn(world, 0)
mesh = player.get_component_by_class(unreal.SkeletalMeshComponent)
mesh.set_relative_scale3d(unreal.Vector(0.35, 0.35, 0.35))
print(f"[PlayerScaleTune] scale={mesh.get_editor_property('relative_scale3d')}")
