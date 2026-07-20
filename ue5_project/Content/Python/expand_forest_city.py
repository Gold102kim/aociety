import math

import unreal


TARGET_MAP = "/Game/Aociety/Maps/Aociety_ForestSnowTown"
SOURCE_CITY_MAP = "/Game/Modular_Rural_Cabin/Maps/Rural_Cabins"
PREFIX = "Aociety_Expansion_"
CITY_PLACEMENTS = (
    (unreal.Vector(6500.0, -350.0, 35.0), 0.0),
    (unreal.Vector(9000.0, 1850.0, 35.0), 110.0),
)
COLLISION_TILE_SIZE = 3200.0
COLLISION_TILE_OVERLAP = 200.0
COLLISION_MARGIN = 400.0
COLLISION_TOP_Z = -25.0
COLLISION_THICKNESS = 40.0


def asset(path):
    value = unreal.load_asset(path)
    if not value:
        raise RuntimeError(f"Missing asset: {path}")
    return value


def optional_asset(path):
    return unreal.load_asset(path)


def actor_mesh_component(actor):
    return actor.get_component_by_class(unreal.StaticMeshComponent)


def snapshot_static_mesh_actors(level_subsystem, actor_subsystem):
    if not level_subsystem.load_level(SOURCE_CITY_MAP):
        raise RuntimeError(f"Could not load {SOURCE_CITY_MAP}")
    rows = []
    for actor in actor_subsystem.get_all_level_actors():
        component = actor_mesh_component(actor)
        mesh = component.static_mesh if component else None
        if not mesh:
            continue
        mesh_path = mesh.get_path_name()
        origin, extent = actor.get_actor_bounds(False, False)
        if (
            abs(origin.x) > 5000.0
            or abs(origin.y) > 5000.0
            or extent.x > 5000.0
            or extent.y > 5000.0
            or extent.z > 5000.0
        ):
            continue
        if not any(
            folder in mesh_path
            for folder in ("/Meshes/Modular/", "/Meshes/Unique/", "/Meshes/Props/")
        ):
            continue
        location = actor.get_actor_location()
        rotation = actor.get_actor_rotation()
        scale = actor.get_actor_scale3d()
        rows.append(
            {
                "label": actor.get_actor_label(),
                "mesh": mesh,
                "materials": [
                    material for material in component.get_materials() if material
                ],
                "location": location,
                "rotation": rotation,
                "scale": scale,
            }
        )
    return rows


def spawn_static_mesh(
    actor_subsystem,
    mesh,
    location,
    rotation,
    scale,
    label,
    materials=None,
    collision_profile=None,
    hidden_in_game=False,
):
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.StaticMeshActor,
        location,
        rotation,
    )
    if not actor:
        return None
    actor.set_actor_label(label)
    actor.set_actor_scale3d(scale)
    component = actor.get_component_by_class(unreal.StaticMeshComponent)
    component.set_static_mesh(mesh)
    if materials:
        for material_index, material in enumerate(materials):
            component.set_material(material_index, material)
    if collision_profile:
        component.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
        component.set_collision_response_to_all_channels(
            unreal.CollisionResponseType.ECR_BLOCK
        )
        component.set_collision_profile_name(collision_profile)
        component.set_editor_property(
            "can_character_step_up_on", unreal.CanBeCharacterBase.ECB_YES
        )
        try:
            component.set_editor_property("generate_overlap_events", False)
        except Exception:
            pass
    if hidden_in_game:
        component.set_editor_property("visible", False)
        component.set_editor_property("hidden_in_game", True)
        component.set_cast_shadow(False)
    try:
        component.set_editor_property("mobility", unreal.ComponentMobility.STATIC)
    except Exception:
        pass
    return actor


def expansion_xy_bounds(actor_subsystem):
    min_x = float("inf")
    min_y = float("inf")
    max_x = float("-inf")
    max_y = float("-inf")
    found = False

    for actor in actor_subsystem.get_all_level_actors():
        label = actor.get_actor_label()
        if not label.startswith(PREFIX) or "Collision" in label:
            continue
        component = actor_mesh_component(actor)
        if not component or not component.static_mesh:
            continue
        origin, extent = actor.get_actor_bounds(False, False)
        if extent.x <= 0.0 or extent.y <= 0.0:
            continue
        min_x = min(min_x, origin.x - extent.x)
        min_y = min(min_y, origin.y - extent.y)
        max_x = max(max_x, origin.x + extent.x)
        max_y = max(max_y, origin.y + extent.y)
        found = True

    if not found:
        raise RuntimeError("Could not determine expansion bounds")

    return (
        min_x - COLLISION_MARGIN,
        min_y - COLLISION_MARGIN,
        max_x + COLLISION_MARGIN,
        max_y + COLLISION_MARGIN,
    )


def spawn_collision_grid(actor_subsystem, collision_mesh):
    min_x, min_y, max_x, max_y = expansion_xy_bounds(actor_subsystem)
    step = COLLISION_TILE_SIZE - COLLISION_TILE_OVERLAP
    start_x = math.floor(min_x / step) * step
    start_y = math.floor(min_y / step) * step
    z = COLLISION_TOP_Z - COLLISION_THICKNESS * 0.5
    scale = unreal.Vector(
        COLLISION_TILE_SIZE / 100.0,
        COLLISION_TILE_SIZE / 100.0,
        COLLISION_THICKNESS / 100.0,
    )

    created = 0
    x_index = 0
    x = start_x
    while x < max_x:
        y_index = 0
        y = start_y
        while y < max_y:
            if spawn_static_mesh(
                actor_subsystem,
                collision_mesh,
                unreal.Vector(
                    x + COLLISION_TILE_SIZE * 0.5,
                    y + COLLISION_TILE_SIZE * 0.5,
                    z,
                ),
                unreal.Rotator(),
                scale,
                f"{PREFIX}CollisionTile_{x_index:02d}_{y_index:02d}",
                collision_profile="BlockAll",
                hidden_in_game=True,
            ):
                created += 1
            y += step
            y_index += 1
        x += step
        x_index += 1

    print(
        "[AocietyExpansion] collision_tiles=%d bounds=(%.1f, %.1f)-(%.1f, %.1f) top_z=%.1f"
        % (created, min_x, min_y, max_x, max_y, COLLISION_TOP_Z)
    )
    return created


def spawn_city(actor_subsystem, rows):
    created = 0
    for district_index, (offset, district_yaw) in enumerate(CITY_PLACEMENTS):
        angle = math.radians(district_yaw)
        cos_angle = math.cos(angle)
        sin_angle = math.sin(angle)
        for index, row in enumerate(rows):
            source_location = row["location"]
            location = unreal.Vector(
                source_location.x * cos_angle - source_location.y * sin_angle
                + offset.x,
                source_location.x * sin_angle + source_location.y * cos_angle
                + offset.y,
                source_location.z + offset.z,
            )
            source_rotation = row["rotation"]
            rotation = unreal.Rotator(
                source_rotation.pitch,
                source_rotation.yaw + district_yaw,
                source_rotation.roll,
            )
            label = (
                f"{PREFIX}City_{district_index:02d}_{index:03d}_{row['label']}"
            )
            if spawn_static_mesh(
                actor_subsystem,
                row["mesh"],
                location,
                rotation,
                row["scale"],
                label,
                row["materials"],
            ):
                created += 1
    return created


def spawn_light(actor_subsystem, location, label, intensity=950.0):
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.PointLight,
        unreal.Vector(*location),
        unreal.Rotator(),
    )
    if not actor:
        return None
    actor.set_actor_label(label)
    component = actor.get_component_by_class(unreal.PointLightComponent)
    component.set_editor_property("intensity", intensity)
    component.set_editor_property("attenuation_radius", 850.0)
    component.set_editor_property("source_radius", 15.0)
    component.set_editor_property("soft_source_radius", 60.0)
    component.set_light_color(unreal.LinearColor(1.0, 0.55, 0.28, 1.0), True)
    return actor


def spawn_decal(actor_subsystem, material, start, end, width, index):
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    midpoint = unreal.Vector(
        (start[0] + end[0]) * 0.5,
        (start[1] + end[1]) * 0.5,
        (start[2] + end[2]) * 0.5 + 30.0,
    )
    yaw = math.degrees(math.atan2(dy, dx))
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.DecalActor,
        midpoint,
        unreal.Rotator(pitch=-90.0, yaw=yaw, roll=0.0),
    )
    if not actor:
        return None
    actor.set_actor_label(f"{PREFIX}Path_{index:02d}")
    component = actor.get_component_by_class(unreal.DecalComponent)
    component.set_decal_material(material)
    component.set_editor_property(
        "decal_size", unreal.Vector(180.0, width * 0.5, length * 0.5)
    )
    component.set_editor_property("sort_order", 5)
    return actor


def spawn_npc(actor_subsystem, npc_class, mesh, idle, walk, location, npc_id, name):
    actor = actor_subsystem.spawn_actor_from_class(
        npc_class,
        unreal.Vector(*location),
        unreal.Rotator(0.0, 180.0, 0.0),
    )
    if not actor:
        return None
    actor.set_actor_label(f"{PREFIX}{npc_id}_{name}")
    actor.set_editor_property("NpcId", npc_id)
    actor.set_editor_property("DisplayName", name)
    actor.set_editor_property("WanderRadius", 620.0)
    actor.set_editor_property("WanderSpeed", 105.0)
    actor.set_editor_property("bEnableWander", True)
    actor.set_editor_property("IdleAnimation", idle)
    actor.set_editor_property("WalkAnimation", walk)
    actor.set_editor_property(
        "tags", [unreal.Name("AocietyResident"), unreal.Name(npc_id)]
    )
    for component in actor.get_components_by_class(unreal.SkeletalMeshComponent):
        component.set_skeletal_mesh(mesh)
        component.set_editor_property("visible", True)
        component.set_editor_property("hidden_in_game", False)
        component.set_receives_decals(False)
    return actor


def spawn_npc_trigger(actor_subsystem, location, npc_id, index):
    trigger = actor_subsystem.spawn_actor_from_class(
        unreal.TriggerBox,
        unreal.Vector(*location),
        unreal.Rotator(),
    )
    if not trigger:
        return None
    trigger.set_actor_label(f"{PREFIX}NPC_Trigger_{index:02d}_{npc_id}")
    trigger.set_actor_scale3d(unreal.Vector(4.0, 4.0, 2.0))
    trigger.set_editor_property(
        "tags", [unreal.Name("AocietyDialogueTrigger"), unreal.Name(npc_id)]
    )
    return trigger


level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
city_rows = snapshot_static_mesh_actors(level_subsystem, actor_subsystem)

if not level_subsystem.load_level(TARGET_MAP):
    raise RuntimeError(f"Could not load {TARGET_MAP}")

old_generated = [
    actor
    for actor in actor_subsystem.get_all_level_actors()
    if actor.get_actor_label().startswith(PREFIX)
]
if old_generated:
    actor_subsystem.destroy_actors(old_generated)

city_count = spawn_city(actor_subsystem, city_rows)

leaf_ground = asset("/Game/MagicTown/PolyHaven/LeavesForestGround/M_PH_LeavesForestGround")
forest_ground_mesh = asset("/Game/MagicTown/HighPolyMeshes/SM_HP_WarmPackedEarthBase")
island_tree = asset(
    "/Game/MagicTown/PolyHaven/IslandTree01/island_tree_01_4k/StaticMeshes/island_tree_01_4k"
)
flower_patch = asset("/Game/Modular_Rural_Cabin/Meshes/Foliage/Flower_Patch_1")
grass_patch = asset("/Game/Modular_Rural_Cabin/Meshes/Foliage/Grass_Patch_2")
bush_tree = asset("/Game/Modular_Rural_Cabin/Meshes/Foliage/Bush_Tree")
rock = asset("/Game/Modular_Rural_Cabin/Meshes/Props/Rock_1")
river_stones = optional_asset("/Game/Modular_Rural_Cabin/Meshes/Props/River_Stone_Set_1")
ophiopogon = asset(
    "/Game/Ophiopogon_japonicus_Nanite_Free/Geometries/SM_Free_Ophiopogon_japonicus_3DGardenPlants"
)

forest_centers = (
    (2800.0, -2450.0, 55.0),
    (3600.0, -1150.0, 55.0),
    (3900.0, 1700.0, 55.0),
    (2750.0, 3250.0, 55.0),
    (850.0, 4200.0, 45.0),
    (-1300.0, 4600.0, 45.0),
    (-3200.0, 3100.0, 45.0),
    (-3900.0, 900.0, 45.0),
    (-3450.0, -2350.0, 45.0),
)

forest_count = 0
flower_count = 0
grass_count = 0
rock_count = 0
for center_index, (cx, cy, cz) in enumerate(forest_centers):
    spawn_static_mesh(
        actor_subsystem,
        forest_ground_mesh,
        unreal.Vector(cx, cy, cz - 35.0),
        unreal.Rotator(),
        unreal.Vector(1.0, 1.0, 1.0),
        f"{PREFIX}ForestGround_{center_index:02d}",
        [leaf_ground],
    )
    for tree_index, (dx, dy, scale) in enumerate(
        ((-480.0, -300.0, 0.86), (360.0, -210.0, 1.0), (70.0, 420.0, 0.92))
    ):
        spawn_static_mesh(
            actor_subsystem,
            island_tree,
            unreal.Vector(cx + dx, cy + dy, cz),
            unreal.Rotator(0.0, (center_index * 47 + tree_index * 71) % 360, 0.0),
            unreal.Vector(scale, scale, scale),
            f"{PREFIX}AutumnTree_{center_index:02d}_{tree_index:02d}",
        )
        forest_count += 1
    for flower_index, (dx, dy) in enumerate(
        ((-420.0, -120.0), (-180.0, 260.0), (120.0, -310.0), (390.0, 150.0))
    ):
        spawn_static_mesh(
            actor_subsystem,
            flower_patch,
            unreal.Vector(cx + dx, cy + dy, cz + 8.0),
            unreal.Rotator(0.0, (flower_index * 83) % 360, 0.0),
            unreal.Vector(1.4, 1.4, 1.4),
            f"{PREFIX}FlowerPatch_{center_index:02d}_{flower_index:02d}",
        )
        spawn_static_mesh(
            actor_subsystem,
            ophiopogon,
            unreal.Vector(cx + dx + 85.0, cy + dy + 65.0, cz + 5.0),
            unreal.Rotator(0.0, (flower_index * 41) % 360, 0.0),
            unreal.Vector(0.55, 0.55, 0.55),
            f"{PREFIX}Ophiopogon_{center_index:02d}_{flower_index:02d}",
        )
        flower_count += 1
    for grass_index, (dx, dy) in enumerate(((-260.0, -440.0), (280.0, 380.0))):
        spawn_static_mesh(
            actor_subsystem,
            grass_patch,
            unreal.Vector(cx + dx, cy + dy, cz + 6.0),
            unreal.Rotator(0.0, (grass_index * 123) % 360, 0.0),
            unreal.Vector(1.5, 1.5, 1.5),
            f"{PREFIX}Grass_{center_index:02d}_{grass_index:02d}",
        )
        grass_count += 1
    for rock_index, (dx, dy, scale) in enumerate(((-560.0, 120.0, 1.4), (520.0, -90.0, 1.0))):
        mesh = river_stones if river_stones and rock_index == 1 else rock
        spawn_static_mesh(
            actor_subsystem,
            mesh,
            unreal.Vector(cx + dx, cy + dy, cz - 5.0),
            unreal.Rotator(0.0, (center_index * 23 + rock_index * 51) % 360, 0.0),
            unreal.Vector(scale, scale, scale),
            f"{PREFIX}Rock_{center_index:02d}_{rock_index:02d}",
        )
        rock_count += 1
    spawn_static_mesh(
        actor_subsystem,
        bush_tree,
        unreal.Vector(cx - 70.0, cy - 520.0, cz + 3.0),
        unreal.Rotator(0.0, center_index * 37, 0.0),
        unreal.Vector(1.2, 1.2, 1.2),
        f"{PREFIX}Bush_{center_index:02d}",
    )

dirt_track = asset("/Game/Modular_Rural_Cabin/Materials/Decals/Dirt_Track_2")
spawn_decal(actor_subsystem, dirt_track, (-650.0, 700.0, 115.0), (4700.0, -200.0, 70.0), 600.0, 0)
spawn_decal(actor_subsystem, dirt_track, (4700.0, -200.0, 70.0), (6500.0, -350.0, 70.0), 600.0, 1)

# Keep the entire generated play space grounded even where decorative terrain
# meshes have gaps or no simple collision. Multiple overlapping BlockAll tiles
# are derived from the generated actor bounds, so later city expansion cannot
# silently grow past a single fixed slab.
collision_floor = asset("/Engine/BasicShapes/Cube.Cube")
collision_count = spawn_collision_grid(actor_subsystem, collision_floor)

npc_class = unreal.load_class(None, "/Script/Aociety.AocietyNPCCharacter")
ecy_mesh = asset("/Game/Aociety/Characters/Ecy/SK_Ecy")
ecy_idle = asset("/Game/Aociety/Characters/Ecy/Animations/A_Ecy_Idle")
ecy_walk = asset("/Game/Aociety/Characters/Ecy/Animations/A_Ecy_Walk")
if npc_class:
    for index, (npc_id, name, location) in enumerate(
        (
            ("npc_03", "芽衣", (6000.0, -470.0, 115.0)),
            ("npc_04", "诺安", (6900.0, 240.0, 115.0)),
        )
    ):
        if spawn_npc(
            actor_subsystem,
            npc_class,
            ecy_mesh,
            ecy_idle,
            ecy_walk,
            location,
            npc_id,
            name,
        ):
            spawn_npc_trigger(actor_subsystem, location, npc_id, index)

level_subsystem.save_current_level()
print(
    "[AocietyExpansion] city=%d forest_trees=%d flowers=%d grass=%d rocks=%d collision=%d"
    % (
        city_count,
        forest_count,
        flower_count,
        grass_count,
        rock_count,
        collision_count,
    )
)
