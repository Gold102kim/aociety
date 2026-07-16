import unreal


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if not world:
    raise RuntimeError("No PIE game world")

for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
    mesh = actor.get_component_by_class(unreal.SkeletalMeshComponent)
    if not mesh:
        continue
    asset = mesh.get_skinned_asset()
    print(
        f"[PIESkeletalActor] actor={actor.get_name()} label={actor.get_actor_label()} "
        f"class={actor.get_class().get_name()} "
        f"mesh_visible={mesh.is_visible()} asset={asset.get_path_name() if asset else None} "
        f"scale={mesh.get_editor_property('relative_scale3d')} animation_mode={mesh.get_animation_mode()}"
    )
