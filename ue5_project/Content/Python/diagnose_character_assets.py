import unreal


ASSETS = (
    "/Game/Aociety/Characters/Ecy/SK_Ecy",
    "/Game/Aociety/Characters/Ecy/Animations/A_Ecy_Idle",
    "/Game/Aociety/Characters/Ecy/Animations/A_Ecy_Walk",
    "/Game/Aociety/Characters/NPC_Cute/AliciaSolid/SK_AliciaSolid",
    "/Game/Aociety/Characters/NPC_Cute/AliciaSolid/Animations/A_AliciaSolid_Idle",
    "/Game/Aociety/Characters/NPC_Cute/AliciaSolid/Animations/A_AliciaSolid_Walk",
    "/Game/Aociety/Characters/NPC_Cute/AliciaSakura/SK_AliciaSakura",
    "/Game/Aociety/Characters/NPC_Cute/AliciaSakura/Animations/A_AliciaSakura_Idle",
    "/Game/Aociety/Characters/NPC_Cute/AliciaSakura/Animations/A_AliciaSakura_Walk",
)

for path in ASSETS:
    asset = unreal.load_asset(path)
    if not asset:
        print(f"[CharacterAudit] MISSING {path}")
        continue
    skeleton = asset.get_editor_property("skeleton") if hasattr(asset, "get_editor_property") else None
    skeleton_path = skeleton.get_path_name() if skeleton else "None"
    details = [
        f"asset={path}",
        f"class={asset.get_class().get_name()}",
        f"skeleton={skeleton_path}",
    ]
    if isinstance(asset, unreal.AnimSequence):
        details.append(f"length={asset.get_play_length():.3f}")
        tracks = list(unreal.AnimationLibrary.get_animation_track_names(asset))
        details.append(f"tracks={len(tracks)}")
        details.append(f"sample_tracks={[str(name) for name in tracks[:8]]}")
    if isinstance(asset, unreal.SkeletalMesh):
        materials = []
        for material in asset.get_editor_property("materials"):
            interface = material.get_editor_property("material_interface")
            materials.append(interface.get_path_name() if interface else "None")
        details.append(f"materials={materials}")
    print("[CharacterAudit] " + " ".join(details))
