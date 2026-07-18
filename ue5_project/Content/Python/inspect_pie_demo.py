import unreal


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_game_world()
if not world:
    raise RuntimeError("No PIE game world")

player = unreal.GameplayStatics.get_player_pawn(world, 0)
camera = unreal.GameplayStatics.get_player_camera_manager(world, 0)
print(
    f"[AocietyPIEInspect] player={player.get_name() if player else None} "
    f"class={player.get_class().get_name() if player else None} "
    f"location={player.get_actor_location() if player else None} "
    f"camera={camera.get_camera_location() if camera else None}"
)
if player:
    player_mesh = player.get_component_by_class(unreal.SkeletalMeshComponent)
    if player_mesh:
        player_anim_data = player_mesh.get_editor_property("animation_data")
        player_anim = player_anim_data.get_editor_property("anim_to_play")
        print(
            f"[AocietyPIEInspect] player_mesh={player_mesh.get_skinned_asset().get_path_name() if player_mesh.get_skinned_asset() else None} "
            f"animation_mode={player_mesh.get_animation_mode()} "
            f"animation={player_anim.get_path_name() if player_anim else None} "
            f"playing={player_mesh.is_playing()}"
        )

for actor in unreal.GameplayStatics.get_all_actors_with_tag(world, unreal.Name("AocietyResident")):
    print(
        f"[AocietyPIEInspect] npc={actor.get_name()} class={actor.get_class().get_name()} "
        f"location={actor.get_actor_location()} velocity={actor.get_velocity()}"
    )
    mesh = actor.get_component_by_class(unreal.SkeletalMeshComponent)
    if mesh:
        animation = mesh.get_animation_mode()
        animation_data = mesh.get_editor_property("animation_data")
        animation_asset = animation_data.get_editor_property("anim_to_play")
        print(
            f"[AocietyPIEInspect] mesh={mesh.get_skinned_asset().get_path_name() if mesh.get_skinned_asset() else None} "
            f"animation_mode={animation} animation={animation_asset.get_path_name() if animation_asset else None} "
            f"playing={mesh.is_playing()} relative={mesh.get_editor_property('relative_location')}"
        )
    widget = actor.get_component_by_class(unreal.WidgetComponent)
    if widget:
        print(
            f"[AocietyPIEInspect] widget scale={widget.get_editor_property('relative_scale3d')} "
            f"draw_size={widget.get_draw_size()}"
        )
