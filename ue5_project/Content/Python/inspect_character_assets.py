import unreal


ASSETS = (
    "/Game/Aociety/Characters/Ecy/SK_Ecy",
    "/Game/Aociety/Characters/NPC/AvatarSample_A/SK_AvatarSample_A",
    "/Game/Aociety/Characters/NPC/AvatarSample_C/SK_AvatarSample_C",
)

for path in ASSETS:
    mesh = unreal.load_asset(path)
    if not mesh:
        print(f"[AocietyCharacterInspect] missing={path}")
        continue
    bounds = mesh.get_bounds()
    skeleton = mesh.get_editor_property("skeleton")
    print(
        "[AocietyCharacterInspect] path=%s origin=%s extent=%s radius=%.2f skeleton=%s"
        % (
            path,
            bounds.origin,
            bounds.box_extent,
            bounds.sphere_radius,
            skeleton.get_path_name() if skeleton else "None",
        )
    )
