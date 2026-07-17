import math
from pathlib import Path

import unreal


MAP_PATH = "/Game/Aociety/Maps/Aociety_ForestSnowTown"
SNOW_DIR = "/Game/Aociety/Materials/Snow"
SNOW_MATERIAL_PATH = f"{SNOW_DIR}/M_Aociety_Snow_PBR"
SOURCE_TEXTURE_DIR = Path(r"E:\Aociety-NEW\ue5_project\SourceAssets\Snow")
GENERATED_PREFIX = "Aociety_Generated_"


def import_texture(filename, asset_name, compression=None, srgb=True):
    asset_path = f"{SNOW_DIR}/Textures/{asset_name}"
    if not unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", str(SOURCE_TEXTURE_DIR / filename))
        task.set_editor_property("destination_path", f"{SNOW_DIR}/Textures")
        task.set_editor_property("destination_name", asset_name)
        task.set_editor_property("automated", True)
        task.set_editor_property("replace_existing", True)
        task.set_editor_property("save", True)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    texture = unreal.load_asset(asset_path)
    if not texture:
        raise RuntimeError(f"Could not load imported texture {asset_path}")
    texture.set_editor_property("srgb", srgb)
    if compression is not None:
        texture.set_editor_property("compression_settings", compression)
    texture.modify()
    unreal.EditorAssetLibrary.save_asset(asset_path)
    return texture


def create_snow_material():
    unreal.EditorAssetLibrary.make_directory(f"{SNOW_DIR}/Textures")
    base = import_texture("T_Snow_BaseColor.png", "T_Snow_BaseColor", srgb=True)
    normal = import_texture(
        "T_Snow_Normal.png",
        "T_Snow_Normal",
        unreal.TextureCompressionSettings.TC_NORMALMAP,
        False,
    )
    roughness = import_texture(
        "T_Snow_Roughness.png",
        "T_Snow_Roughness",
        unreal.TextureCompressionSettings.TC_MASKS,
        False,
    )

    material = unreal.load_asset(SNOW_MATERIAL_PATH)
    if material:
        return material

    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "M_Aociety_Snow_PBR",
        SNOW_DIR,
        unreal.Material,
        unreal.MaterialFactoryNew(),
    )
    if not material:
        raise RuntimeError("Could not create snow material")

    uv = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionTextureCoordinate, -650, 40
    )
    uv.set_editor_property("u_tiling", 3.5)
    uv.set_editor_property("v_tiling", 3.5)

    base_sample = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionTextureSample, -350, -100
    )
    base_sample.set_editor_property("texture", base)
    normal_sample = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionTextureSample, -350, 100
    )
    normal_sample.set_editor_property("texture", normal)
    rough_sample = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionTextureSample, -350, 300
    )
    rough_sample.set_editor_property("texture", roughness)
    specular = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, -300, 480
    )
    specular.set_editor_property("r", 0.28)

    for sample in (base_sample, normal_sample, rough_sample):
        unreal.MaterialEditingLibrary.connect_material_expressions(uv, "", sample, "Coordinates")
    unreal.MaterialEditingLibrary.connect_material_property(
        base_sample, "RGB", unreal.MaterialProperty.MP_BASE_COLOR
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        normal_sample, "RGB", unreal.MaterialProperty.MP_NORMAL
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        rough_sample, "R", unreal.MaterialProperty.MP_ROUGHNESS
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        specular, "", unreal.MaterialProperty.MP_SPECULAR
    )
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_asset(SNOW_MATERIAL_PATH)
    return material


def static_mesh_components(actor):
    return actor.get_components_by_class(unreal.StaticMeshComponent)


def mesh_paths(actor):
    paths = []
    for component in static_mesh_components(actor):
        if component.static_mesh:
            paths.append(component.static_mesh.get_path_name())
    return paths


def distance_2d(location, center):
    return math.hypot(location.x - center[0], location.y - center[1])


def duplicate_cluster(actor_subsystem, actors, center, radius, offset, town_index):
    selected = []
    for actor in actors:
        label = actor.get_actor_label()
        if label.startswith(GENERATED_PREFIX):
            continue
        if distance_2d(actor.get_actor_location(), center) > radius:
            continue
        class_name = actor.get_class().get_name()
        paths = " ".join(mesh_paths(actor))
        is_modular = "/Meshes/Modular/" in paths
        is_prop = "/Meshes/Props/" in paths and not any(
            excluded in paths
            for excluded in ("Power_Pole", "Diorama_", "Wooden_Boat")
        )
        is_decal = class_name == "DecalActor"
        is_local_light = class_name in ("PointLight", "RectLight", "SpotLight")
        if is_modular or is_prop or is_decal or is_local_light:
            selected.append(actor)

    created = []
    for source in selected:
        try:
            source_location = source.get_actor_location()
            location = unreal.Vector(
                source_location.x + offset[0],
                source_location.y + offset[1],
                source_location.z + offset[2],
            )
            actor = actor_subsystem.spawn_actor_from_class(
                source.get_class(), location, source.get_actor_rotation()
            )
            if not actor:
                continue
            actor.set_actor_scale3d(source.get_actor_scale3d())

            source_meshes = static_mesh_components(source)
            target_meshes = static_mesh_components(actor)
            for component_index, source_component in enumerate(source_meshes):
                if component_index >= len(target_meshes):
                    break
                target_component = target_meshes[component_index]
                if source_component.static_mesh:
                    target_component.set_static_mesh(source_component.static_mesh)
                for material_index, material in enumerate(source_component.get_materials()):
                    if material:
                        target_component.set_material(material_index, material)

            source_decal = source.get_component_by_class(unreal.DecalComponent)
            target_decal = actor.get_component_by_class(unreal.DecalComponent)
            if source_decal and target_decal:
                target_decal.set_decal_material(source_decal.get_decal_material())
                target_decal.set_editor_property("decal_size", source_decal.get_editor_property("decal_size"))
                target_decal.set_editor_property("sort_order", source_decal.get_editor_property("sort_order"))

            actor.set_actor_label(
                f"{GENERATED_PREFIX}Town{town_index:02d}_{len(created):03d}_{source.get_actor_label()}"
            )
            created.append(actor)
        except Exception as error:
            unreal.log_warning(f"[AocietyTown] skipped {source.get_actor_label()}: {error}")
    return len(created)


def clear_new_lots(actor_subsystem, actors, centers):
    to_remove = []
    for actor in actors:
        paths = " ".join(mesh_paths(actor))
        if not any(token in paths for token in ("Pine_Tree", "Bush", "Shrubs", "Grass_Patch")):
            continue
        if any(distance_2d(actor.get_actor_location(), center) < 650.0 for center in centers):
            to_remove.append(actor)
    if to_remove:
        actor_subsystem.destroy_actors(to_remove)
    return len(to_remove)


def spawn_warm_light(actor_subsystem, location, index):
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.PointLight, unreal.Vector(*location), unreal.Rotator()
    )
    actor.set_actor_label(f"{GENERATED_PREFIX}WarmLight_{index:02d}")
    component = actor.get_component_by_class(unreal.PointLightComponent)
    component.set_editor_property("intensity", 4200.0)
    component.set_editor_property("attenuation_radius", 1150.0)
    component.set_editor_property("source_radius", 25.0)
    component.set_editor_property("soft_source_radius", 120.0)
    component.set_light_color(unreal.LinearColor(1.0, 0.44, 0.16, 1.0), True)
    return actor


def add_npc_points(actor_subsystem, centers):
    for index, (x, y, z) in enumerate(centers):
        anchor_location = unreal.Vector(x + 260.0, y + 180.0, z + 115.0)
        anchor = actor_subsystem.spawn_actor_from_class(
            unreal.TargetPoint, anchor_location, unreal.Rotator()
        )
        anchor.set_actor_label(f"{GENERATED_PREFIX}NPC_Anchor_{index:02d}")
        anchor.set_editor_property(
            "tags", [unreal.Name("AocietyNPC"), unreal.Name(f"npc_{index + 1:02d}")]
        )

        trigger = actor_subsystem.spawn_actor_from_class(
            unreal.TriggerBox, anchor_location, unreal.Rotator()
        )
        trigger.set_actor_label(f"{GENERATED_PREFIX}NPC_Trigger_{index:02d}")
        trigger.set_actor_scale3d(unreal.Vector(3.0, 3.0, 2.0))
        trigger.set_editor_property(
            "tags", [unreal.Name("AocietyDialogueTrigger"), unreal.Name(f"npc_{index + 1:02d}")]
        )


def add_weather(actor_subsystem):
    system = unreal.load_asset("/Niagara/DefaultAssets/Templates/Systems/FountainLightweight")
    if not system:
        return 0
    positions = ((-900, -600, 1850), (-1200, 2500, 1850), (-1100, -2900, 1850))
    for index, location in enumerate(positions):
        actor = actor_subsystem.spawn_actor_from_class(
            unreal.NiagaraActor, unreal.Vector(*location), unreal.Rotator(180, 0, 0)
        )
        actor.set_actor_label(f"{GENERATED_PREFIX}Snowfall_{index:02d}")
        actor.set_actor_scale3d(unreal.Vector(12.0, 12.0, 12.0))
        component = actor.get_component_by_class(unreal.NiagaraComponent)
        component.set_asset(system)
        component.activate(True)
    return len(positions)


level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not level_subsystem.load_level(MAP_PATH):
    raise RuntimeError(f"Could not load {MAP_PATH}")

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = actor_subsystem.get_all_level_actors()
generated = [actor for actor in actors if actor.get_actor_label().startswith(GENERATED_PREFIX)]
if generated:
    actor_subsystem.destroy_actors(generated)
actors = actor_subsystem.get_all_level_actors()

source_a = (-1000.0, -500.0)
source_b = (850.0, 1000.0)
new_lots = (
    (-2900.0, -650.0, 65.0),
    (-2250.0, 1950.0, -10.0),
    (-550.0, -3000.0, 0.0),
    (-550.0, 3000.0, -10.0),
)
removed_foliage = clear_new_lots(actor_subsystem, actors, new_lots)
actors = actor_subsystem.get_all_level_actors()

duplicated = 0
duplicated += duplicate_cluster(actor_subsystem, actors, source_a, 980.0, (-1900.0, -150.0, -135.0), 2)
duplicated += duplicate_cluster(actor_subsystem, actors, source_a, 980.0, (-1250.0, 2450.0, -210.0), 3)
duplicated += duplicate_cluster(actor_subsystem, actors, source_b, 900.0, (-1400.0, -4000.0, -50.0), 4)
duplicated += duplicate_cluster(actor_subsystem, actors, source_b, 900.0, (-1400.0, 2000.0, -60.0), 5)

snow = create_snow_material()
ground_count = 0
roof_count = 0
tree_count = 0
for actor_index, actor in enumerate(actor_subsystem.get_all_level_actors()):
    for component in static_mesh_components(actor):
        if not component.static_mesh:
            continue
        mesh_path = component.static_mesh.get_path_name()
        material_paths = " ".join(
            material.get_path_name() for material in component.get_materials() if material
        )
        if "Diorama_Ground" in mesh_path:
            for slot in range(component.get_num_materials()):
                component.set_material(slot, snow)
            ground_count += 1
        elif "Roof" in mesh_path or "Roof" in material_paths:
            for slot in range(component.get_num_materials()):
                component.set_material(slot, snow)
            roof_count += 1
        elif "Pine_Tree" in mesh_path and actor_index % 3 == 0 and component.get_num_materials() > 1:
            component.set_material(1, snow)
            tree_count += 1

town_centers = (
    (-1000.0, -500.0, 200.0),
    (850.0, 1000.0, 50.0),
    new_lots[0],
    new_lots[1],
    new_lots[2],
    new_lots[3],
)
for index, (x, y, z) in enumerate(town_centers):
    spawn_warm_light(actor_subsystem, (x, y, z + 360.0), index)

add_npc_points(actor_subsystem, town_centers)
weather_count = add_weather(actor_subsystem)

for actor in actor_subsystem.get_all_level_actors():
    try:
        label = actor.get_actor_label()
        if actor.get_class().get_name() == "DirectionalLight":
            component = actor.get_component_by_class(unreal.DirectionalLightComponent)
            if label == "DirectionalLight":
                actor.set_actor_rotation(unreal.Rotator(-42.0, -28.0, 0.0), False)
                component.set_editor_property("intensity", 4.2)
                component.set_light_color(unreal.LinearColor(0.78, 0.87, 1.0, 1.0), True)
            else:
                component.set_editor_property("intensity", 0.15)
        elif actor.get_class().get_name() == "SkyLight":
            component = actor.get_component_by_class(unreal.SkyLightComponent)
            component.set_editor_property("intensity", 1.4)
        elif actor.get_class().get_name() == "ExponentialHeightFog":
            component = actor.get_component_by_class(unreal.ExponentialHeightFogComponent)
            component.set_editor_property("fog_density", 0.012)
            component.set_editor_property("fog_height_falloff", 0.22)
            component.set_editor_property("enable_volumetric_fog", True)
            component.set_editor_property("volumetric_fog_extinction_scale", 0.65)
    except Exception as error:
        unreal.log_warning(f"[AocietyTown] environment setting skipped for {actor.get_actor_label()}: {error}")

level_subsystem.save_current_level()
try:
    unreal.EditorAssetLibrary.save_directory("/Game/Aociety", only_if_is_dirty=False, recursive=True)
except Exception as error:
    unreal.log_warning(f"[AocietyTown] save_directory skipped: {error}")
print(
    "[AocietyTown] duplicated=%d removed_foliage=%d ground_snow=%d roof_snow=%d tree_snow=%d weather=%d"
    % (duplicated, removed_foliage, ground_count, roof_count, tree_count, weather_count)
)
