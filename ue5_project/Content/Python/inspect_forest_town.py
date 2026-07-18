import unreal


MAP_PATH = "/Game/Aociety/Maps/Aociety_ForestSnowTown"

level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not level_subsystem.load_level(MAP_PATH):
    raise RuntimeError(f"Could not load {MAP_PATH}")

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
interesting = []
for actor in actor_subsystem.get_all_level_actors():
    label = actor.get_actor_label()
    class_name = actor.get_class().get_name()
    if (
        "Light" in class_name
        or "PostProcess" in class_name
        or "Sky" in class_name
        or "Camera" in class_name
        or label.startswith("Aociety_TownRefine_")
        or "PlayerStart" in class_name
    ):
        location = actor.get_actor_location()
        row = {
            "label": label,
            "class": class_name,
            "location": (round(location.x, 1), round(location.y, 1), round(location.z, 1)),
            "rotation": tuple(round(value, 1) for value in (
                actor.get_actor_rotation().pitch,
                actor.get_actor_rotation().yaw,
                actor.get_actor_rotation().roll,
            )),
        }
        light_component = actor.get_component_by_class(unreal.LightComponent)
        if light_component:
            row["intensity"] = light_component.get_editor_property("intensity")
            row["color"] = str(light_component.get_editor_property("light_color"))
        interesting.append(row)

for row in interesting:
    print(f"[AocietyTownInspect] {row}")
print(f"[AocietyTownInspect] count={len(interesting)}")
