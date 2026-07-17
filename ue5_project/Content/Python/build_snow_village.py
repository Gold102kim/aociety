import unreal

LOG = "[AocietySnow]"

def make_snow_material():
    path = "/Game/MagicTown/Materials/M_Aociety_Snow"
    existing = unreal.load_asset(path)
    if existing:
        return existing
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    mat = tools.create_asset("M_Aociety_Snow", "/Game/MagicTown/Materials", unreal.Material, unreal.MaterialFactoryNew())
    if not mat:
        return None
    color = unreal.MaterialEditingLibrary.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -300, 0)
    color.constant = unreal.LinearColor(0.82, 0.90, 1.0, 1.0)
    rough = unreal.MaterialEditingLibrary.create_material_expression(mat, unreal.MaterialExpressionConstant, -300, 180)
    rough.r = 0.88
    unreal.MaterialEditingLibrary.connect_material_property(color, "", unreal.MaterialProperty.MP_BASE_COLOR)
    unreal.MaterialEditingLibrary.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    unreal.MaterialEditingLibrary.recompile_material(mat)
    mat.set_editor_property("two_sided", False)
    unreal.EditorAssetLibrary.save_asset(path)
    return mat

def add_light(world, loc, color, intensity, radius, label):
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.PointLight, unreal.Vector(*loc), unreal.Rotator(0, 0, 0))
    if actor:
        actor.set_actor_label(label)
        comp = actor.get_component_by_class(unreal.PointLightComponent)
        comp.set_editor_property("intensity", intensity)
        comp.set_light_color(color, True)
        comp.set_editor_property("attenuation_radius", radius)
    return actor

world = unreal.EditorLevelLibrary.get_editor_world()
snow = make_snow_material()
snow_count = 0
if snow:
    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        name = actor.get_name().lower()
        comp = actor.get_component_by_class(unreal.StaticMeshComponent)
        if not comp or not comp.static_mesh:
            continue
        mesh_name = comp.static_mesh.get_name().lower()
        if any(k in (name + " " + mesh_name) for k in ("ground", "terrain", "cobble", "roof", "slate", "street")):
            for i in range(comp.get_num_materials()):
                comp.set_material(i, snow)
            snow_count += 1

directional = None
for actor in unreal.EditorLevelLibrary.get_all_level_actors():
    if actor.get_class().get_name() == "DirectionalLight":
        directional = actor
        break
if directional:
    directional.set_actor_rotation(unreal.Rotator(-48, -35, 0), False)
    comp = directional.get_component_by_class(unreal.DirectionalLightComponent)
    comp.set_editor_property("intensity", 6.0)
    comp.set_light_color(unreal.LinearColor(0.72, 0.84, 1.0, 1.0), True)

for actor in unreal.EditorLevelLibrary.get_all_level_actors():
    if actor.get_actor_label().startswith(("Aociety_WarmLight_", "NPC_DialogueAnchor_", "NS_Aociety_Snowfall")):
        unreal.EditorLevelLibrary.destroy_actor(actor)

for idx, loc in enumerate(((0, 0, 350), (700, 0, 300), (-700, 250, 300), (0, -650, 280))):
    add_light(world, loc, unreal.LinearColor(1.0, 0.55, 0.25, 1.0), 900.0, 900.0, "Aociety_WarmLight_%02d" % idx)

for idx, loc in enumerate(((0, 0, 110), (550, 0, 110), (-500, 250, 110), (0, -550, 110))):
    tp = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.TargetPoint, unreal.Vector(*loc), unreal.Rotator(0, 0, 0))
    if tp:
        tp.set_actor_label("NPC_DialogueAnchor_%02d" % idx)

snow_system = unreal.load_asset("/Niagara/DefaultAssets/Templates/Systems/FountainLightweight")
if snow_system:
    snow_actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.NiagaraActor, unreal.Vector(0, 0, 1800), unreal.Rotator(180, 0, 0))
    if snow_actor:
        snow_actor.set_actor_label("NS_Aociety_Snowfall_Niagara")
        snow_actor.set_actor_scale3d(unreal.Vector(8, 8, 8))
        snow_comp = snow_actor.get_component_by_class(unreal.NiagaraComponent)
        snow_comp.set_asset(snow_system)
        snow_comp.activate(True)

unreal.EditorLevelLibrary.save_current_level()
print("%s applied snow material to %d meshes and added NPC anchors" % (LOG, snow_count))
