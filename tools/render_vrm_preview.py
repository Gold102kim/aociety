from pathlib import Path
import math
import sys

import bpy
from mathutils import Vector


if "--" not in sys.argv or len(sys.argv) < sys.argv.index("--") + 3:
    raise RuntimeError("Usage: blender -b --python script.py -- input.vrm output.png")

separator = sys.argv.index("--")
input_path = Path(sys.argv[separator + 1]).resolve()
output_path = Path(sys.argv[separator + 2]).resolve()
output_path.parent.mkdir(parents=True, exist_ok=True)

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(input_path), import_pack_images=True)

mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
if not mesh_objects:
    raise RuntimeError("No mesh imported")

world_points = [obj.matrix_world @ Vector(corner) for obj in mesh_objects for corner in obj.bound_box]
minimum = Vector((min(p.x for p in world_points), min(p.y for p in world_points), min(p.z for p in world_points)))
maximum = Vector((max(p.x for p in world_points), max(p.y for p in world_points), max(p.z for p in world_points)))
center = (minimum + maximum) * 0.5
height = max(0.1, maximum.z - minimum.z)

floor_size = height * 2.5
bpy.ops.mesh.primitive_plane_add(size=floor_size, location=(center.x, center.y, minimum.z))
floor = bpy.context.object
floor_material = bpy.data.materials.new("PreviewFloor")
floor_material.diffuse_color = (0.16, 0.22, 0.17, 1.0)
floor.data.materials.append(floor_material)

bpy.ops.object.camera_add(location=(center.x, center.y + height * 2.15, center.z + height * 0.05))
camera = bpy.context.object
camera.data.lens = 58
camera.rotation_euler = ((center - camera.location).to_track_quat("-Z", "Y")).to_euler()
bpy.context.scene.camera = camera

def add_area(name, location, energy, size, color):
    data = bpy.data.lights.new(name=name, type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = color
    light = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(light)
    light.location = location
    light.rotation_euler = ((center - light.location).to_track_quat("-Z", "Y")).to_euler()


add_area("Key", (center.x - height, center.y + height, center.z + height), 950, height, (1.0, 0.86, 0.72))
add_area("Fill", (center.x + height, center.y + height * 0.4, center.z + height * 0.4), 650, height, (0.64, 0.78, 1.0))
add_area("Rim", (center.x, center.y - height, center.z + height), 900, height * 0.7, (0.8, 0.9, 1.0))

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 512
scene.render.resolution_y = 768
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = str(output_path)
scene.render.film_transparent = False
scene.world.color = (0.025, 0.04, 0.06)
scene.view_settings.look = "AgX - Medium High Contrast"
bpy.ops.render.render(write_still=True)
print(f"[AocietyVRMPreview] {output_path}")
