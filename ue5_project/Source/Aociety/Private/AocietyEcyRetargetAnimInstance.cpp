// Copyright Aociety. All rights reserved.

#include "AocietyEcyRetargetAnimInstance.h"

#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Retargeter/IKRetargeter.h"

FAocietyEcyRetargetAnimInstanceProxy::FAocietyEcyRetargetAnimInstanceProxy()
{
    ConfigureGraph();
}

FAocietyEcyRetargetAnimInstanceProxy::FAocietyEcyRetargetAnimInstanceProxy(
    UAnimInstance* Instance)
    : FAnimInstanceProxy(Instance)
{
    ConfigureGraph();
}

void FAocietyEcyRetargetAnimInstanceProxy::ConfigureGraph()
{
    RetargetNode.RetargetFrom = ERetargetSourceMode::CustomSkeletalMeshComponent;
    RetargetNode.bSuppressWarnings = false;

    LocalToComponentNode.LocalPose.SetLinkNode(&RetargetNode);
    RootTranslationFix.ComponentPose.SetLinkNode(&LocalToComponentNode);
    RootTranslationFix.BoneToModify.BoneName = TEXT("root_218");
    RootTranslationFix.TranslationMode = EBoneModificationMode::BMM_Replace;
    RootTranslationFix.TranslationSpace = EBoneControlSpace::BCS_ParentBoneSpace;
    RootTranslationFix.RotationMode = EBoneModificationMode::BMM_Ignore;
    RootTranslationFix.ScaleMode = EBoneModificationMode::BMM_Ignore;
    RootTranslationFix.Alpha = 1.0f;

    HipsTranslationFix.ComponentPose.SetLinkNode(&RootTranslationFix);
    HipsTranslationFix.BoneToModify.BoneName = TEXT("hips_217");
    HipsTranslationFix.TranslationMode = EBoneModificationMode::BMM_Replace;
    HipsTranslationFix.TranslationSpace = EBoneControlSpace::BCS_ParentBoneSpace;
    HipsTranslationFix.RotationMode = EBoneModificationMode::BMM_Ignore;
    HipsTranslationFix.ScaleMode = EBoneModificationMode::BMM_Ignore;
    HipsTranslationFix.Alpha = 1.0f;

    ComponentToLocalNode.ComponentPose.SetLinkNode(&HipsTranslationFix);
}

void FAocietyEcyRetargetAnimInstanceProxy::Initialize(UAnimInstance* Instance)
{
    ConfigureGraph();
    FAnimInstanceProxy::Initialize(Instance);
}

FAnimNode_Base* FAocietyEcyRetargetAnimInstanceProxy::GetCustomRootNode()
{
    return &ComponentToLocalNode;
}

void FAocietyEcyRetargetAnimInstanceProxy::GetCustomNodes(
    TArray<FAnimNode_Base*>& OutNodes)
{
    OutNodes.Add(&RetargetNode);
    OutNodes.Add(&LocalToComponentNode);
    OutNodes.Add(&RootTranslationFix);
    OutNodes.Add(&HipsTranslationFix);
    OutNodes.Add(&ComponentToLocalNode);
}

bool FAocietyEcyRetargetAnimInstanceProxy::Configure(
    UIKRetargeter* InRetargeter,
    USkeletalMeshComponent* SourceMesh,
    USkeletalMeshComponent* TargetMesh)
{
    RetargetNode.IKRetargeterAsset = InRetargeter;
    RetargetNode.SourceMeshComponent = SourceMesh;
    bRootTranslationFixReady = false;
    bHipsTranslationFixReady = false;
    RootReferenceTranslation = FVector::ZeroVector;
    HipsReferenceTranslation = FVector::ZeroVector;

    if (TargetMesh)
    {
        if (const USkeletalMesh* TargetAsset = TargetMesh->GetSkeletalMeshAsset())
        {
            const FReferenceSkeleton& ReferenceSkeleton = TargetAsset->GetRefSkeleton();
            const int32 RootIndex = ReferenceSkeleton.FindBoneIndex(TEXT("root_218"));
            const int32 HipsIndex = ReferenceSkeleton.FindBoneIndex(TEXT("hips_217"));
            if (RootIndex != INDEX_NONE)
            {
                RootReferenceTranslation =
                    ReferenceSkeleton.GetRefBonePose()[RootIndex].GetTranslation();
                RootTranslationFix.Translation = RootReferenceTranslation;
                bRootTranslationFixReady = true;
            }
            if (HipsIndex != INDEX_NONE)
            {
                HipsReferenceTranslation =
                    ReferenceSkeleton.GetRefBonePose()[HipsIndex].GetTranslation();
                HipsTranslationFix.Translation = HipsReferenceTranslation;
                bHipsTranslationFixReady = true;
            }
        }
    }

    return InRetargeter && SourceMesh && TargetMesh
        && bRootTranslationFixReady && bHipsTranslationFixReady
        ? RetargetNode.EnsureProcessorIsInitialized(TargetMesh)
        : false;
}

FString FAocietyEcyRetargetAnimInstanceProxy::DescribeState() const
{
    return FString::Printf(
        TEXT("retargeter=%s source=%s root_fix=%s root_ref=%s hips_fix=%s hips_ref=%s secondary_motion=disabled"),
        *GetNameSafe(RetargetNode.IKRetargeterAsset),
        *GetNameSafe(RetargetNode.SourceMeshComponent.Get()),
        bRootTranslationFixReady ? TEXT("true") : TEXT("false"),
        *RootReferenceTranslation.ToCompactString(),
        bHipsTranslationFixReady ? TEXT("true") : TEXT("false"),
        *HipsReferenceTranslation.ToCompactString());
}

bool UAocietyEcyRetargetAnimInstance::ConfigureRetarget(
    UIKRetargeter* InRetargeter,
    USkeletalMeshComponent* SourceMesh)
{
    RetargeterAsset = InRetargeter;
    MotionSourceMesh = SourceMesh;
    return GetProxyOnGameThread<FAocietyEcyRetargetAnimInstanceProxy>().Configure(
        InRetargeter,
        SourceMesh,
        GetSkelMeshComponent());
}

FString UAocietyEcyRetargetAnimInstance::GetRetargetState() const
{
    return GetProxyOnGameThread<FAocietyEcyRetargetAnimInstanceProxy>()
        .DescribeState();
}

FAnimInstanceProxy* UAocietyEcyRetargetAnimInstance::CreateAnimInstanceProxy()
{
    return new FAocietyEcyRetargetAnimInstanceProxy(this);
}
