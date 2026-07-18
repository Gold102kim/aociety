import unreal


MAP_PATH = "/Game/Aociety/Maps/Aociety_ForestSnowTown"
FURNITURE_TOKENS = (
    "armchair",
    "bed",
    "bench",
    "bookcase",
    "cabinet",
    "chair",
    "couch",
    "cupboard",
    "desk",
    "dresser",
    "drawer",
    "fridge",
    "nightstand",
    "ottoman",
    "refrigerator",
    "shelf",
    "sofa",
    "stool",
    "table",
    "vanity",
    "wardrobe",
)


def is_furniture(actor, component):
    mesh = component.static_mesh
    if not mesh:
        return False
    identity = "%s %s" % (
        actor.get_actor_label(),
        mesh.get_path_name(),
    )
    identity = identity.lower()
    return any(token in identity for token in FURNITURE_TOKENS)


level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not level_subsystem.load_level(MAP_PATH):
    raise RuntimeError("Could not load %s" % MAP_PATH)

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = actor_subsystem.get_all_level_actors()

matched_components = 0
changed_components = 0
already_disabled = 0
decal_actors_untouched = 0

for actor in actors:
    if actor.get_class().get_name() == "DecalActor":
        decal_actors_untouched += 1
        continue

    for component in actor.get_components_by_class(unreal.StaticMeshComponent):
        if not is_furniture(actor, component):
            continue

        matched_components += 1
        if not component.get_editor_property("receives_decals"):
            already_disabled += 1
            continue

        actor.modify()
        component.modify()
        component.set_editor_property("receives_decals", False)
        changed_components += 1

if changed_components:
    level_subsystem.save_current_level()

print(
    "[AocietyFurnitureDecals] matched=%d changed=%d already_disabled=%d "
    "decal_actors_untouched=%d"
    % (
        matched_components,
        changed_components,
        already_disabled,
        decal_actors_untouched,
    )
)
