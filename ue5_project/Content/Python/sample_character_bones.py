import unreal


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_game_world()
if not world:
    raise RuntimeError("No PIE game world")

actors = []
player = unreal.GameplayStatics.get_player_pawn(world, 0)
if player:
    player_mesh = player.get_component_by_class(unreal.SkeletalMeshComponent)
    player_bone = ""
    for index in range(player_mesh.get_num_bones()):
        candidate = str(player_mesh.get_bone_name(index))
        if "upper_leg" in candidate.lower() and "l" in candidate.lower():
            player_bone = candidate
            break
    if not player_bone:
        raise RuntimeError("Could not find Ecy left upper-leg bone")
    actors.append(("Ecy", player, player_bone))
for actor in unreal.GameplayStatics.get_all_actors_with_tag(
    world, unreal.Name("AocietyResident")
):
    actors.append((actor.get_name(), actor, "LeftUpLeg"))

for label, actor, bone in actors:
    mesh = actor.get_component_by_class(unreal.SkeletalMeshComponent)
    transform = mesh.get_socket_transform(
        bone, unreal.RelativeTransformSpace.RTS_COMPONENT
    )
    print(
        f"[CharacterBoneSample] label={label} bone={bone} "
        f"rotation={transform.rotation.rotator()} location={transform.translation} "
        f"playing={mesh.is_playing()}"
    )
