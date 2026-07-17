import json
from pathlib import Path

import unreal


SOURCE_MAP = "/Game/Modular_Rural_Cabin/Maps/Rural_Cabins"
TARGET_MAP = "/Game/Aociety/Maps/Aociety_ForestSnowTown"
REPORT_PATH = Path(r"E:\Aociety-NEW\ue5_project\Saved\forest_town_actor_report.json")


if not unreal.EditorAssetLibrary.does_asset_exist(TARGET_MAP):
    if not unreal.EditorAssetLibrary.duplicate_asset(SOURCE_MAP, TARGET_MAP):
        raise RuntimeError(f"Could not duplicate {SOURCE_MAP} to {TARGET_MAP}")

level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not level_subsystem.load_level(TARGET_MAP):
    raise RuntimeError(f"Could not load {TARGET_MAP}")

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = actor_subsystem.get_all_level_actors()
report = []
for actor in actors:
    row = {
        "label": actor.get_actor_label(),
        "name": actor.get_name(),
        "class": actor.get_class().get_name(),
        "location": {
            "x": actor.get_actor_location().x,
            "y": actor.get_actor_location().y,
            "z": actor.get_actor_location().z,
        },
    }
    component = actor.get_component_by_class(unreal.StaticMeshComponent)
    if component and component.static_mesh:
        row["mesh"] = component.static_mesh.get_path_name()
        row["materials"] = [
            material.get_path_name() if material else None
            for material in component.get_materials()
        ]
    report.append(row)

REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
level_subsystem.save_current_level()
print(f"[AocietyTown] prepared {TARGET_MAP}; actors={len(report)}; report={REPORT_PATH}")
