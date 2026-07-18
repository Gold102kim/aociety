// Copyright Aociety. All rights reserved.

#include "AocietyEcyRetargetAnimInstance.h"

#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Retargeter/IKRetargeter.h"

namespace
{
void ConfigureDynamicsChain(
    FAnimNode_AnimDynamics& Node,
    const TArray<FName>& Bones,
    float Alpha,
    float GravityScale,
    float ConeAngle)
{
    check(Bones.Num() >= 2);
    Node.BoundBone.BoneName = Bones[0];
    Node.ChainEnd.BoneName = Bones.Last();
    Node.bChain = true;
    Node.bDoUpdate = true;
    Node.bDoEval = true;
    Node.SimulationSpace = AnimPhysSimSpaceType::Component;
    Node.GravityScale = GravityScale;
    Node.Alpha = Alpha;
    Node.bOverrideLinearDamping = true;
    Node.LinearDampingOverride = 0.96f;
    Node.bOverrideAngularDamping = true;
    Node.AngularDampingOverride = 0.96f;
    Node.bOverrideAngularBias = true;
    Node.AngularBiasOverride = 0.82f;
    Node.NumSolverIterationsPreUpdate = 8;
    Node.NumSolverIterationsPostUpdate = 4;
    Node.ComponentLinearAccScale = FVector(0.004f);
    Node.ComponentLinearVelScale = FVector(0.002f);
    Node.ComponentAppliedLinearAccClamp = FVector(6.0f);
    Node.PhysicsBodyDefinitions.Reset(Bones.Num());

    for (const FName BoneName : Bones)
    {
        FAnimPhysBodyDefinition Body;
        Body.BoundBone.BoneName = BoneName;
        Body.BoxExtents = FVector(1.5f, 2.5f, 1.5f);
        Body.ConstraintSetup.AngularConstraintType =
            AnimPhysAngularConstraintType::Cone;
        Body.ConstraintSetup.ConeAngle = ConeAngle;
        Body.ConstraintSetup.AngularLimitsMin = FVector(-ConeAngle);
        Body.ConstraintSetup.AngularLimitsMax = FVector(ConeAngle);
        Node.PhysicsBodyDefinitions.Add(Body);
    }
}
}

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
    HipsTranslationFix.ComponentPose.SetLinkNode(&LocalToComponentNode);
    HipsTranslationFix.BoneToModify.BoneName = TEXT("hips_217");
    HipsTranslationFix.TranslationMode = EBoneModificationMode::BMM_Replace;
    HipsTranslationFix.TranslationSpace = EBoneControlSpace::BCS_ParentBoneSpace;
    HipsTranslationFix.RotationMode = EBoneModificationMode::BMM_Ignore;
    HipsTranslationFix.ScaleMode = EBoneModificationMode::BMM_Ignore;
    HipsTranslationFix.Alpha = 1.0f;

    LeftSkirtDynamics.ComponentPose.SetLinkNode(&HipsTranslationFix);
    RightSkirtDynamics.ComponentPose.SetLinkNode(&LeftSkirtDynamics);
    HairDynamics.ComponentPose.SetLinkNode(&RightSkirtDynamics);
    ComponentToLocalNode.ComponentPose.SetLinkNode(&HairDynamics);

    ConfigureDynamicsChain(
        LeftSkirtDynamics,
        {
            TEXT("sk_L_154"),
            TEXT("sk_L_006_153"),
            TEXT("sk_L_003_152"),
            TEXT("sk_L_009_151"),
            TEXT("sk_L_012_150"),
        },
        0.045f,
        0.02f,
        3.0f);
    ConfigureDynamicsChain(
        RightSkirtDynamics,
        {
            TEXT("sk_R_169"),
            TEXT("sk_R_006_168"),
            TEXT("sk_R_003_167"),
            TEXT("sk_R_009_166"),
            TEXT("sk_R_012_165"),
        },
        0.045f,
        0.02f,
        3.0f);
    ConfigureDynamicsChain(
        HairDynamics,
        {
            TEXT("hair_h_R_62"),
            TEXT("hair_h_R_001_61"),
            TEXT("hair_h_001_R_60"),
            TEXT("hair_h_001_R_001_59"),
            TEXT("hair_h_001_R_002_58"),
        },
        0.05f,
        0.015f,
        3.0f);
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
    OutNodes.Add(&HipsTranslationFix);
    OutNodes.Add(&LeftSkirtDynamics);
    OutNodes.Add(&RightSkirtDynamics);
    OutNodes.Add(&HairDynamics);
    OutNodes.Add(&ComponentToLocalNode);
}

bool FAocietyEcyRetargetAnimInstanceProxy::Configure(
    UIKRetargeter* InRetargeter,
    USkeletalMeshComponent* SourceMesh,
    USkeletalMeshComponent* TargetMesh)
{
    RetargetNode.IKRetargeterAsset = InRetargeter;
    RetargetNode.SourceMeshComponent = SourceMesh;
    bHipsTranslationFixReady = false;
    HipsReferenceTranslation = FVector::ZeroVector;

    if (TargetMesh)
    {
        if (const USkeletalMesh* TargetAsset = TargetMesh->GetSkeletalMeshAsset())
        {
            const FReferenceSkeleton& ReferenceSkeleton = TargetAsset->GetRefSkeleton();
            const int32 HipsIndex = ReferenceSkeleton.FindBoneIndex(TEXT("hips_217"));
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
        && bHipsTranslationFixReady
        ? RetargetNode.EnsureProcessorIsInitialized(TargetMesh)
        : false;
}

FString FAocietyEcyRetargetAnimInstanceProxy::DescribeState() const
{
    return FString::Printf(
        TEXT("retargeter=%s source=%s hips_fix=%s hips_ref=%s skirt_l_bodies=%d skirt_r_bodies=%d hair_bodies=%d"),
        *GetNameSafe(RetargetNode.IKRetargeterAsset),
        *GetNameSafe(RetargetNode.SourceMeshComponent.Get()),
        bHipsTranslationFixReady ? TEXT("true") : TEXT("false"),
        *HipsReferenceTranslation.ToCompactString(),
        LeftSkirtDynamics.GetNumBodies(),
        RightSkirtDynamics.GetNumBodies(),
        HairDynamics.GetNumBodies());
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
