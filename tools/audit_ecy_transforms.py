import bpy


def vec(value):
    return tuple(round(float(part), 6) for part in value)


print(
    "[EcyBlenderAudit] "
    f"unit_system={bpy.context.scene.unit_settings.system} "
    f"scale_length={bpy.context.scene.unit_settings.scale_length}"
)

for obj in bpy.data.objects:
    if obj.type not in {"ARMATURE", "MESH", "EMPTY"}:
        continue
    armature_targets = [
        modifier.object.name if modifier.object else "None"
        for modifier in getattr(obj, "modifiers", ())
        if modifier.type == "ARMATURE"
    ]
    print(
        "[EcyBlenderAudit] "
        f"object={obj.name} type={obj.type} parent={obj.parent.name if obj.parent else 'None'} "
        f"location={vec(obj.location)} rotation={vec(obj.rotation_euler)} scale={vec(obj.scale)} "
        f"dimensions={vec(obj.dimensions)} armature_targets={armature_targets}"
    )

armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
for armature in armatures:
    print(
        f"[EcyBlenderAudit] armature={armature.name} "
        f"bones={len(armature.data.bones)} pose_position={armature.data.pose_position}"
    )
    for bone in armature.data.bones:
        if bone.parent is None or bone.name in {
            "root_218",
            "hips_217",
            "spine_141",
            "chest_140",
            "upper_leg.L_143",
            "upper_leg.R_142",
            "lower_leg.L_145",
            "lower_leg.R_144",
            "upper_arm.L_138",
            "upper_arm.R_137",
            "lower_arm.L_135",
            "lower_arm.R_134",
        }:
            print(
                "[EcyBlenderAudit] "
                f"bone={bone.name} parent={bone.parent.name if bone.parent else 'None'} "
                f"head={vec(bone.head_local)} tail={vec(bone.tail_local)} "
                f"matrix_scale={vec(bone.matrix_local.to_scale())} deform={bone.use_deform}"
            )

