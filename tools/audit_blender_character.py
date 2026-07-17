import json
from pathlib import Path
import sys

import bpy


def object_summary(obj):
    data = {
        "name": obj.name,
        "type": obj.type,
        "parent": obj.parent.name if obj.parent else "",
        "dimensions": [round(value, 4) for value in obj.dimensions],
        "modifiers": [modifier.type for modifier in obj.modifiers],
    }
    if obj.type == "MESH":
        data.update(
            vertices=len(obj.data.vertices),
            edges=len(obj.data.edges),
            polygons=len(obj.data.polygons),
            materials=[slot.material.name if slot.material else "" for slot in obj.material_slots],
            vertex_group_count=len(obj.vertex_groups),
            deform_groups=[
                group.name
                for group in obj.vertex_groups
                if group.name.startswith(("sk.", "hair.", "root", "hips", "spine", "chest"))
            ],
            shape_keys=(
                [block.name for block in obj.data.shape_keys.key_blocks]
                if obj.data.shape_keys
                else []
            ),
        )
    elif obj.type == "ARMATURE":
        data.update(
            bones=[bone.name for bone in obj.data.bones],
            bone_count=len(obj.data.bones),
            bone_tree=[
                {
                    "name": bone.name,
                    "parent": bone.parent.name if bone.parent else "",
                    "deform": bone.use_deform,
                }
                for bone in obj.data.bones
            ],
        )
    return data


report = {
    "blender_version": bpy.app.version_string,
    "file": bpy.data.filepath,
    "objects": [object_summary(obj) for obj in bpy.data.objects],
    "images": [
        {
            "name": image.name,
            "filepath": image.filepath,
            "packed": image.packed_file is not None,
            "size": list(image.size),
        }
        for image in bpy.data.images
    ],
    "actions": [
        {
            "name": action.name,
            "frame_range": list(action.frame_range),
            "slots": len(action.slots),
        }
        for action in bpy.data.actions
    ],
}

output_path = Path(sys.argv[-1]) if sys.argv[-2:-1] == ["--"] else None
if output_path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote audit report: {output_path}")
else:
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    print()
