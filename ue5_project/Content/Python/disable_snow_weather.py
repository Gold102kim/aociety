import unreal


MAP_PATH = "/Game/Aociety/Maps/Aociety_ForestSnowTown"
SNOW_TOKEN = "/Game/Aociety/Materials/Snow/M_Aociety_Snow_PBR"


level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not level_subsystem.load_level(MAP_PATH):
    raise RuntimeError(f"Could not load {MAP_PATH}")

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = actor_subsystem.get_all_level_actors()
snowfall = [actor for actor in actors if actor.get_actor_label().startswith("Aociety_Generated_Snowfall_")]
if snowfall:
    actor_subsystem.destroy_actors(snowfall)

restored_components = 0
restored_slots = 0
for actor in actor_subsystem.get_all_level_actors():
    for component in actor.get_components_by_class(unreal.StaticMeshComponent):
        mesh = component.static_mesh
        if not mesh:
            continue
        changed = False
        for slot in range(component.get_num_materials()):
            material = component.get_material(slot)
            if not material or SNOW_TOKEN not in material.get_path_name():
                continue
            original = mesh.get_material(slot)
            if original:
                component.set_material(slot, original)
                restored_slots += 1
                changed = True
        if changed:
            restored_components += 1

level_subsystem.save_current_level()
print(
    "[AocietyTown] snow disabled; snowfall_removed=%d restored_components=%d restored_slots=%d"
    % (len(snowfall), restored_components, restored_slots)
)
