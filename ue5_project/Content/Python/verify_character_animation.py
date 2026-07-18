import time

import unreal


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_game_world()
if not world:
    raise RuntimeError("No PIE game world")

checks = []
player = unreal.GameplayStatics.get_player_pawn(world, 0)
if player:
    checks.append(
        (
            "Ecy",
            player.get_component_by_class(unreal.SkeletalMeshComponent),
            unreal.load_asset("/Game/Aociety/Characters/Ecy/Animations/A_Ecy_Walk"),
            "upper_leg.L_145",
        )
    )

for actor in unreal.GameplayStatics.get_all_actors_with_tag(
    world, unreal.Name("AocietyResident")
):
    mesh = actor.get_component_by_class(unreal.SkeletalMeshComponent)
    asset_path = mesh.get_skinned_asset().get_path_name()
    if "AliciaSolid" in asset_path:
        animation = unreal.load_asset(
            "/Game/Aociety/Characters/NPC_Cute/AliciaSolid/Animations/A_AliciaSolid_Walk"
        )
    else:
        animation = unreal.load_asset(
            "/Game/Aociety/Characters/NPC_Cute/AliciaSakura/Animations/A_AliciaSakura_Walk"
        )
    checks.append((actor.get_name(), mesh, animation, "LeftUpLeg"))

for label, mesh, animation, bone in checks:
    mesh.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
    mesh.play_animation(animation, True)
    time.sleep(0.05)
    first = mesh.get_socket_transform(bone, unreal.RelativeTransformSpace.RTS_COMPONENT)
    time.sleep(0.32)
    second = mesh.get_socket_transform(bone, unreal.RelativeTransformSpace.RTS_COMPONENT)
    first_rotation = first.rotation.rotator()
    second_rotation = second.rotation.rotator()
    print(
        f"[CharacterAnimationVerify] label={label} bone={bone} "
        f"first={first_rotation} second={second_rotation} playing={mesh.is_playing()}"
    )
