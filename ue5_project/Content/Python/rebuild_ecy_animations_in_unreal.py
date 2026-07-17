import math

import unreal


ANIMATION_ROOT = "/Game/Aociety/Characters/Ecy/Animations"
SKELETON_PATH = "/Game/Aociety/Characters/Ecy/SK_Ecy_Skeleton"


def multiply_quat(a, b):
    x = a.w * b.x + a.x * b.w + a.y * b.z - a.z * b.y
    y = a.w * b.y - a.x * b.z + a.y * b.w + a.z * b.x
    z = a.w * b.z + a.x * b.y - a.y * b.x + a.z * b.w
    w = a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z
    length = math.sqrt(x * x + y * y + z * z + w * w)
    return unreal.Quat(x / length, y / length, z / length, w / length)


def axis_quat(axis, degrees):
    half = math.radians(degrees) * 0.5
    sine = math.sin(half)
    cosine = math.cos(half)
    if axis == "x":
        return unreal.Quat(sine, 0.0, 0.0, cosine)
    if axis == "y":
        return unreal.Quat(0.0, sine, 0.0, cosine)
    return unreal.Quat(0.0, 0.0, sine, cosine)


def find_track(tracks, *tokens):
    for track in tracks:
        name = track.lower()
        if all(token.lower() in name for token in tokens):
            return track
    return None


def find_sided_track(tracks, stem, side):
    marker = f"_{side.lower()}_"
    for track in tracks:
        name = track.lower()
        if stem.lower() in name and marker in name:
            return track
    return None


def animation_delta(mode, frame, frame_count, selected):
    phase = 2.0 * math.pi * frame / max(1, frame_count - 1)
    wave = math.sin(phase)
    opposite = -wave
    if mode == "idle":
        values = {
            selected["hips"]: ("z", wave * 0.8),
            selected["spine"]: ("z", opposite * 0.55),
            selected["left_arm"]: ("x", 1.0 + wave * 0.5),
            selected["right_arm"]: ("x", -1.0 + opposite * 0.5),
        }
    else:
        # This glTF rig keeps local Y as the bone-length axis. Visual axis tests
        # show local X produces the reported sideways high-step, while local Z
        # is the sagittal flexion axis. Mirrored bone rolls mean both thighs use
        # the same local-Z sign, while knee/ankle compensation must be mirrored.
        swing = wave * 18.0
        stride_velocity = math.cos(phase)
        left_knee_flex = 4.0 + max(0.0, stride_velocity) * 24.0
        right_knee_flex = 4.0 + max(0.0, -stride_velocity) * 24.0
        values = {
            selected["hips"]: ("z", wave * 1.1),
            selected["spine"]: ("z", opposite * 0.9),
            selected["left_leg"]: ("z", -swing),
            selected["right_leg"]: ("z", -swing),
            selected["left_knee"]: ("z", left_knee_flex),
            selected["right_knee"]: ("z", -right_knee_flex),
            selected["left_foot"]: ("z", -left_knee_flex * 0.42),
            selected["right_foot"]: ("z", right_knee_flex * 0.42),
            selected["left_arm"]: ("x", -swing * 0.45),
            selected["right_arm"]: ("x", swing * 0.45),
            selected["left_forearm"]: ("x", -6.0),
            selected["right_forearm"]: ("x", -6.0),
        }
    if selected.get("left_skirt"):
        values[selected["left_skirt"]] = ("z", wave * 2.0)
    if selected.get("right_skirt"):
        values[selected["right_skirt"]] = ("z", -wave * 2.0)
    return values


def rebuild(path, frame_count, mode):
    backup_path = f"{path}_ImportedBackup"
    if not unreal.EditorAssetLibrary.does_asset_exist(backup_path):
        if not unreal.EditorAssetLibrary.duplicate_asset(path, backup_path):
            raise RuntimeError(f"Could not create animation backup: {backup_path}")

    animation = unreal.load_asset(path)
    tracks = [
        str(name) for name in unreal.AnimationLibrary.get_animation_track_names(animation)
    ]
    selected = {
        "hips": find_track(tracks, "hips"),
        "spine": find_track(tracks, "spine"),
        "left_leg": find_sided_track(tracks, "upper_leg", "l"),
        "right_leg": find_sided_track(tracks, "upper_leg", "r"),
        "left_knee": find_sided_track(tracks, "lower_leg", "l"),
        "right_knee": find_sided_track(tracks, "lower_leg", "r"),
        "left_foot": find_sided_track(tracks, "foot", "l"),
        "right_foot": find_sided_track(tracks, "foot", "r"),
        "left_arm": find_sided_track(tracks, "upper_arm", "l"),
        "right_arm": find_sided_track(tracks, "upper_arm", "r"),
        "left_forearm": find_sided_track(tracks, "lower_arm", "l"),
        "right_forearm": find_sided_track(tracks, "lower_arm", "r"),
        "left_skirt": find_track(tracks, "sk_l_154"),
        "right_skirt": find_track(tracks, "sk_r_169"),
    }
    missing = [
        key
        for key, value in selected.items()
        if key not in ("left_skirt", "right_skirt") and not value
    ]
    if missing:
        raise RuntimeError(f"Missing Ecy tracks: {missing}")

    reference = unreal.load_asset(SKELETON_PATH).get_reference_pose()
    controller = animation.get_editor_property("controller")

    for track in tracks:
        ref = reference.get_ref_bone_pose(track)
        positions = []
        rotations = []
        scales = []
        for frame in range(frame_count):
            positions.append(ref.translation)
            scales.append(ref.scale3d)
            delta = animation_delta(mode, frame, frame_count, selected).get(track)
            if delta:
                rotations.append(
                    multiply_quat(ref.rotation, axis_quat(delta[0], delta[1]))
                )
            else:
                rotations.append(ref.rotation)
        if not controller.set_bone_track_keys(
            track, positions, rotations, scales, False
        ):
            raise RuntimeError(f"Could not write {track} in {path}")

    unreal.EditorAssetLibrary.save_loaded_asset(animation, only_if_is_dirty=False)
    print(
        f"[EcyAnimationRebuild] animation={path} frames={frame_count} mode={mode}"
    )


rebuild(f"{ANIMATION_ROOT}/A_Ecy_Idle", 61, "idle")
rebuild(f"{ANIMATION_ROOT}/A_Ecy_Walk", 33, "walk")
unreal.EditorAssetLibrary.save_directory(
    ANIMATION_ROOT, only_if_is_dirty=False, recursive=True
)
print("[EcyAnimationRebuild] complete")
