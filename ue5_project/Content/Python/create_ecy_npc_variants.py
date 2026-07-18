import unreal


GENERATED_ROOT = "/Game/Aociety/Characters/GeneratedMaterials"
ECY_ROOT = "/Game/Aociety/Characters/Ecy"


def create_tinted_material(asset_name, texture_path, tint, masked, roughness, specular):
    asset_path = f"{GENERATED_ROOT}/{asset_name}"
    existing = unreal.load_asset(asset_path)
    if existing:
        unreal.EditorAssetLibrary.delete_asset(asset_path)

    texture = unreal.load_asset(texture_path)
    if not texture:
        raise RuntimeError(f"Missing texture: {texture_path}")

    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name,
        GENERATED_ROOT,
        unreal.Material,
        unreal.MaterialFactoryNew(),
    )
    if not material:
        raise RuntimeError(f"Could not create material: {asset_path}")

    material.set_editor_property("two_sided", masked)
    unreal.MaterialEditingLibrary.set_base_material_usage(
        material,
        unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH,
        True,
    )
    material.set_editor_property(
        "blend_mode",
        unreal.BlendMode.BLEND_MASKED if masked else unreal.BlendMode.BLEND_OPAQUE,
    )
    if masked:
        material.set_editor_property("opacity_mask_clip_value", 0.333)

    sample = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionTextureSample, -520, -100
    )
    sample.set_editor_property("texture", texture)

    tint_node = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector, -520, 80
    )
    tint_node.set_editor_property("constant", unreal.LinearColor(*tint, 1.0))

    blend = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionLinearInterpolate, -250, -80
    )
    blend_alpha = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, -500, 210
    )
    blend_alpha.set_editor_property("r", 0.58)
    unreal.MaterialEditingLibrary.connect_material_expressions(sample, "RGB", blend, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(tint_node, "", blend, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(blend_alpha, "", blend, "Alpha")
    unreal.MaterialEditingLibrary.connect_material_property(
        blend, "", unreal.MaterialProperty.MP_BASE_COLOR
    )
    emissive_strength = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, -10, -20
    )
    emissive_strength.set_editor_property("r", 0.025)
    emissive = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 160, -80
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(blend, "", emissive, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(
        emissive_strength, "", emissive, "B"
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        emissive, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR
    )
    if masked:
        unreal.MaterialEditingLibrary.connect_material_property(
            sample, "A", unreal.MaterialProperty.MP_OPACITY_MASK
        )

    constants = (
        (unreal.MaterialProperty.MP_METALLIC, 0.0, -80, 70),
        (unreal.MaterialProperty.MP_SPECULAR, specular, -80, 140),
        (unreal.MaterialProperty.MP_ROUGHNESS, roughness, -80, 210),
        (unreal.MaterialProperty.MP_AMBIENT_OCCLUSION, 1.0, -80, 280),
    )
    for prop, value, x, y in constants:
        node = unreal.MaterialEditingLibrary.create_material_expression(
            material, unreal.MaterialExpressionConstant, x, y
        )
        node.set_editor_property("r", value)
        unreal.MaterialEditingLibrary.connect_material_property(node, "", prop)

    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=False)
    print(f"[AocietyNPCVariant] created={asset_path}")


variants = (
    (
        "M_EcyNPC_Linxi_Cloth",
        f"{ECY_ROOT}/cloth_Base_color",
        (0.55, 0.08, 0.30),
        False,
        0.86,
        0.22,
    ),
    (
        "M_EcyNPC_Linxi_Hair",
        f"{ECY_ROOT}/hair_Base_color",
        (0.36, 0.07, 0.52),
        True,
        0.64,
        0.30,
    ),
    (
        "M_EcyNPC_Sakura_Cloth",
        f"{ECY_ROOT}/cloth_Base_color",
        (0.05, 0.42, 0.66),
        False,
        0.86,
        0.22,
    ),
    (
        "M_EcyNPC_Sakura_Hair",
        f"{ECY_ROOT}/hair_Base_color",
        (0.48, 0.20, 0.05),
        True,
        0.64,
        0.30,
    ),
)

for variant in variants:
    create_tinted_material(*variant)

print(f"[AocietyNPCVariant] complete count={len(variants)}")
