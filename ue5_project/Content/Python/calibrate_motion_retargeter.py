import unreal


ASSET_PATH = "/Game/Aociety/MotionMatching/RTG_MannyToEcy"

retargeter = unreal.load_asset(ASSET_PATH)
controller = unreal.IKRetargeterController.get_controller(retargeter)
updated = False

for index in range(controller.get_num_retarget_ops()):
    op_controller = controller.get_op_controller(index)
    if not op_controller:
        continue
    if op_controller.get_class().get_name() != "IKRetargetPelvisMotionController":
        continue
    settings = op_controller.get_settings()
    settings.set_editor_property("translation_alpha", 0.0)
    settings.set_editor_property("affect_ik_horizontal", 0.0)
    settings.set_editor_property("affect_ik_vertical", 0.0)
    op_controller.set_settings(settings)
    updated = True
    print(
        "[RetargetCalibration] pelvis_op=%d translation_alpha=%s "
        "affect_ik_horizontal=%s affect_ik_vertical=%s"
        % (
            index,
            settings.get_editor_property("translation_alpha"),
            settings.get_editor_property("affect_ik_horizontal"),
            settings.get_editor_property("affect_ik_vertical"),
        )
    )
    break

if not updated:
    raise RuntimeError("Pelvis Motion op not found")

if not unreal.EditorAssetLibrary.save_asset(ASSET_PATH, only_if_is_dirty=False):
    raise RuntimeError("Failed to save calibrated IK Retargeter")

print("[RetargetCalibration] PASS")
