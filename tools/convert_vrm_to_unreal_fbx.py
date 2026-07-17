from pathlib import Path
import sys

import bpy


if "--" not in sys.argv or len(sys.argv) < sys.argv.index("--") + 3:
    raise RuntimeError("Usage: blender -b --python script.py -- input.vrm output_dir")

separator = sys.argv.index("--")
input_path = Path(sys.argv[separator + 1]).resolve()
output_dir = Path(sys.argv[separator + 2]).resolve()
texture_dir = output_dir / "Textures"
output_dir.mkdir(parents=True, exist_ok=True)
texture_dir.mkdir(parents=True, exist_ok=True)

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

# VRM 0.x is a GLB container. Blender's glTF importer keeps the humanoid
# skeleton, skin weights, embedded textures, and expression shape keys.
bpy.ops.import_scene.gltf(filepath=str(input_path), import_pack_images=True)

armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
if not armatures or not meshes:
    raise RuntimeError(
        f"VRM import did not create a usable character: armatures={len(armatures)}, meshes={len(meshes)}"
    )

asset_name = input_path.stem
for index, armature in enumerate(armatures):
    armature.name = f"SK_{asset_name}_Armature_{index:02d}"
    armature.data.name = f"SK_{asset_name}_Skeleton_{index:02d}"
for index, mesh in enumerate(meshes):
    mesh.name = f"SK_{asset_name}_Part_{index:02d}"
    mesh.data.name = f"SK_{asset_name}_Part_{index:02d}_Mesh"

for image in bpy.data.images:
    if image.name == "Render Result" or not image.size[0] or not image.size[1]:
        continue
    target = texture_dir / f"{Path(image.name).stem}.png"
    image.filepath_raw = str(target)
    image.file_format = "PNG"
    image.save()

bpy.ops.object.select_all(action="DESELECT")
for obj in [*armatures, *meshes]:
    obj.select_set(True)
bpy.context.view_layer.objects.active = armatures[0]

fbx_path = output_dir / f"SK_{asset_name}.fbx"
bpy.ops.export_scene.fbx(
    filepath=str(fbx_path),
    use_selection=True,
    object_types={"ARMATURE", "MESH"},
    apply_unit_scale=True,
    apply_scale_options="FBX_SCALE_UNITS",
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
    f"[AocietyVRM] exported={fbx_path} armatures={len(armatures)} "
    f"meshes={len(meshes)} materials={len(bpy.data.materials)}"
)
