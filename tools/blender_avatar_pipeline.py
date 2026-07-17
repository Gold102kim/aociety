import bpy
import json
import math
import os
import sys
from mathutils import Vector


def arguments():
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    if len(values) != 4:
        raise SystemExit("Expected: <texture_dir> <output_glb> <report_json> <preview_png>")
    return [os.path.abspath(value) for value in values]


def relink_images(texture_dir):
    linked = []
    missing = []
    for image in bpy.data.images:
        if image.source != "FILE":
            continue
        basename = os.path.basename(bpy.path.abspath(image.filepath)) or image.name
        candidate = os.path.join(texture_dir, basename)
        if os.path.exists(candidate):
            image.filepath = candidate
            image.reload()
            linked.append(candidate)
        elif not image.packed_file:
            missing.append(basename)
    return linked, missing


def scene_bounds(meshes):
    points = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
    if not points:
        return Vector((-1, -1, -1)), Vector((1, 1, 1))
    minimum = Vector(min(point[index] for point in points) for index in range(3))
    maximum = Vector(max(point[index] for point in points) for index in range(3))
    return minimum, maximum


def look_at(obj, target):
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def render_preview(output_path, minimum, maximum):
    scene = bpy.context.scene
    center = (minimum + maximum) * 0.5
    size = maximum - minimum
    radius = max(size.length * 0.58, 1.0)

    camera_data = bpy.data.cameras.new("EchoVersePreviewCamera")
    camera = bpy.data.objects.new("EchoVersePreviewCamera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = center + Vector((radius * 1.15, -radius * 2.2, radius * 0.55))
    camera_data.lens = 55
    look_at(camera, center + Vector((0, 0, size.z * 0.05)))
    scene.camera = camera

    for name, energy, location, size_value in [
        ("Key", 1200, center + Vector((radius * 1.5, -radius * 1.2, radius * 1.8)), radius * 1.2),
        ("Fill", 700, center + Vector((-radius * 1.4, -radius * 0.5, radius * 0.8)), radius),
        ("Rim", 900, center + Vector((0, radius * 1.4, radius * 1.5)), radius * 0.8),
    ]:
        light_data = bpy.data.lights.new(f"EchoVerse{name}Light", "AREA")
        light_data.energy = energy
        light_data.shape = "DISK"
        light_data.size = size_value
        light = bpy.data.objects.new(light_data.name, light_data)
        scene.collection.objects.link(light)
        light.location = location
        look_at(light, center)

    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 720
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = True
    scene.render.filepath = output_path
    scene.world.color = (0.008, 0.012, 0.02)
    bpy.ops.render.render(write_still=True)


def main():
    texture_dir, output_glb, report_json, preview_png = arguments()
    for target in (output_glb, report_json, preview_png):
        os.makedirs(os.path.dirname(target), exist_ok=True)

    linked, missing = relink_images(texture_dir)
    scene = bpy.context.scene
    for object_name in ("_gltfNode_243",):
        helper = bpy.data.objects.get(object_name)
        if helper:
            bpy.data.objects.remove(helper, do_unlink=True)
    meshes = [obj for obj in scene.objects if obj.type == "MESH"]
    minimum, maximum = scene_bounds(meshes)

    bpy.ops.export_scene.gltf(
        filepath=output_glb,
        export_format="GLB",
        export_apply=True,
        export_animations=True,
        export_current_frame=True,
        export_rest_position_armature=False,
        export_yup=True,
        export_materials="EXPORT",
        export_image_format="AUTO",
        use_active_scene=True,
    )
    report = {
        "blenderVersion": bpy.app.version_string,
        "scene": scene.name,
        "objects": [
            {
                "name": obj.name,
                "type": obj.type,
                "vertices": len(obj.data.vertices) if obj.type == "MESH" else None,
                "parent": obj.parent.name if obj.parent else None,
            }
            for obj in scene.objects
            if not obj.name.startswith("EchoVerse")
        ],
        "materials": [material.name for material in bpy.data.materials],
        "actions": [
            {"name": action.name, "frameRange": [float(action.frame_range[0]), float(action.frame_range[1])]}
            for action in bpy.data.actions
        ],
        "bounds": {
            "minimum": list(minimum),
            "maximum": list(maximum),
            "size": list(maximum - minimum),
        },
        "linkedTextures": linked,
        "missingTextures": missing,
        "outputGlb": output_glb,
        "previewPng": preview_png,
        "previewRendered": False,
    }
    with open(report_json, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)

    try:
        render_preview(preview_png, minimum, maximum)
        report["previewRendered"] = True
    except Exception as error:
        report["previewError"] = str(error)
    with open(report_json, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)


main()
