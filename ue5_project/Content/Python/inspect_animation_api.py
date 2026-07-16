import unreal


for class_name in ("AnimationLibrary", "AnimationDataController", "AnimSequence"):
    cls = getattr(unreal, class_name, None)
    if cls:
        names = [
            name
            for name in dir(cls)
            if any(token in name.lower() for token in ("bone", "track", "curve", "model"))
        ]
        print(f"[AnimationAPI] {class_name}={names}")

component_names = [
    name for name in dir(unreal.SkeletalMeshComponent) if "bound" in name.lower()
]
print(f"[AnimationAPI] SkeletalMeshComponentBounds={component_names}")
for class_name in ("SkeletalMeshEditorSubsystem", "Skeleton", "SkeletalMesh"):
    cls = getattr(unreal, class_name, None)
    if cls:
        names = [
            name
            for name in dir(cls)
            if any(token in name.lower() for token in ("bone", "ref", "pose", "skeleton"))
        ]
        print(f"[AnimationAPI] {class_name}Refs={names}")
pose = unreal.load_asset("/Game/Aociety/Characters/Ecy/SK_Ecy_Skeleton").get_reference_pose()
pose_names = [
    name
    for name in dir(pose)
    if any(token in name.lower() for token in ("bone", "transform", "pose", "name"))
]
print(f"[AnimationAPI] AnimPose={pose_names}")
print(f"[AnimationAPI] AnimPoseGetRef={unreal.AnimPose.get_ref_bone_pose.__doc__}")
print(f"[AnimationAPI] AnimPoseGetNames={unreal.AnimPose.get_bone_names.__doc__}")
print(f"[AnimationAPI] GetBonePoseFrame={unreal.AnimationLibrary.get_bone_pose_for_frame.__doc__}")
print(f"[AnimationAPI] GetRawTrack={unreal.AnimationLibrary.get_raw_track_data.__doc__}")
print(f"[AnimationAPI] SetBoneKeys={unreal.AnimationDataController.set_bone_track_keys.__doc__}")
print(f"[AnimationAPI] SetModel={unreal.AnimationDataController.set_model.__doc__}")
controller_names = [
    name for name in dir(unreal.AnimSequence) if "controller" in name.lower()
]
print(f"[AnimationAPI] AnimSequenceControllers={controller_names}")
controller_classes = [
    name for name in dir(unreal) if "animationdatacontroller" in name.lower()
]
print(f"[AnimationAPI] ControllerClasses={controller_classes}")
