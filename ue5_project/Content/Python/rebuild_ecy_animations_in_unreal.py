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


def animation_delta(mode, frame, frame_count, selected):
    phase = 2.0 * math.pi * frame / max(1, frame_count - 1)
    wave = math.sin(phase)
    opposite = -wave
    if mode == "idle":
        values = {
            selected["hips"]: ("z", wave * 1.5),
            selected["spine"]: ("z", opposite * 1.0),
            selected["left_arm"]: ("x", 2.0 + wave * 1.0),
            selected["right_arm"]: ("x", -2.0 + opposite * 1.0),
        }
    else:
        swing = wave * 27.0
        values = {
            selected["hips"]: ("z", wave * 2.5),
            selected["spine"]: ("z", opposite * 2.0),
            selected["left_leg"]: ("x", swing),
            selected["right_leg"]: ("x", -swing),
            selected["left_knee"]: ("x", max(0.0, -swing) * 1.05),
            selected["right_knee"]: ("x", max(0.0, swing) * 1.05),
            selected["left_arm"]: ("x", -swing * 0.70),
            selected["right_arm"]: ("x", swing * 0.70),
            selected["left_forearm"]: ("x", -10.0),
            selected["right_forearm"]: ("x", -10.0),
        }
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
        "left_leg": find_track(tracks, "upper_leg", "l"),
        "right_leg": find_track(tracks, "upper_leg", "r"),
        "left_knee": find_track(tracks, "lower_leg", "l"),
        "right_knee": find_track(tracks, "lower_leg", "r"),
        "left_arm": find_track(tracks, "upper_arm", "l"),
        "right_arm": find_track(tracks, "upper_arm", "r"),
        "left_forearm": find_track(tracks, "lower_arm", "l"),
        "right_forearm": find_track(tracks, "lower_arm", "r"),
    }
    missing = [key for key, value in selected.items() if not value]
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
