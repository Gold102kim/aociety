import unreal


for path in (
    "/Game/Aociety/Characters/Ecy/SK_Ecy",
    "/Game/Aociety/Characters/NPC_Cute/AliciaSolid/SK_AliciaSolid",
    "/Game/Aociety/Characters/NPC_Cute/AliciaSakura/SK_AliciaSakura",
):
    mesh = unreal.load_asset(path)
    print(f"[AocietyMaterialSlots] mesh={path}")
    for index, slot in enumerate(mesh.get_editor_property("materials")):
        material = slot.get_editor_property("material_interface")
        slot_name = slot.get_editor_property("material_slot_name")
        print(
            "[AocietyMaterialSlots] index=%d slot=%s material=%s class=%s"
            % (
                index,
                slot_name,
                material.get_path_name() if material else "None",
                material.get_class().get_name() if material else "None",
            )
        )
