from pathlib import Path
import shutil
import sys

import bpy
from mathutils import Matrix


if "--" not in sys.argv:
    raise RuntimeError("Expected output directory after --")

output_dir = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
texture_dir = output_dir / "Textures"
output_dir.mkdir(parents=True, exist_ok=True)
texture_dir.mkdir(parents=True, exist_ok=True)

armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
if len(armatures) != 1:
    raise RuntimeError(f"Expected one armature, found {len(armatures)}")
armature = armatures[0]

skinned_meshes = []
for obj in bpy.data.objects:
    if obj.type != "MESH":
        continue
    if any(mod.type == "ARMATURE" and mod.object == armature for mod in obj.modifiers):
        skinned_meshes.append(obj)

if not skinned_meshes:
    raise RuntimeError("No meshes are skinned to the character armature")

# The source glTF character is authored in metres. Blender's FBX exporter can
# convert mesh vertices for UE while leaving armature translations 100x too
# small, producing a correct-looking reference mesh but exploding skinning as
# soon as an animation rotates a bone. Bake both geometry and rest bones into
# centimetre-sized data, then declare one Blender unit as one centimetre.
centimetre_scale = Matrix.Scale(100.0, 4)
armature.data.transform(centimetre_scale)
for mesh in skinned_meshes:
    mesh.data.transform(centimetre_scale, shape_keys=True)
bpy.context.scene.unit_settings.system = "METRIC"
bpy.context.scene.unit_settings.scale_length = 0.01

armature.name = "SK_Ecy_Armature"
armature.data.name = "SK_Ecy_Skeleton"
for index, mesh in enumerate(skinned_meshes):
    mesh.name = f"SK_Ecy_Part_{index:02d}"
    mesh.data.name = f"SK_Ecy_Part_{index:02d}_Mesh"

for image in bpy.data.images:
    if image.name == "Render Result" or not image.size[0] or not image.size[1]:
        continue
    target = texture_dir / Path(image.name).name
    if image.packed_file:
        image.filepath_raw = str(target)
        image.file_format = "PNG"
        image.save()
    else:
        source = Path(bpy.path.abspath(image.filepath))
        if source.is_file() and source.resolve() != target.resolve():
            shutil.copy2(source, target)

bpy.ops.object.select_all(action="DESELECT")
armature.select_set(True)
for mesh in skinned_meshes:
    mesh.select_set(True)
bpy.context.view_layer.objects.active = armature

fbx_path = output_dir / "SK_Ecy.fbx"
bpy.ops.export_scene.fbx(
    filepath=str(fbx_path),
    use_selection=True,
    object_types={"ARMATURE", "MESH"},
    apply_unit_scale=True,
    apply_scale_options="FBX_SCALE_UNITS",
    global_scale=1.0,
    axis_forward="-Z",
    axis_up="Y",
    use_space_transform=True,
    add_leaf_bones=False,
    use_armature_deform_only=True,
    bake_anim=False,
    path_mode="COPY",
    embed_textures=False,
    use_mesh_modifiers=True,
    mesh_smooth_type="FACE",
)

print(
    f"Exported {fbx_path} with {len(skinned_meshes)} mesh parts and "
    f"{len(armature.data.bones)} deform-capable bones"
)
