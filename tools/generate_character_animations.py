from pathlib import Path
import math
import sys

import bpy


if "--" not in sys.argv or len(sys.argv) < sys.argv.index("--") + 4:
    raise RuntimeError(
        "Usage: blender -b --python generate_character_animations.py -- input output_dir prefix"
    )

separator = sys.argv.index("--")
input_path = Path(sys.argv[separator + 1]).resolve()
output_dir = Path(sys.argv[separator + 2]).resolve()
prefix = sys.argv[separator + 3]
output_dir.mkdir(parents=True, exist_ok=True)

if input_path.suffix.lower() == ".blend":
    bpy.ops.wm.open_mainfile(filepath=str(input_path))
else:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(input_path), import_pack_images=True)

armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
if not armatures:
    raise RuntimeError("No armature found")
armature = armatures[0]


def find_bone(*candidates):
    names = [bone.name for bone in armature.pose.bones]
    for candidate in candidates:
        if candidate in names:
            return armature.pose.bones[candidate]
        match = next((name for name in names if name.lower().startswith(candidate.lower())), None)
        if match:
            return armature.pose.bones[match]
    return None


bones = {
    "hips": find_bone("Hips", "hips"),
    "spine": find_bone("Spine1", "chest", "spine"),
    "left_leg": find_bone("LeftUpLeg", "upper_leg.L"),
    "right_leg": find_bone("RightUpLeg", "upper_leg.R"),
    "left_knee": find_bone("LeftLeg", "lower_leg.L"),
    "right_knee": find_bone("RightLeg", "lower_leg.R"),
    "left_arm": find_bone("LeftArm", "upper_arm.L"),
    "right_arm": find_bone("RightArm", "upper_arm.R"),
    "left_forearm": find_bone("LeftForeArm", "lower_arm.L"),
    "right_forearm": find_bone("RightForeArm", "lower_arm.R"),
}
missing = [name for name, bone in bones.items() if bone is None]
if missing:
    raise RuntimeError(f"Missing animation bones: {missing}")

for bone in bones.values():
    bone.rotation_mode = "XYZ"


def reset_pose():
    for pose_bone in armature.pose.bones:
        pose_bone.rotation_mode = "XYZ"
        pose_bone.rotation_euler = (0.0, 0.0, 0.0)
        pose_bone.location = (0.0, 0.0, 0.0)
        pose_bone.scale = (1.0, 1.0, 1.0)


def key_rotation(bone, frame, x=0.0, y=0.0, z=0.0):
    bone.rotation_euler = tuple(math.radians(value) for value in (x, y, z))
    bone.keyframe_insert("rotation_euler", frame=frame)


def key_location(bone, frame, x=0.0, y=0.0, z=0.0):
    bone.location = (x, y, z)
    bone.keyframe_insert("location", frame=frame)


def create_idle():
    action = bpy.data.actions.new(f"A_{prefix}_Idle")
    armature.animation_data_create()
    armature.animation_data.action = action
    reset_pose()
    for frame, sway, bob in ((1, -1.5, 0.0), (31, 1.5, 0.012), (61, -1.5, 0.0)):
        key_rotation(bones["hips"], frame, z=sway)
        key_location(bones["hips"], frame, z=bob)
        key_rotation(bones["spine"], frame, x=-1.0, z=-sway * 0.7)
        key_rotation(bones["left_arm"], frame, x=1.5 + sway * 0.3, z=-3.0)
        key_rotation(bones["right_arm"], frame, x=-1.5 - sway * 0.3, z=3.0)
    return action, 1, 61


def create_walk():
    action = bpy.data.actions.new(f"A_{prefix}_Walk")
    armature.animation_data_create()
    armature.animation_data.action = action
    reset_pose()
    poses = (
        (1, 28.0, -28.0, 0.0),
        (9, 0.0, 0.0, 0.028),
        (17, -28.0, 28.0, 0.0),
        (25, 0.0, 0.0, 0.028),
        (33, 28.0, -28.0, 0.0),
    )
    for frame, left_swing, right_swing, bob in poses:
        key_location(bones["hips"], frame, z=bob)
        key_rotation(bones["hips"], frame, z=(left_swing / 28.0) * 2.5)
        key_rotation(bones["spine"], frame, z=-(left_swing / 28.0) * 2.0)
        key_rotation(bones["left_leg"], frame, x=left_swing)
        key_rotation(bones["right_leg"], frame, x=right_swing)
        key_rotation(bones["left_knee"], frame, x=max(0.0, -left_swing) * 1.15)
        key_rotation(bones["right_knee"], frame, x=max(0.0, -right_swing) * 1.15)
        key_rotation(bones["left_arm"], frame, x=-left_swing * 0.72)
        key_rotation(bones["right_arm"], frame, x=-right_swing * 0.72)
        key_rotation(bones["left_forearm"], frame, x=-12.0)
        key_rotation(bones["right_forearm"], frame, x=-12.0)
    return action, 1, 33


def export_action(action, first_frame, last_frame, suffix):
    armature.animation_data.action = action
    bpy.context.scene.frame_start = first_frame
    bpy.context.scene.frame_end = last_frame
    bpy.context.scene.render.fps = 30
    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    output = output_dir / f"A_{prefix}_{suffix}.fbx"
    bpy.ops.export_scene.fbx(
        filepath=str(output),
        use_selection=True,
        object_types={"ARMATURE"},
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Z",
        axis_up="Y",
        use_space_transform=True,
        add_leaf_bones=False,
        bake_anim=True,
        bake_anim_use_all_bones=True,
        bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False,
        bake_anim_force_startend_keying=True,
        bake_anim_step=1.0,
        bake_anim_simplify_factor=0.0,
    )
    print(f"[AocietyAnimation] exported={output}")


idle_action, idle_start, idle_end = create_idle()
export_action(idle_action, idle_start, idle_end, "Idle")
walk_action, walk_start, walk_end = create_walk()
export_action(walk_action, walk_start, walk_end, "Walk")
