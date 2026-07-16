from pathlib import Path
import sys

import bpy


if "--" not in sys.argv:
    raise RuntimeError("Usage: blender -b --python inspect_character_bones.py -- file")

path = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
if path.suffix.lower() == ".blend":
    bpy.ops.wm.open_mainfile(filepath=str(path))
else:
    bpy.ops.import_scene.gltf(filepath=str(path), import_pack_images=True)

for armature in [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]:
    print(f"[AocietyBones] armature={armature.name} count={len(armature.data.bones)}")
    print("[AocietyBones] " + ",".join(bone.name for bone in armature.data.bones))
