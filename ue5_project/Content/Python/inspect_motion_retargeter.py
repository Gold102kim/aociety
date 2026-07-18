import unreal


retargeter = unreal.load_asset(
    "/Game/Aociety/MotionMatching/RTG_MannyToEcy"
)
controller = unreal.IKRetargeterController.get_controller(retargeter)
skeleton = unreal.load_asset(
    "/Game/Aociety/Characters/Ecy/SK_Ecy_Skeleton"
)
reference_pose = skeleton.get_reference_pose()

for bone_name in ("SK_Ecy_Armature", "root_218", "hips_217"):
    print(
        "[RetargetAudit] target_ref bone=%s local=%s"
        % (bone_name, reference_pose.get_ref_bone_pose(bone_name))
    )

print(
    "[RetargetAudit] source_root_offset=%s target_root_offset=%s ops=%d"
    % (
        controller.get_root_offset_in_retarget_pose(
            unreal.RetargetSourceOrTarget.SOURCE
        ),
        controller.get_root_offset_in_retarget_pose(
            unreal.RetargetSourceOrTarget.TARGET
        ),
        controller.get_num_retarget_ops(),
    )
)

for index in range(controller.get_num_retarget_ops()):
    op_controller = controller.get_op_controller(index)
    settings = None
    if op_controller and hasattr(op_controller, "get_settings"):
        settings = op_controller.get_settings()
    print(
        "[RetargetAudit] op=%d name=%s enabled=%s controller=%s settings=%s"
        % (
            index,
            controller.get_op_name(index),
            controller.get_retarget_op_enabled(index),
            op_controller.get_class().get_name() if op_controller else None,
            settings,
        )
    )
