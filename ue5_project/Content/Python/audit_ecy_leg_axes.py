import unreal


SKELETON_PATH = "/Game/Aociety/Characters/Ecy/SK_Ecy_Skeleton"
ANIMATION_PATH = "/Game/Aociety/Characters/Ecy/Animations/A_Ecy_Walk"

skeleton = unreal.load_asset(SKELETON_PATH)
pose = skeleton.get_reference_pose()
animation = unreal.load_asset(ANIMATION_PATH)
names = [str(name) for name in pose.get_bone_names()]
lines = []


def emit(message):
    lines.append(message)
    print(message)


def multiply_quat(a, b):
    x = a.w * b.x + a.x * b.w + a.y * b.z - a.z * b.y
    y = a.w * b.y - a.x * b.z + a.y * b.w + a.z * b.x
    z = a.w * b.z + a.x * b.y - a.y * b.x + a.z * b.w
    w = a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z
    length = (x * x + y * y + z * z + w * w) ** 0.5
    return unreal.Quat(x / length, y / length, z / length, w / length)


def axis_quat(axis, degrees):
    import math

    half = math.radians(degrees) * 0.5
    sine = math.sin(half)
    cosine = math.cos(half)
    if axis == "x":
        return unreal.Quat(sine, 0.0, 0.0, cosine)
    if axis == "y":
        return unreal.Quat(0.0, sine, 0.0, cosine)
    return unreal.Quat(0.0, 0.0, sine, cosine)


def rotated(transform, axis, degrees):
    return unreal.Transform(
        transform.translation,
        multiply_quat(transform.rotation, axis_quat(axis, degrees)).rotator(),
        transform.scale3d,
    )


def compose_chain(transforms):
    result = transforms[0]
    for transform in transforms[1:]:
        result = unreal.MathLibrary.compose_transforms(transform, result)
    return result


def xyz(vector):
    return tuple(round(value, 4) for value in (vector.x, vector.y, vector.z))

emit(
    "[EcyLegAxisAudit] pose_api="
    + str([name for name in dir(pose) if "bone" in name.lower() or "parent" in name.lower()])
)
emit(f"[EcyLegAxisAudit] get_bone_pose_doc={pose.get_bone_pose.__doc__}")
emit(
    f"[EcyLegAxisAudit] compose_transforms_doc="
    f"{unreal.MathLibrary.compose_transforms.__doc__}"
)
for name in names:
    lower = name.lower()
    if any(token in lower for token in ("upper_leg", "lower_leg", "foot", "toe", "hips_", "root_")):
        ref = pose.get_ref_bone_pose(name)
        emit(f"[EcyLegAxisAudit] ref bone={name} transform={ref}")

root_ref = pose.get_ref_bone_pose("root_218")
hips_ref = pose.get_ref_bone_pose("hips_217")
for side in ("L", "R"):
    upper_ref = pose.get_ref_bone_pose(f"upper_leg_{side}_{145 if side == 'L' else 149}")
    lower_ref = pose.get_ref_bone_pose(f"lower_leg_{side}_{144 if side == 'L' else 148}")
    foot_ref = pose.get_ref_bone_pose(f"foot_{side}_{143 if side == 'L' else 147}")
    rest_foot = compose_chain((root_ref, hips_ref, upper_ref, lower_ref, foot_ref))
    emit(f"[EcyLegAxisAudit] side={side} rest_foot={xyz(rest_foot.translation)}")
    for axis in ("x", "y", "z"):
        upper_test = rotated(upper_ref, axis, 20.0)
        upper_foot = compose_chain((root_ref, hips_ref, upper_test, lower_ref, foot_ref))
        lower_test = rotated(lower_ref, axis, 25.0)
        knee_foot = compose_chain((root_ref, hips_ref, upper_ref, lower_test, foot_ref))
        emit(
            f"[EcyLegAxisAudit] side={side} axis={axis} "
            f"upper20_foot={xyz(upper_foot.translation)} "
            f"knee25_foot={xyz(knee_foot.translation)}"
        )

for frame in (0, 4, 8, 12, 16, 20, 24, 28, 31):
    samples = []
    for name in names:
        lower = name.lower()
        if any(token in lower for token in ("upper_leg", "lower_leg", "foot_")):
            transform = unreal.AnimationLibrary.get_bone_pose_for_frame(
                animation, name, frame, False
            )
            samples.append((name, transform.rotation.rotator()))
    emit(f"[EcyLegAxisAudit] frame={frame} rotations={samples}")
    root_frame = unreal.AnimationLibrary.get_bone_pose_for_frame(
        animation, "root_218", frame, False
    )
    hips_frame = unreal.AnimationLibrary.get_bone_pose_for_frame(
        animation, "hips_217", frame, False
    )
    positions = []
    for side in ("L", "R"):
        upper = unreal.AnimationLibrary.get_bone_pose_for_frame(
            animation, f"upper_leg_{side}_{145 if side == 'L' else 149}", frame, False
        )
        lower = unreal.AnimationLibrary.get_bone_pose_for_frame(
            animation, f"lower_leg_{side}_{144 if side == 'L' else 148}", frame, False
        )
        foot = unreal.AnimationLibrary.get_bone_pose_for_frame(
            animation, f"foot_{side}_{143 if side == 'L' else 147}", frame, False
        )
        foot_world = compose_chain((root_frame, hips_frame, upper, lower, foot))
        positions.append((side, xyz(foot_world.translation)))
    emit(f"[EcyLegAxisAudit] frame={frame} foot_positions={positions}")

emit("[EcyLegAxisAudit] complete")
with open(r"E:\Aociety-NEW\ue5_project\Saved\EcyLegAxisAudit.txt", "w", encoding="utf-8") as handle:
    handle.write("\n".join(lines))
