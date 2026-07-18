import os

import unreal


GENERATED_ROOT = "/Game/Aociety/Characters/GeneratedMaterials"


def create_hidden_outline_material():
    asset_name = "M_Ecy_OutlineDisabled_v4"
    path = f"{GENERATED_ROOT}/{asset_name}"
    material = unreal.load_asset(path)
    if material:
        return material
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name,
        GENERATED_ROOT,
        unreal.Material,
        unreal.MaterialFactoryNew(),
    )
    if not material:
        raise RuntimeError(f"Could not create hidden outline material: {path}")
    material.set_editor_property("two_sided", False)
    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    material.set_editor_property("opacity_mask_clip_value", 0.333)
    opacity = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, -240, 20
    )
    opacity.set_editor_property("r", 0.0)
    unreal.MaterialEditingLibrary.connect_material_property(
        opacity, "", unreal.MaterialProperty.MP_OPACITY_MASK
    )
    roughness = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, -240, 120
    )
    roughness.set_editor_property("r", 1.0)
    unreal.MaterialEditingLibrary.connect_material_property(
        roughness, "", unreal.MaterialProperty.MP_ROUGHNESS
    )
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)
    return material


def create_ecy_pbr_material(asset_name, texture_path, masked, roughness_value, specular_value):
    path = f"{GENERATED_ROOT}/{asset_name}"
    material = unreal.load_asset(path)
    if material:
        return material

    texture = unreal.load_asset(texture_path)
    if not texture:
        raise RuntimeError(f"Could not load Ecy texture: {texture_path}")
    texture.set_editor_property("srgb", True)
    unreal.EditorAssetLibrary.save_loaded_asset(texture, only_if_is_dirty=False)

    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name,
        GENERATED_ROOT,
        unreal.Material,
        unreal.MaterialFactoryNew(),
    )
    if not material:
        raise RuntimeError(f"Could not create Ecy PBR material: {path}")

    material.set_editor_property("two_sided", masked)
    material.set_editor_property(
        "blend_mode",
        unreal.BlendMode.BLEND_MASKED if masked else unreal.BlendMode.BLEND_OPAQUE,
    )
    if masked:
        material.set_editor_property("opacity_mask_clip_value", 0.333)

    sample = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionTextureSample, -480, -80
    )
    sample.set_editor_property("texture", texture)
    unreal.MaterialEditingLibrary.connect_material_property(
        sample, "RGB", unreal.MaterialProperty.MP_BASE_COLOR
    )
    if masked:
        unreal.MaterialEditingLibrary.connect_material_property(
            sample, "A", unreal.MaterialProperty.MP_OPACITY_MASK
        )

    constants = (
        (unreal.MaterialProperty.MP_METALLIC, 0.0, -220, 70),
        (unreal.MaterialProperty.MP_SPECULAR, specular_value, -220, 140),
        (unreal.MaterialProperty.MP_ROUGHNESS, roughness_value, -220, 210),
        (unreal.MaterialProperty.MP_AMBIENT_OCCLUSION, 1.0, -220, 280),
    )
    for prop, value, x, y in constants:
        expression = unreal.MaterialEditingLibrary.create_material_expression(
            material, unreal.MaterialExpressionConstant, x, y
        )
        expression.set_editor_property("r", value)
        unreal.MaterialEditingLibrary.connect_material_property(expression, "", prop)

    # Deliberately leave Emissive unconnected. Ecy must react to scene light like
    # cloth and skin instead of behaving as an unlit billboard.
    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)
    return material


def import_textures(source_dir, destination_path):
    tasks = []
    for filename in sorted(os.listdir(source_dir)):
        if not filename.lower().endswith(".png") or filename.startswith("Viewer Node"):
            continue
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", os.path.join(source_dir, filename))
        task.set_editor_property("destination_path", destination_path)
        task.set_editor_property("destination_name", f"T_{os.path.splitext(filename)[0]}")
        task.set_editor_property("automated", True)
        task.set_editor_property("save", True)
        task.set_editor_property("replace_existing", True)
        tasks.append(task)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)


def create_textured_material(asset_name, texture_path, masked=False, color=None, unlit=False):
    path = f"{GENERATED_ROOT}/{asset_name}"
    material = unreal.load_asset(path)
    if material:
        return material
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name,
        GENERATED_ROOT,
        unreal.Material,
        unreal.MaterialFactoryNew(),
    )
    texture = unreal.load_asset(texture_path) if texture_path else None
    if not material or (texture_path and not texture):
        raise RuntimeError(f"Could not create material {path} from {texture_path}")

    material.set_editor_property("two_sided", True)
    material.set_editor_property(
        "blend_mode",
        unreal.BlendMode.BLEND_MASKED if masked else unreal.BlendMode.BLEND_OPAQUE,
    )

    if texture:
        sample = unreal.MaterialEditingLibrary.create_material_expression(
            material, unreal.MaterialExpressionTextureSample, -420, -40
        )
        sample.set_editor_property("texture", texture)
        if unlit:
            unreal.MaterialEditingLibrary.connect_material_property(
                sample, "RGB", unreal.MaterialProperty.MP_BASE_COLOR
            )
            unreal.MaterialEditingLibrary.connect_material_property(
                sample, "RGB", unreal.MaterialProperty.MP_EMISSIVE_COLOR
            )
        else:
            unreal.MaterialEditingLibrary.connect_material_property(
                sample, "RGB", unreal.MaterialProperty.MP_BASE_COLOR
            )
            emissive_strength = unreal.MaterialEditingLibrary.create_material_expression(
                material, unreal.MaterialExpressionConstant, -420, 150
            )
            emissive_strength.set_editor_property("r", 0.28)
            emissive = unreal.MaterialEditingLibrary.create_material_expression(
                material, unreal.MaterialExpressionMultiply, -180, 40
            )
            unreal.MaterialEditingLibrary.connect_material_expressions(
                sample, "RGB", emissive, "A"
            )
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
    else:
        vector = unreal.MaterialEditingLibrary.create_material_expression(
            material, unreal.MaterialExpressionConstant3Vector, -420, -40
        )
        vector.set_editor_property("constant", unreal.LinearColor(*color))
        unreal.MaterialEditingLibrary.connect_material_property(
            vector,
            "",
            unreal.MaterialProperty.MP_EMISSIVE_COLOR
            if unlit
            else unreal.MaterialProperty.MP_BASE_COLOR,
        )

    roughness = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, -220, 180
    )
    roughness.set_editor_property("r", 0.62)
    unreal.MaterialEditingLibrary.connect_material_property(
        roughness, "", unreal.MaterialProperty.MP_ROUGHNESS
    )

    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)
    return material


def assign_materials(mesh_path, prefix, resolver):
    mesh = unreal.load_asset(mesh_path)
    if not mesh:
        raise RuntimeError(f"Missing skeletal mesh: {mesh_path}")
    materials = list(mesh.get_editor_property("materials"))
    for index, slot in enumerate(materials):
        slot_name = str(slot.get_editor_property("material_slot_name"))
        if prefix == "Ecy" and slot_name.lower() == "line":
            material = create_hidden_outline_material()
            slot.set_editor_property("material_interface", material)
            print(
                f"[AocietyMaterialRepair] mesh={mesh_path} slot={slot_name} "
                f"material={material.get_path_name()} reason=hide_inverted_outline_shell"
            )
            continue
        texture_path, masked, color = resolver(slot_name)
        safe_slot = "".join(ch if ch.isalnum() else "_" for ch in slot_name)
        if prefix == "Ecy":
            name = slot_name.lower()
            if "cloth" in name:
                roughness, specular = 0.84, 0.24
            elif "body" in name or "face" in name:
                roughness, specular = 0.72, 0.32
            elif "hair" in name:
                roughness, specular = 0.60, 0.34
            elif "eye" in name:
                roughness, specular = 0.42, 0.42
            else:
                roughness, specular = 0.75, 0.28
            material = create_ecy_pbr_material(
                f"M_EcyPBR_v4_{index:02d}_{safe_slot}",
                texture_path,
                masked,
                roughness,
                specular,
            )
        else:
            material = create_textured_material(
                f"MF2_{prefix}_{index:02d}_{safe_slot}",
                texture_path,
                masked,
                color,
                unlit=False,
            )
        slot.set_editor_property("material_interface", material)
        print(
            f"[AocietyMaterialRepair] mesh={mesh_path} slot={slot_name} material={material.get_path_name()}"
        )
    mesh.set_editor_property("materials", materials)
    unreal.EditorAssetLibrary.save_loaded_asset(mesh, only_if_is_dirty=False)


ECY_ROOT = "/Game/Aociety/Characters/Ecy"


def resolve_ecy(slot):
    name = slot.lower()
    if "cloth" in name:
        return f"{ECY_ROOT}/cloth_Base_color", False, None
    if "eye" in name:
        return f"{ECY_ROOT}/eye_Base_color", False, None
    if "hair" in name:
        return f"{ECY_ROOT}/hair_Base_color", True, None
    if "face" in name:
        return f"{ECY_ROOT}/face_Base_color", "005" in name, None
    if "body" in name:
        return f"{ECY_ROOT}/body_Base_color", False, None
    return None, False, (0.015, 0.02, 0.03, 1.0)


assign_materials(f"{ECY_ROOT}/SK_Ecy", "Ecy", resolve_ecy)

VARIANTS = (
    (
        "AliciaSolid",
        r"E:\Aociety-NEW\SourceAssets\Characters\NPC_Cute\Export\AliciaSolid\Textures",
    ),
    (
        "AliciaSakura",
        r"E:\Aociety-NEW\SourceAssets\Characters\NPC_Cute\Export\AliciaSakura\Textures",
    ),
)

for variant, source_dir in VARIANTS:
    root = f"/Game/Aociety/Characters/NPC_Cute/{variant}"
    import_textures(source_dir, root)

    def resolve_alicia(slot, root=root):
        name = slot.lower()
        if "hair" in name:
            texture = "Alicia_hair"
        elif "wear" in name:
            texture = "Alicia_wear"
        elif "eye" in name:
            texture = "Alicia_eye"
        elif "face" in name or "mastuge" in name:
            texture = "Alicia_face"
        elif "other" in name:
            texture = "Alicia_other"
        else:
            texture = "Alicia_body"
        masked = any(token in name for token in ("hair", "wear", "mastuge", "trans"))
        return f"{root}/T_{texture}", masked, None

    assign_materials(f"{root}/SK_{variant}", variant, resolve_alicia)

unreal.EditorAssetLibrary.save_directory(
    "/Game/Aociety/Characters", only_if_is_dirty=False, recursive=True
)
print("[AocietyMaterialRepair] complete Ecy=colored NPCs=colored")
