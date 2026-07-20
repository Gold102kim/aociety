// Copyright Aociety. All rights reserved.

#include "AocietyMotionAssetBuilderCommandlet.h"

#include "Animation/AnimData/IAnimationDataController.h"
#include "Animation/AnimData/IAnimationDataModel.h"
#include "Animation/AnimSequence.h"
#include "Animation/Skeleton.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Chooser.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "ObjectChooser_Asset.h"
#include "PoseSearch/PoseSearchDatabase.h"
#include "PoseSearch/PoseSearchDerivedData.h"
#include "PoseSearch/PoseSearchIndex.h"
#include "PoseSearch/PoseSearchSchema.h"
#include "RetargetEditor/IKRetargeterController.h"
#include "Retargeter/IKRetargeter.h"
#include "Retargeter/RetargetOps/PelvisMotionOp.h"
#include "Rig/IKRigDefinition.h"
#include "RigEditor/IKRigController.h"
#include "Serialization/Archive.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"

namespace
{
constexpr const TCHAR* MotionFolder = TEXT("/Game/Aociety/MotionMatching");

enum class ERootMotionProfile : uint8
{
    Constant,
    Accelerate,
    Decelerate,
    TurnLeft,
    TurnRight,
};

template <typename T>
T* FindOrCreateAsset(const FString& AssetName, bool& bOutCreated)
{
    const FString PackageName = FString::Printf(
        TEXT("%s/%s"), MotionFolder, *AssetName);
    const FString ObjectPath = FString::Printf(
        TEXT("%s.%s"), *PackageName, *AssetName);
    if (T* Existing = LoadObject<T>(nullptr, *ObjectPath))
    {
        bOutCreated = false;
        return Existing;
    }

    UPackage* Package = CreatePackage(*PackageName);
    T* Asset = NewObject<T>(
        Package,
        *AssetName,
        RF_Public | RF_Standalone | RF_Transactional);
    FAssetRegistryModule::AssetCreated(Asset);
    Asset->MarkPackageDirty();
    bOutCreated = true;
    return Asset;
}

bool SaveAsset(UObject* Asset)
{
    if (!Asset)
    {
        return false;
    }

    UPackage* Package = Asset->GetOutermost();
    const FString Filename = FPackageName::LongPackageNameToFilename(
        Package->GetName(),
        FPackageName::GetAssetPackageExtension());
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(Filename), true);

    FSavePackageArgs SaveArgs;
    SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
    SaveArgs.SaveFlags = SAVE_NoError;
    return UPackage::SavePackage(Package, Asset, *Filename, SaveArgs);
}

USkeletalMesh* BuildMannyDriverMesh(
    USkeletalMesh* SourceMesh,
    USkeleton* MannySkeleton)
{
    const FString AssetName(TEXT("SKM_Manny_Aociety"));
    const FString PackageName = FString::Printf(
        TEXT("%s/%s"), MotionFolder, *AssetName);
    const FString ObjectPath = FString::Printf(
        TEXT("%s.%s"), *PackageName, *AssetName);
    USkeletalMesh* DriverMesh = LoadObject<USkeletalMesh>(nullptr, *ObjectPath);
    bool bCreated = false;
    if (!DriverMesh)
    {
        UPackage* Package = CreatePackage(*PackageName);
        DriverMesh = DuplicateObject<USkeletalMesh>(
            SourceMesh, Package, *AssetName);
        DriverMesh->SetFlags(RF_Public | RF_Standalone | RF_Transactional);
        FAssetRegistryModule::AssetCreated(DriverMesh);
        bCreated = true;
    }

    DriverMesh->SetSkeleton(MannySkeleton);
    DriverMesh->MarkPackageDirty();
    DriverMesh->PostEditChange();
    SaveAsset(DriverMesh);
    UE_LOG(
        LogTemp,
        Display,
        TEXT("[AocietyMotionAssetBuilder] driver_mesh=%s created=%s skeleton=%s bones=%d"),
        *DriverMesh->GetPathName(),
        bCreated ? TEXT("true") : TEXT("false"),
        *GetNameSafe(DriverMesh->GetSkeleton()),
        DriverMesh->GetRefSkeleton().GetNum());
    return DriverMesh;
}

FName FindFirstExistingBone(
    const USkeletalMesh* Mesh,
    const TArray<FName>& Candidates)
{
    if (!Mesh)
    {
        return NAME_None;
    }

    const FReferenceSkeleton& ReferenceSkeleton = Mesh->GetRefSkeleton();
    for (const FName Candidate : Candidates)
    {
        if (ReferenceSkeleton.FindBoneIndex(Candidate) != INDEX_NONE)
        {
            return Candidate;
        }
    }
    return NAME_None;
}

void EnsureRetargetChain(
    UIKRigController* Controller,
    FName ChainName,
    FName StartBone,
    FName EndBone)
{
    if (!Controller || StartBone.IsNone() || EndBone.IsNone())
    {
        UE_LOG(
            LogTemp,
            Error,
            TEXT("[AocietyMotionAssetBuilder] invalid chain=%s start=%s end=%s"),
            *ChainName.ToString(),
            *StartBone.ToString(),
            *EndBone.ToString());
        return;
    }

    if (Controller->GetRetargetChainStartBone(ChainName).IsNone())
    {
        Controller->AddRetargetChain(
            ChainName,
            StartBone,
            EndBone,
            NAME_None);
        return;
    }

    Controller->SetRetargetChainStartBone(ChainName, StartBone);
    Controller->SetRetargetChainEndBone(ChainName, EndBone);
    Controller->SetRetargetChainGoal(ChainName, NAME_None);
}

UIKRigDefinition* BuildMannyRig(USkeletalMesh* MannyMesh)
{
    bool bCreated = false;
    UIKRigDefinition* Rig = FindOrCreateAsset<UIKRigDefinition>(
        TEXT("IKR_Manny_Aociety"), bCreated);
    UIKRigController* Controller = UIKRigController::GetController(Rig);
    Controller->SetSkeletalMesh(MannyMesh);
    Controller->SetRetargetRoot(TEXT("pelvis"));
    Controller->SetRootMotionBone(TEXT("root"));

    const FName SpineEnd = FindFirstExistingBone(
        MannyMesh,
        {TEXT("spine_05"), TEXT("spine_04"), TEXT("spine_03")});
    const FName NeckEnd = FindFirstExistingBone(
        MannyMesh,
        {TEXT("neck_02"), TEXT("neck_01")});

    EnsureRetargetChain(Controller, TEXT("Root"), TEXT("root"), TEXT("root"));
    EnsureRetargetChain(
        Controller, TEXT("Spine"), TEXT("spine_01"), SpineEnd);
    EnsureRetargetChain(
        Controller, TEXT("Neck"), TEXT("neck_01"), NeckEnd);
    EnsureRetargetChain(Controller, TEXT("Head"), TEXT("head"), TEXT("head"));
    EnsureRetargetChain(
        Controller, TEXT("LeftArm"), TEXT("clavicle_l"), TEXT("hand_l"));
    EnsureRetargetChain(
        Controller, TEXT("RightArm"), TEXT("clavicle_r"), TEXT("hand_r"));
    EnsureRetargetChain(
        Controller, TEXT("LeftLeg"), TEXT("thigh_l"), TEXT("foot_l"));
    EnsureRetargetChain(
        Controller, TEXT("RightLeg"), TEXT("thigh_r"), TEXT("foot_r"));
    EnsureRetargetChain(
        Controller, TEXT("LeftToe"), TEXT("ball_l"), TEXT("ball_l"));
    EnsureRetargetChain(
        Controller, TEXT("RightToe"), TEXT("ball_r"), TEXT("ball_r"));

    Rig->MarkPackageDirty();
    SaveAsset(Rig);
    UE_LOG(
        LogTemp,
        Display,
        TEXT("[AocietyMotionAssetBuilder] manny_rig=%s created=%s chains=%d"),
        *Rig->GetPathName(),
        bCreated ? TEXT("true") : TEXT("false"),
        Controller->GetRetargetChains().Num());
    return Rig;
}

UIKRigDefinition* BuildEcyRig(USkeletalMesh* EcyMesh)
{
    bool bCreated = false;
    UIKRigDefinition* Rig = FindOrCreateAsset<UIKRigDefinition>(
        TEXT("IKR_Ecy"), bCreated);
    UIKRigController* Controller = UIKRigController::GetController(Rig);
    Controller->SetSkeletalMesh(EcyMesh);
    Controller->SetRetargetRoot(TEXT("hips_217"));
    Controller->SetRootMotionBone(TEXT("root_218"));

    const FName LeftShoulder = FindFirstExistingBone(
        EcyMesh, {TEXT("shoulder.L_116"), TEXT("shoulder_L_116")});
    const FName LeftHand = FindFirstExistingBone(
        EcyMesh, {TEXT("hand.L_113"), TEXT("hand_L_113")});
    const FName RightShoulder = FindFirstExistingBone(
        EcyMesh, {TEXT("shoulder.R_135"), TEXT("shoulder_R_135")});
    const FName RightHand = FindFirstExistingBone(
        EcyMesh, {TEXT("hand.R_132"), TEXT("hand_R_132")});
    const FName LeftUpperLeg = FindFirstExistingBone(
        EcyMesh, {TEXT("upper_leg.L_145"), TEXT("upper_leg_L_145")});
    const FName LeftFoot = FindFirstExistingBone(
        EcyMesh, {TEXT("foot.L_143"), TEXT("foot_L_143")});
    const FName RightUpperLeg = FindFirstExistingBone(
        EcyMesh, {TEXT("upper_leg.R_149"), TEXT("upper_leg_R_149")});
    const FName RightFoot = FindFirstExistingBone(
        EcyMesh, {TEXT("foot.R_147"), TEXT("foot_R_147")});
    const FName LeftToe = FindFirstExistingBone(
        EcyMesh, {TEXT("toes.L_142"), TEXT("toes_L_142")});
    const FName RightToe = FindFirstExistingBone(
        EcyMesh, {TEXT("toes.R_146"), TEXT("toes_R_146")});

    EnsureRetargetChain(
        Controller, TEXT("Root"), TEXT("root_218"), TEXT("root_218"));
    EnsureRetargetChain(
        Controller, TEXT("Spine"), TEXT("spine_141"), TEXT("chest_140"));
    EnsureRetargetChain(
        Controller, TEXT("Neck"), TEXT("neck_97"), TEXT("neck_97"));
    EnsureRetargetChain(
        Controller, TEXT("Head"), TEXT("head_96"), TEXT("head_96"));
    EnsureRetargetChain(
        Controller,
        TEXT("LeftArm"),
        LeftShoulder,
        LeftHand);
    EnsureRetargetChain(
        Controller,
        TEXT("RightArm"),
        RightShoulder,
        RightHand);
    EnsureRetargetChain(
        Controller,
        TEXT("LeftLeg"),
        LeftUpperLeg,
        LeftFoot);
    EnsureRetargetChain(
        Controller,
        TEXT("RightLeg"),
        RightUpperLeg,
        RightFoot);
    EnsureRetargetChain(
        Controller,
        TEXT("LeftToe"),
        LeftToe,
        LeftToe);
    EnsureRetargetChain(
        Controller,
        TEXT("RightToe"),
        RightToe,
        RightToe);

    Rig->MarkPackageDirty();
    SaveAsset(Rig);
    UE_LOG(
        LogTemp,
        Display,
        TEXT("[AocietyMotionAssetBuilder] ecy_rig=%s created=%s chains=%d"),
        *Rig->GetPathName(),
        bCreated ? TEXT("true") : TEXT("false"),
        Controller->GetRetargetChains().Num());
    return Rig;
}

UIKRetargeter* BuildRetargeter(
    UIKRigDefinition* MannyRig,
    UIKRigDefinition* EcyRig,
    USkeletalMesh* MannyMesh,
    USkeletalMesh* EcyMesh)
{
    bool bCreated = false;
    UIKRetargeter* Retargeter = FindOrCreateAsset<UIKRetargeter>(
        TEXT("RTG_MannyToEcy"), bCreated);
    UIKRetargeterController* Controller =
        UIKRetargeterController::GetController(Retargeter);
    Controller->SetIKRig(ERetargetSourceOrTarget::Source, MannyRig);
    Controller->SetIKRig(ERetargetSourceOrTarget::Target, EcyRig);
    Controller->SetPreviewMesh(ERetargetSourceOrTarget::Source, MannyMesh);
    Controller->SetPreviewMesh(ERetargetSourceOrTarget::Target, EcyMesh);
    if (Controller->GetNumRetargetOps() == 0)
    {
        Controller->AddDefaultOps();
    }
    Controller->AssignIKRigToAllOps(
        ERetargetSourceOrTarget::Source, MannyRig);
    Controller->AssignIKRigToAllOps(
        ERetargetSourceOrTarget::Target, EcyRig);
    Controller->AutoMapChains(EAutoMapChainType::Exact, true);
    for (const FName ChainName : {
             FName(TEXT("Root")),
             FName(TEXT("Spine")),
             FName(TEXT("Neck")),
             FName(TEXT("Head")),
             FName(TEXT("LeftArm")),
             FName(TEXT("RightArm")),
             FName(TEXT("LeftLeg")),
             FName(TEXT("RightLeg")),
             FName(TEXT("LeftToe")),
             FName(TEXT("RightToe")),
         })
    {
        Controller->SetSourceChain(ChainName, ChainName);
    }
    Controller->AutoAlignAllBones(ERetargetSourceOrTarget::Target);
    if (FIKRetargetPelvisMotionOp* PelvisMotion =
            Controller->GetFirstRetargetOpOfType<FIKRetargetPelvisMotionOp>())
    {
        PelvisMotion->Settings.TranslationAlpha = 0.0;
        PelvisMotion->Settings.AffectIKHorizontal = 0.0;
        PelvisMotion->Settings.AffectIKVertical = 0.0;
    }
    Controller->CleanAsset();

    Retargeter->MarkPackageDirty();
    SaveAsset(Retargeter);
    UE_LOG(
        LogTemp,
        Display,
        TEXT("[AocietyMotionAssetBuilder] retargeter=%s created=%s ops=%d"),
        *Retargeter->GetPathName(),
        bCreated ? TEXT("true") : TEXT("false"),
        Controller->GetNumRetargetOps());
    return Retargeter;
}

UAnimSequence* BuildRootMotionSequence(
    const FString& SourcePath,
    const FString& AssetName,
    FVector2D Direction,
    float Speed,
    ERootMotionProfile Profile = ERootMotionProfile::Constant)
{
    UAnimSequence* Source = LoadObject<UAnimSequence>(nullptr, *SourcePath);
    if (!Source)
    {
        UE_LOG(
            LogTemp,
            Error,
            TEXT("[AocietyMotionAssetBuilder] missing source animation=%s"),
            *SourcePath);
        return nullptr;
    }

    const FString PackageName = FString::Printf(
        TEXT("%s/Animations/%s"), MotionFolder, *AssetName);
    const FString ObjectPath = FString::Printf(
        TEXT("%s.%s"), *PackageName, *AssetName);
    UAnimSequence* Sequence = LoadObject<UAnimSequence>(nullptr, *ObjectPath);
    if (!Sequence)
    {
        UPackage* Package = CreatePackage(*PackageName);
        Sequence = DuplicateObject<UAnimSequence>(Source, Package, *AssetName);
        Sequence->SetFlags(RF_Public | RF_Standalone | RF_Transactional);
        FAssetRegistryModule::AssetCreated(Sequence);
    }

    Sequence->SetSkeleton(Source->GetSkeleton());

    const IAnimationDataModel* SourceModel = Source->GetDataModel();
    const IAnimationDataModel* Model = Sequence->GetDataModel();
    if (!SourceModel || !Model)
    {
        UE_LOG(
            LogTemp,
            Error,
            TEXT("[AocietyMotionAssetBuilder] no data model source=%s target=%s"),
            *Source->GetPathName(),
            *Sequence->GetPathName());
        return nullptr;
    }

    const FName RootBone(TEXT("root"));
    const int32 NumKeys = FMath::Max(2, SourceModel->GetNumberOfKeys());
    TArray<FTransform> ExistingTransforms;
    if (SourceModel->IsValidBoneTrackName(RootBone))
    {
        SourceModel->GetBoneTrackTransforms(RootBone, ExistingTransforms);
    }

    // Preserve the authored root-motion path. Adding a second synthetic XY
    // translation turns forward clips into diagonal movement.
    Direction = Direction.GetSafeNormal();
    const float Distance = Speed * static_cast<float>(SourceModel->GetPlayLength());
    const FVector SourceRootStart = ExistingTransforms.IsEmpty()
        ? FVector::ZeroVector
        : ExistingTransforms[0].GetTranslation();
    const FVector SourceRootEnd = ExistingTransforms.IsEmpty()
        ? FVector::ZeroVector
        : ExistingTransforms.Last().GetTranslation();
    const FVector SourceRootDelta = SourceRootEnd - SourceRootStart;
    const FVector SourceRootHorizontal(
        SourceRootDelta.X,
        SourceRootDelta.Y,
        0.0f);
    const FVector SourceDirection = SourceRootHorizontal.IsNearlyZero()
        ? FVector(Direction.X, Direction.Y, 0.0f)
        : SourceRootHorizontal.GetSafeNormal();
    const float SourceDistanceSquared = SourceRootHorizontal.SizeSquared();
    TArray<FVector> Positions;
    TArray<FQuat> Rotations;
    TArray<FVector> Scales;
    Positions.Reserve(NumKeys);
    Rotations.Reserve(NumKeys);
    Scales.Reserve(NumKeys);
    for (int32 KeyIndex = 0; KeyIndex < NumKeys; ++KeyIndex)
    {
        const float Alpha = NumKeys > 1
            ? static_cast<float>(KeyIndex) / static_cast<float>(NumKeys - 1)
            : 0.0f;
        const FTransform Base = ExistingTransforms.IsValidIndex(KeyIndex)
            ? ExistingTransforms[KeyIndex]
            : (ExistingTransforms.IsEmpty()
                   ? FTransform::Identity
                   : ExistingTransforms.Last());
        float DistanceAlpha = Alpha;
        float YawDegrees = 0.0f;
        switch (Profile)
        {
        case ERootMotionProfile::Accelerate:
            DistanceAlpha = Alpha * Alpha;
            break;
        case ERootMotionProfile::Decelerate:
            DistanceAlpha = 1.0f - FMath::Square(1.0f - Alpha);
            break;
        case ERootMotionProfile::TurnLeft:
            YawDegrees = -90.0f * Alpha;
            break;
        case ERootMotionProfile::TurnRight:
            YawDegrees = 90.0f * Alpha;
            break;
        default:
            break;
        }
        const FVector SourceDelta = Base.GetTranslation() - SourceRootStart;
        float SourceProgress = Alpha;
        if (SourceDistanceSquared > UE_SMALL_NUMBER)
        {
            SourceProgress = FMath::Clamp(
                FVector::DotProduct(
                    FVector(SourceDelta.X, SourceDelta.Y, 0.0f),
                    SourceRootHorizontal)
                    / SourceDistanceSquared,
                0.0f,
                1.0f);
        }
        float RootMotionProgress = SourceProgress;
        if (Profile == ERootMotionProfile::Accelerate)
        {
            RootMotionProgress = SourceProgress * SourceProgress;
        }
        else if (Profile == ERootMotionProfile::Decelerate)
        {
            RootMotionProgress =
                1.0f - FMath::Square(1.0f - SourceProgress);
        }

        FVector HorizontalTranslation = FVector::ZeroVector;
        if (Profile != ERootMotionProfile::TurnLeft
            && Profile != ERootMotionProfile::TurnRight
            && Distance > UE_SMALL_NUMBER)
        {
            HorizontalTranslation = SourceDirection
                * Distance
                * (SourceDistanceSquared > UE_SMALL_NUMBER
                    ? RootMotionProgress
                    : DistanceAlpha);
        }

        Positions.Add(
            FVector(
                SourceRootStart.X + HorizontalTranslation.X,
                SourceRootStart.Y + HorizontalTranslation.Y,
                Base.GetTranslation().Z));
        Rotations.Add(
            FQuat(FVector::UpVector, FMath::DegreesToRadians(YawDegrees))
            * Base.GetRotation());
        Scales.Add(Base.GetScale3D());
    }

    IAnimationDataController& DataController = Sequence->GetController();
    DataController.OpenBracket(
        NSLOCTEXT("Aociety", "BuildMotionRoot", "Build motion-matching root track"),
        false);
    if (!Model->IsValidBoneTrackName(RootBone))
    {
        DataController.AddBoneCurve(RootBone, false);
    }
    DataController.SetBoneTrackKeys(
        RootBone,
        Positions,
        Rotations,
        Scales,
        false);
    DataController.CloseBracket(false);

    Sequence->bEnableRootMotion = true;
    Sequence->RootMotionRootLock = ERootMotionRootLock::AnimFirstFrame;
    Sequence->bForceRootLock = true;
    Sequence->MarkPackageDirty();
    Sequence->PostEditChange();
    Sequence->WaitOnExistingCompression(true);
    SaveAsset(Sequence);
    UE_LOG(
        LogTemp,
        Display,
        TEXT("[AocietyMotionAssetBuilder] root_motion=%s profile=%d speed=%.1f distance=%.1f keys=%d"),
        *Sequence->GetPathName(),
        static_cast<int32>(Profile),
        Speed,
        Distance,
        NumKeys);
    return Sequence;
}

UPoseSearchSchema* BuildSchema(USkeleton* MannySkeleton)
{
    bool bCreated = false;
    UPoseSearchSchema* Schema = FindOrCreateAsset<UPoseSearchSchema>(
        TEXT("PSS_EcyLocomotion"), bCreated);
    if (bCreated)
    {
        Schema->AddSkeleton(MannySkeleton);
        Schema->AddDefaultChannels();
    }
    Schema->SampleRate = 30;
    Schema->bInjectAdditionalDebugChannels = true;
    Schema->MarkPackageDirty();
    Schema->PostEditChange();
    SaveAsset(Schema);
    UE_LOG(
        LogTemp,
        Display,
        TEXT("[AocietyMotionAssetBuilder] schema=%s created=%s channels=%d cardinality=%d"),
        *Schema->GetPathName(),
        bCreated ? TEXT("true") : TEXT("false"),
        Schema->GetChannels().Num(),
        Schema->SchemaCardinality);
    return Schema;
}

UPoseSearchDatabase* BuildDatabase(
    UPoseSearchSchema* Schema,
    USkeletalMesh* MannyMesh,
    const TArray<UAnimationAsset*>& Animations)
{
    bool bCreated = false;
    UPoseSearchDatabase* Database = FindOrCreateAsset<UPoseSearchDatabase>(
        TEXT("PSDB_EcyLocomotion"), bCreated);
    Database->Schema = Schema;
    Database->PoseSearchMode = EPoseSearchMode::BruteForce;
    Database->PreviewMesh = MannyMesh;
    Database->Tags = {TEXT("Aociety"), TEXT("Ecy"), TEXT("MotionMatching")};

    while (Database->GetNumAnimationAssets() > 0)
    {
        Database->RemoveAnimationAssetAt(Database->GetNumAnimationAssets() - 1);
    }

    for (UAnimationAsset* Animation : Animations)
    {
        if (!Animation)
        {
            continue;
        }

        bool bAlreadyPresent = false;
        for (int32 Index = 0; Index < Database->GetNumAnimationAssets(); ++Index)
        {
            if (Database->GetAnimationAsset(Index) == Animation)
            {
                bAlreadyPresent = true;
                break;
            }
        }
        if (!bAlreadyPresent)
        {
            FPoseSearchDatabaseAnimationAsset Entry;
            Entry.AnimAsset = Animation;
            Database->AddAnimationAsset(Entry);
        }
    }

    Database->MarkPackageDirty();
    Database->PostEditChange();
    SaveAsset(Database);

    using namespace UE::PoseSearch;
    const EAsyncBuildIndexResult BuildResult =
        FAsyncPoseSearchDatabasesManagement::RequestAsyncBuildIndex(
            Database,
            ERequestAsyncBuildFlag::NewRequest
                | ERequestAsyncBuildFlag::WaitForCompletion);
    Database->MarkPackageDirty();
    SaveAsset(Database);
    UE_LOG(
        LogTemp,
        Display,
        TEXT("[AocietyMotionAssetBuilder] database=%s created=%s assets=%d build_result=%d indexed_poses=%d"),
        *Database->GetPathName(),
        bCreated ? TEXT("true") : TEXT("false"),
        Database->GetNumAnimationAssets(),
        static_cast<int32>(BuildResult),
        Database->GetSearchIndex().GetNumPoses());
    return BuildResult == EAsyncBuildIndexResult::Success
        && Database->GetSearchIndex().GetNumPoses() > 0
        ? Database
        : nullptr;
}

UChooserTable* BuildChooser(UPoseSearchDatabase* Database)
{
    bool bCreated = false;
    UChooserTable* Chooser = FindOrCreateAsset<UChooserTable>(
        TEXT("CH_EcyLocomotion"), bCreated);
    Chooser->ResultType = EObjectChooserResultType::ObjectResult;
    Chooser->OutputObjectType = UPoseSearchDatabase::StaticClass();
    Chooser->ResultsStructs.Reset();
    FInstancedStruct Result;
    Result.InitializeAs(FAssetChooser::StaticStruct());
    Result.GetMutable<FAssetChooser>().Asset = Database;
    Chooser->ResultsStructs.Add(MoveTemp(Result));
    Chooser->Compile(true);
    Chooser->MarkPackageDirty();
    SaveAsset(Chooser);
    UE_LOG(
        LogTemp,
        Display,
        TEXT("[AocietyMotionAssetBuilder] chooser=%s created=%s rows=%d result=%s"),
        *Chooser->GetPathName(),
        bCreated ? TEXT("true") : TEXT("false"),
        Chooser->ResultsStructs.Num(),
        *GetNameSafe(Database));
    return Chooser;
}
}

UAocietyMotionAssetBuilderCommandlet::UAocietyMotionAssetBuilderCommandlet()
{
    IsClient = false;
    IsServer = false;
    IsEditor = true;
    LogToConsole = true;
    ShowErrorCount = true;
}

int32 UAocietyMotionAssetBuilderCommandlet::Main(const FString& Params)
{
    UE_LOG(
        LogTemp,
        Display,
        TEXT("[AocietyMotionAssetBuilder] begin params=%s"),
        *Params);

    USkeletalMesh* MannySourceMesh = LoadObject<USkeletalMesh>(
        nullptr,
        TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple"));
    USkeleton* MannySkeleton = LoadObject<USkeleton>(
        nullptr,
        TEXT("/Game/Characters/Mannequins/Meshes/SK_Mannequin.SK_Mannequin"));
    USkeletalMesh* EcyMesh = LoadObject<USkeletalMesh>(
        nullptr,
        TEXT("/Game/Aociety/Characters/Ecy/SK_Ecy.SK_Ecy"));
    if (!MannySourceMesh || !MannySkeleton || !EcyMesh)
    {
        UE_LOG(
            LogTemp,
            Error,
            TEXT("[AocietyMotionAssetBuilder] missing source manny=%s skeleton=%s ecy=%s"),
            *GetNameSafe(MannySourceMesh),
            *GetNameSafe(MannySkeleton),
            *GetNameSafe(EcyMesh));
        return 2;
    }

    USkeletalMesh* MannyMesh = BuildMannyDriverMesh(
        MannySourceMesh, MannySkeleton);

    UIKRigDefinition* MannyRig = BuildMannyRig(MannyMesh);
    UIKRigDefinition* EcyRig = BuildEcyRig(EcyMesh);
    UIKRetargeter* Retargeter = BuildRetargeter(
        MannyRig, EcyRig, MannyMesh, EcyMesh);

    struct FLocomotionAnimation
    {
        const TCHAR* SourcePath;
        const TCHAR* AssetName;
        FVector2D Direction;
        float Speed;
    };

    const TArray<FLocomotionAnimation> LocomotionAnimations = {
        {TEXT("/Game/Characters/Mannequins/Anims/Unarmed/MM_Idle.MM_Idle"), TEXT("MM_Ecy_Idle_RM"), FVector2D::ZeroVector, 0.0f},
        {TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Fwd.MF_Unarmed_Walk_Fwd"), TEXT("MM_Ecy_Walk_Fwd_RM"), FVector2D(1.0f, 0.0f), 180.0f},
        {TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Bwd.MF_Unarmed_Walk_Bwd"), TEXT("MM_Ecy_Walk_Bwd_RM"), FVector2D(-1.0f, 0.0f), 180.0f},
        {TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Left.MF_Unarmed_Walk_Left"), TEXT("MM_Ecy_Walk_Left_RM"), FVector2D(0.0f, -1.0f), 180.0f},
        {TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Right.MF_Unarmed_Walk_Right"), TEXT("MM_Ecy_Walk_Right_RM"), FVector2D(0.0f, 1.0f), 180.0f},
        {TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Fwd_Left.MF_Unarmed_Walk_Fwd_Left"), TEXT("MM_Ecy_Walk_Fwd_Left_RM"), FVector2D(1.0f, -1.0f), 180.0f},
        {TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Fwd_Right.MF_Unarmed_Walk_Fwd_Right"), TEXT("MM_Ecy_Walk_Fwd_Right_RM"), FVector2D(1.0f, 1.0f), 180.0f},
        {TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Bwd_Left.MF_Unarmed_Walk_Bwd_Left"), TEXT("MM_Ecy_Walk_Bwd_Left_RM"), FVector2D(-1.0f, -1.0f), 180.0f},
        {TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Bwd_Right.MF_Unarmed_Walk_Bwd_Right"), TEXT("MM_Ecy_Walk_Bwd_Right_RM"), FVector2D(-1.0f, 1.0f), 180.0f},
        {TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Jog/MF_Unarmed_Jog_Fwd.MF_Unarmed_Jog_Fwd"), TEXT("MM_Ecy_Jog_Fwd_RM"), FVector2D(1.0f, 0.0f), 420.0f},
        {TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Jog/MF_Unarmed_Jog_Bwd.MF_Unarmed_Jog_Bwd"), TEXT("MM_Ecy_Jog_Bwd_RM"), FVector2D(-1.0f, 0.0f), 420.0f},
        {TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Jog/MF_Unarmed_Jog_Left.MF_Unarmed_Jog_Left"), TEXT("MM_Ecy_Jog_Left_RM"), FVector2D(0.0f, -1.0f), 420.0f},
        {TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Jog/MF_Unarmed_Jog_Right.MF_Unarmed_Jog_Right"), TEXT("MM_Ecy_Jog_Right_RM"), FVector2D(0.0f, 1.0f), 420.0f},
        {TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Jog/MF_Unarmed_Jog_Fwd_Left.MF_Unarmed_Jog_Fwd_Left"), TEXT("MM_Ecy_Jog_Fwd_Left_RM"), FVector2D(1.0f, -1.0f), 420.0f},
        {TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Jog/MF_Unarmed_Jog_Fwd_Right.MF_Unarmed_Jog_Fwd_Right"), TEXT("MM_Ecy_Jog_Fwd_Right_RM"), FVector2D(1.0f, 1.0f), 420.0f},
        {TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Jog/MF_Unarmed_Jog_Bwd_Left.MF_Unarmed_Jog_Bwd_Left"), TEXT("MM_Ecy_Jog_Bwd_Left_RM"), FVector2D(-1.0f, -1.0f), 420.0f},
        {TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Jog/MF_Unarmed_Jog_Bwd_Right.MF_Unarmed_Jog_Bwd_Right"), TEXT("MM_Ecy_Jog_Bwd_Right_RM"), FVector2D(-1.0f, 1.0f), 420.0f},
    };

    TArray<UAnimationAsset*> DatabaseAnimations;
    for (const FLocomotionAnimation& Entry : LocomotionAnimations)
    {
        DatabaseAnimations.Add(BuildRootMotionSequence(
            Entry.SourcePath,
            Entry.AssetName,
            Entry.Direction,
            Entry.Speed));
    }
    // Keep only genuine locomotion clips until authored start, stop and pivot
    // animations are available.
    UAnimSequence* JumpAnimation = BuildRootMotionSequence(
        TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Jump/MM_Jump.MM_Jump"),
        TEXT("MM_Ecy_Jump_RM"),
        FVector2D::ZeroVector,
        0.0f);
    UAnimSequence* FallAnimation = BuildRootMotionSequence(
        TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Jump/MM_Fall_Loop.MM_Fall_Loop"),
        TEXT("MM_Ecy_Fall_Loop_RM"),
        FVector2D::ZeroVector,
        0.0f);
    UAnimSequence* LandAnimation = BuildRootMotionSequence(
        TEXT("/Game/Characters/Mannequins/Anims/Unarmed/Jump/MM_Land.MM_Land"),
        TEXT("MM_Ecy_Land_RM"),
        FVector2D::ZeroVector,
        0.0f);

    UPoseSearchSchema* Schema = BuildSchema(MannySkeleton);
    UPoseSearchDatabase* Database = BuildDatabase(
        Schema, MannyMesh, DatabaseAnimations);
    UChooserTable* Chooser = Database ? BuildChooser(Database) : nullptr;

    const bool bSuccess = MannyRig && EcyRig && Retargeter && Schema
        && Database && Chooser && JumpAnimation && FallAnimation && LandAnimation;
    const FString Evidence = FString::Printf(
        TEXT("success=%s\n")
        TEXT("manny_rig=%s\n")
        TEXT("ecy_rig=%s\n")
        TEXT("retargeter=%s\n")
        TEXT("schema=%s\n")
        TEXT("database=%s\n")
        TEXT("chooser=%s\n")
        TEXT("database_assets=%d\n")
        TEXT("indexed_poses=%d\n"),
        bSuccess ? TEXT("true") : TEXT("false"),
        *GetPathNameSafe(MannyRig),
        *GetPathNameSafe(EcyRig),
        *GetPathNameSafe(Retargeter),
        *GetPathNameSafe(Schema),
        *GetPathNameSafe(Database),
        *GetPathNameSafe(Chooser),
        Database ? Database->GetNumAnimationAssets() : 0,
        Database ? Database->GetSearchIndex().GetNumPoses() : 0);
    const FString EvidencePath = FPaths::ProjectSavedDir()
        / TEXT("MotionMatchingAssetBuild.txt");
    FFileHelper::SaveStringToFile(Evidence, *EvidencePath);
    UE_LOG(
        LogTemp,
        Display,
        TEXT("[AocietyMotionAssetBuilder] complete success=%s evidence=%s"),
        bSuccess ? TEXT("true") : TEXT("false"),
        *EvidencePath);
    return bSuccess ? 0 : 3;
}
