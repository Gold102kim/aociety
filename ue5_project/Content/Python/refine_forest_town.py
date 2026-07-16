import math
import unreal


MAP_PATH = "/Game/Aociety/Maps/Aociety_ForestSnowTown"
PREFIX = "Aociety_TownRefine_"
SNOW_TOKEN = "/Game/Aociety/Materials/Snow/M_Aociety_Snow_PBR"


def load(path):
    asset = unreal.load_asset(path)
    if not asset:
        raise RuntimeError(f"Missing asset: {path}")
    return asset


def load_optional(path):
    return unreal.load_asset(path)


def spawn_ground_decal(actor_subsystem, material, start, end, width, index):
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    midpoint = unreal.Vector(
        (start[0] + end[0]) * 0.5,
        (start[1] + end[1]) * 0.5,
        (start[2] + end[2]) * 0.5 + 28.0,
    )
    yaw = math.degrees(math.atan2(dy, dx))
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.DecalActor,
        midpoint,
        unreal.Rotator(pitch=-90.0, yaw=yaw, roll=0.0),
    )
    actor.set_actor_label(f"{PREFIX}Path_{index:02d}")
    component = actor.get_component_by_class(unreal.DecalComponent)
    component.set_decal_material(material)
    component.set_editor_property("decal_size", unreal.Vector(180.0, width * 0.5, length * 0.5))
    component.set_editor_property("sort_order", 4)
    return actor


def spawn_static_mesh(actor_subsystem, mesh, location, rotation, scale, label):
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.StaticMeshActor,
        unreal.Vector(*location),
        unreal.Rotator(pitch=rotation[0], yaw=rotation[1], roll=rotation[2]),
    )
    actor.set_actor_label(label)
    actor.set_actor_scale3d(unreal.Vector(*scale))
    component = actor.get_component_by_class(unreal.StaticMeshComponent)
    component.set_static_mesh(mesh)
    return actor


def restore_default_materials(actor):
    restored = 0
    for component in actor.get_components_by_class(unreal.StaticMeshComponent):
        mesh = component.static_mesh
        if not mesh:
            continue
        for slot in range(component.get_num_materials()):
            material = component.get_material(slot)
            if material and SNOW_TOKEN in material.get_path_name():
                component.set_material(slot, mesh.get_material(slot))
                restored += 1
    return restored


level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not level_subsystem.load_level(MAP_PATH):
    raise RuntimeError(f"Could not load {MAP_PATH}")

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = actor_subsystem.get_all_level_actors()

old_refine = [actor for actor in actors if actor.get_actor_label().startswith(PREFIX)]
if old_refine:
    actor_subsystem.destroy_actors(old_refine)

snowfall = [
    actor for actor in actor_subsystem.get_all_level_actors()
    if actor.get_actor_label().startswith("Aociety_Generated_Snowfall_")
]
if snowfall:
    actor_subsystem.destroy_actors(snowfall)

restored_slots = 0
for actor in actor_subsystem.get_all_level_actors():
    restored_slots += restore_default_materials(actor)

dirt_track = load("/Game/Modular_Rural_Cabin/Materials/Decals/Dirt_Track_2")
forest_ground = load("/Game/Modular_Rural_Cabin/Materials/Decals/Forest_Ground")
road_sign = load("/Game/Modular_Rural_Cabin/Meshes/Props/Road_Sign")
fence_meshes = (
    load("/Game/Modular_Rural_Cabin/Meshes/Props/Fence_Old_1_2m"),
    load("/Game/Modular_Rural_Cabin/Meshes/Props/Fence_Old_2_2m"),
    load("/Game/Modular_Rural_Cabin/Meshes/Props/Fence_Old_3_2m"),
)

town_centers = (
    (-1000.0, -500.0, 200.0),
    (850.0, 1000.0, 50.0),
    (-2900.0, -650.0, 65.0),
    (-2250.0, 1950.0, -10.0),
    (-550.0, -3000.0, 0.0),
    (-550.0, 3000.0, -10.0),
)
plaza = (-650.0, 700.0, 115.0)

path_count = 0
for center in town_centers:
    spawn_ground_decal(actor_subsystem, dirt_track, plaza, center, 520.0, path_count)
    path_count += 1

# A broad village green visually binds the six cabin groups into one town.
for index, angle in enumerate((0.0, 60.0, 120.0)):
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.DecalActor,
        unreal.Vector(plaza[0], plaza[1], plaza[2] + 20.0),
        unreal.Rotator(pitch=-90.0, yaw=angle, roll=0.0),
    )
    actor.set_actor_label(f"{PREFIX}VillageGreen_{index:02d}")
    component = actor.get_component_by_class(unreal.DecalComponent)
    component.set_decal_material(forest_ground)
    component.set_editor_property("decal_size", unreal.Vector(220.0, 780.0, 1100.0))
    component.set_editor_property("sort_order", 2)

for index, center in enumerate(town_centers):
    dx = center[0] - plaza[0]
    dy = center[1] - plaza[1]
    yaw = math.degrees(math.atan2(dy, dx))
    sign_location = (
        plaza[0] + dx * 0.34,
        plaza[1] + dy * 0.34,
        plaza[2] + 45.0,
    )
    spawn_static_mesh(
        actor_subsystem,
        road_sign,
        sign_location,
        (0.0, yaw + 90.0, 0.0),
        (1.0, 1.0, 1.0),
        f"{PREFIX}RoadSign_{index:02d}",
    )

fence_count = 0
for town_index, center in enumerate(town_centers):
    for side_index, offset in enumerate(((-540.0, -520.0), (540.0, -520.0))):
        mesh = fence_meshes[(town_index + side_index) % len(fence_meshes)]
        spawn_static_mesh(
            actor_subsystem,
            mesh,
            (center[0] + offset[0], center[1] + offset[1], center[2] + 35.0),
            (0.0, 0.0, 0.0),
            (1.6, 1.6, 1.6),
            f"{PREFIX}Fence_{fence_count:02d}",
        )
        fence_count += 1

# Keep the town readable rather than crowding it with all 36 backend agents.
# The demo exposes two restrained VRoid-style residents; Manny/Quinn are only
# a safe fallback if character import has not run yet.
anime_resident_meshes = tuple(
    mesh
    for mesh in (
        load_optional("/Game/Aociety/Characters/NPC/AvatarSample_A/SK_AvatarSample_A"),
        load_optional("/Game/Aociety/Characters/NPC/AvatarSample_C/SK_AvatarSample_C"),
    )
    if mesh
)
using_fallback_residents = not anime_resident_meshes
resident_meshes = anime_resident_meshes or (
    load("/Game/Mannequins/Meshes/SKM_Quinn_Simple"),
    load("/Game/Mannequins/Meshes/SKM_Manny_Simple"),
)
idle_animation = (
    load("/Game/Mannequins/Anims/Unarmed/MM_Idle")
    if using_fallback_residents
    else None
)
resident_count = 0
for index, center in enumerate(town_centers[:2]):
    location = unreal.Vector(center[0] + 260.0, center[1] + 180.0, center[2] + 100.0)
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.SkeletalMeshActor,
        location,
        unreal.Rotator(pitch=0.0, yaw=180.0, roll=0.0),
    )
    actor.set_actor_label(f"{PREFIX}Resident_{index:02d}_npc_{index + 1:02d}")
    actor.set_editor_property("tags", [unreal.Name("AocietyResident"), unreal.Name(f"npc_{index + 1:02d}")])
    component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
    component.set_skeletal_mesh(resident_meshes[index % len(resident_meshes)])
    if idle_animation:
        component.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
        component.set_animation(idle_animation)
        component.set_editor_property("play_rate", 1.0)
        component.play(True)
    resident_count += 1

level_subsystem.save_current_level()
unreal.EditorAssetLibrary.save_directory("/Game/Aociety", only_if_is_dirty=False, recursive=True)
print(
    "[AocietyTownRefine] paths=%d fences=%d residents=%d snowfall_removed=%d restored_slots=%d"
    % (path_count, fence_count, resident_count, len(snowfall), restored_slots)
)
