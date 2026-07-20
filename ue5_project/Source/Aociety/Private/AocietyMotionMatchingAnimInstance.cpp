// Copyright Aociety. All rights reserved.

#include "AocietyMotionMatchingAnimInstance.h"

#include "Animation/AnimSequence.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Misc/App.h"
#include "PoseSearch/PoseSearchDatabase.h"
#if WITH_EDITOR
#include "PoseSearch/PoseSearchDerivedData.h"
#endif
#include "PoseSearch/PoseSearchIndex.h"

FAocietyMotionMatchingAnimInstanceProxy::FAocietyMotionMatchingAnimInstanceProxy()
{
    ConfigureGraph();
}

FAocietyMotionMatchingAnimInstanceProxy::FAocietyMotionMatchingAnimInstanceProxy(
    UAnimInstance* Instance)
    : FAnimInstanceProxy(Instance)
{
    ConfigureGraph();
}

void FAocietyMotionMatchingAnimInstanceProxy::ConfigureGraph()
{
    MotionMatchingNode.SetMaxActiveBlends(6);

    GroundLocalToComponentNode.LocalPose.SetLinkNode(&MotionMatchingNode);
    StrideWarpingNode.ComponentPose.SetLinkNode(&GroundLocalToComponentNode);
    StrideWarpingNode.Mode = EWarpingEvaluationMode::Manual;
    StrideWarpingNode.StrideDirection = FVector::YAxisVector;
    StrideWarpingNode.PelvisBone.BoneName = TEXT("pelvis");
    StrideWarpingNode.IKFootRootBone.BoneName = TEXT("ik_foot_root");
    StrideWarpingNode.FootDefinitions.Reset();
    for (const TTuple<FName, FName, FName>& Foot : {
             TTuple<FName, FName, FName>(
                 TEXT("ik_foot_l"), TEXT("foot_l"), TEXT("thigh_l")),
             TTuple<FName, FName, FName>(
                 TEXT("ik_foot_r"), TEXT("foot_r"), TEXT("thigh_r")),
         })
    {
        FStrideWarpingFootDefinition Definition;
        Definition.IKFootBone.BoneName = Foot.Get<0>();
        Definition.FKFootBone.BoneName = Foot.Get<1>();
        Definition.ThighBone.BoneName = Foot.Get<2>();
        StrideWarpingNode.FootDefinitions.Add(Definition);
    }
    StrideWarpingNode.StrideScaleModifier.bClampResult = true;
    StrideWarpingNode.StrideScaleModifier.ClampMin = 0.55f;
    StrideWarpingNode.StrideScaleModifier.ClampMax = 1.10f;
    StrideWarpingNode.StrideScaleModifier.bInterpResult = true;
    StrideWarpingNode.StrideScaleModifier.InterpSpeedIncreasing = 8.0f;
    StrideWarpingNode.StrideScaleModifier.InterpSpeedDecreasing = 10.0f;
    GroundComponentToLocalNode.ComponentPose.SetLinkNode(&StrideWarpingNode);

    GroundAirBlendNode.A.SetLinkNode(&GroundComponentToLocalNode);
    GroundAirBlendNode.B.SetLinkNode(&AirSequenceNode);
    GroundAirBlendNode.AlphaInputType = EAnimAlphaInputType::Bool;
    GroundAirBlendNode.bAlphaBoolEnabled =
        AirState != EAocietyAirLocomotionState::Grounded;
    GroundAirBlendNode.AlphaBoolBlend.BlendInTime = 0.12f;
    GroundAirBlendNode.AlphaBoolBlend.BlendOutTime = 0.16f;
    GroundAirBlendNode.AlphaBoolBlend.BlendOption = EAlphaBlendOption::Cubic;

    PoseHistoryNode.Source.SetLinkNode(&GroundAirBlendNode);
    PoseHistoryNode.PoseCount = 24;
    PoseHistoryNode.SamplingInterval = 1.0f / 30.0f;
    PoseHistoryNode.bGenerateTrajectory = true;
    PoseHistoryNode.TrajectoryHistoryCount = 12;
    PoseHistoryNode.TrajectoryPredictionCount = 10;
    PoseHistoryNode.PredictionSamplingInterval = 0.16f;
    PoseHistoryNode.TrajectoryData.RotateTowardsMovementSpeed = 12.0f;
    PoseHistoryNode.TrajectoryData.MaxControllerYawRate = 540.0f;
    PoseHistoryNode.TrajectoryData.BendVelocityTowardsAcceleration = 0.35f;
}

void FAocietyMotionMatchingAnimInstanceProxy::Initialize(UAnimInstance* Instance)
{
    ConfigureGraph();
    FAnimInstanceProxy::Initialize(Instance);
}

FAnimNode_Base* FAocietyMotionMatchingAnimInstanceProxy::GetCustomRootNode()
{
    return &PoseHistoryNode;
}

void FAocietyMotionMatchingAnimInstanceProxy::GetCustomNodes(
    TArray<FAnimNode_Base*>& OutNodes)
{
    OutNodes.Add(&MotionMatchingNode);
    OutNodes.Add(&GroundLocalToComponentNode);
    OutNodes.Add(&StrideWarpingNode);
    OutNodes.Add(&GroundComponentToLocalNode);
    OutNodes.Add(&AirSequenceNode);
    OutNodes.Add(&GroundAirBlendNode);
    OutNodes.Add(&PoseHistoryNode);
}

void FAocietyMotionMatchingAnimInstanceProxy::SetLocomotionSpeed(float InSpeed)
{
    const UObject* SelectedAnimation =
        MotionMatchingNode.GetMotionMatchingState().SearchResult.SelectedAnim;
    const FString SelectedName = GetNameSafe(SelectedAnimation);
    float AuthoredPoseSpeed = 0.0f;
    if (SelectedName.Contains(TEXT("Jog")))
    {
        AuthoredPoseSpeed = 600.0f;
    }
    else if (SelectedName.Contains(TEXT("Walk")))
    {
        AuthoredPoseSpeed = 300.0f;
    }

    StrideWarpingNode.StrideScale = AuthoredPoseSpeed > UE_SMALL_NUMBER
        && InSpeed > 8.0f
        ? FMath::Clamp(InSpeed / AuthoredPoseSpeed, 0.55f, 1.10f)
        : 1.0f;
}

void FAocietyMotionMatchingAnimInstanceProxy::SetDatabase(
    UPoseSearchDatabase* InDatabase)
{
    Database = InDatabase;
    if (InDatabase)
    {
        MotionMatchingNode.SetDatabaseToSearch(
            InDatabase,
            EPoseSearchInterruptMode::InterruptOnDatabaseChangeAndInvalidateContinuingPose);
    }
    else
    {
        MotionMatchingNode.ResetDatabasesToSearch(
            EPoseSearchInterruptMode::ForceInterruptAndInvalidateContinuingPose);
    }
}

void FAocietyMotionMatchingAnimInstanceProxy::ConfigureAirAnimations(
    UAnimSequenceBase* InJumpAnimation,
    UAnimSequenceBase* InFallAnimation,
    UAnimSequenceBase* InLandAnimation)
{
    JumpAnimation = InJumpAnimation;
    FallAnimation = InFallAnimation;
    LandAnimation = InLandAnimation;
    if (!AirSequenceNode.GetSequence())
    {
        AirSequenceNode.SetSequence(InJumpAnimation);
        AirSequenceNode.SetLoopAnimation(false);
    }
}

void FAocietyMotionMatchingAnimInstanceProxy::SetAirState(
    EAocietyAirLocomotionState InState)
{
    GroundAirBlendNode.bAlphaBoolEnabled =
        InState != EAocietyAirLocomotionState::Grounded;
    if (AirState == InState)
    {
        return;
    }

    AirState = InState;
    UAnimSequenceBase* DesiredAnimation = nullptr;
    bool bLoop = false;
    switch (AirState)
    {
    case EAocietyAirLocomotionState::Jumping:
        DesiredAnimation = JumpAnimation.Get();
        break;
    case EAocietyAirLocomotionState::Falling:
        DesiredAnimation = FallAnimation.Get();
        bLoop = true;
        break;
    case EAocietyAirLocomotionState::Landing:
        DesiredAnimation = LandAnimation.Get();
        break;
    default:
        break;
    }

    if (DesiredAnimation)
    {
        AirSequenceNode.SetSequence(DesiredAnimation);
        AirSequenceNode.SetLoopAnimation(bLoop);
        AirSequenceNode.SetAccumulatedTime(0.0f);
    }
}

FString FAocietyMotionMatchingAnimInstanceProxy::DescribeState() const
{
    const FPoseSearchBlueprintResult& Result =
        MotionMatchingNode.GetMotionMatchingState().SearchResult;
    const TCHAR* AirStateName = TEXT("grounded");
    switch (AirState)
    {
    case EAocietyAirLocomotionState::Jumping:
        AirStateName = TEXT("jumping");
        break;
    case EAocietyAirLocomotionState::Falling:
        AirStateName = TEXT("falling");
        break;
    case EAocietyAirLocomotionState::Landing:
        AirStateName = TEXT("landing");
        break;
    default:
        break;
    }
    return FString::Printf(
        TEXT("database=%s indexed_poses=%d selected=%s time=%.3f cost=%.4f continuing=%s stride_scale=%.2f air_state=%s air_sequence=%s"),
        *GetNameSafe(Database.Get()),
        GetIndexedPoseCount(),
        *GetNameSafe(Result.SelectedAnim),
        Result.SelectedTime,
        Result.SearchCost,
        Result.bIsContinuingPoseSearch ? TEXT("true") : TEXT("false"),
        StrideWarpingNode.StrideScale,
        AirStateName,
        *GetNameSafe(AirSequenceNode.GetSequence()));
}

int32 FAocietyMotionMatchingAnimInstanceProxy::GetIndexedPoseCount() const
{
    const UPoseSearchDatabase* CurrentDatabase = Database.Get();
    if (!CurrentDatabase)
    {
        return 0;
    }

#if WITH_EDITOR
    if (!FApp::IsGame())
    {
        using namespace UE::PoseSearch;
        if (FAsyncPoseSearchDatabasesManagement::RequestAsyncBuildIndex(
                CurrentDatabase,
                ERequestAsyncBuildFlag::ContinueRequest)
            != EAsyncBuildIndexResult::Success)
        {
            return 0;
        }
    }
#endif

    return CurrentDatabase->GetSearchIndex().GetNumPoses();
}

UAocietyMotionMatchingAnimInstance::UAocietyMotionMatchingAnimInstance()
{
    SetRootMotionMode(ERootMotionMode::IgnoreRootMotion);
}

void UAocietyMotionMatchingAnimInstance::NativeInitializeAnimation()
{
    Super::NativeInitializeAnimation();

    JumpAnimation = LoadObject<UAnimSequenceBase>(
        nullptr,
        TEXT("/Game/Aociety/MotionMatching/Animations/MM_Ecy_Jump_RM.MM_Ecy_Jump_RM"));
    FallAnimation = LoadObject<UAnimSequenceBase>(
        nullptr,
        TEXT("/Game/Aociety/MotionMatching/Animations/MM_Ecy_Fall_Loop_RM.MM_Ecy_Fall_Loop_RM"));
    LandAnimation = LoadObject<UAnimSequenceBase>(
        nullptr,
        TEXT("/Game/Aociety/MotionMatching/Animations/MM_Ecy_Land_RM.MM_Ecy_Land_RM"));
    GetProxyOnGameThread<FAocietyMotionMatchingAnimInstanceProxy>()
        .ConfigureAirAnimations(JumpAnimation, FallAnimation, LandAnimation);
}

void UAocietyMotionMatchingAnimInstance::NativeUpdateAnimation(float DeltaSeconds)
{
    Super::NativeUpdateAnimation(DeltaSeconds);

    EAocietyAirLocomotionState DesiredState =
        EAocietyAirLocomotionState::Grounded;
    const ACharacter* Character = Cast<ACharacter>(TryGetPawnOwner());
    const UCharacterMovementComponent* Movement = Character
        ? Character->GetCharacterMovement()
        : nullptr;
    const bool bIsFalling = Movement && Movement->IsFalling();
    if (bIsFalling)
    {
        LandingTimeRemaining = 0.0f;
        DesiredState = Character->GetVelocity().Z > 80.0f
            ? EAocietyAirLocomotionState::Jumping
            : EAocietyAirLocomotionState::Falling;
    }
    else if (bWasFalling)
    {
        LandingTimeRemaining = 0.38f;
        DesiredState = EAocietyAirLocomotionState::Landing;
    }
    else if (LandingTimeRemaining > 0.0f)
    {
        LandingTimeRemaining = FMath::Max(
            0.0f,
            LandingTimeRemaining - DeltaSeconds);
        DesiredState = EAocietyAirLocomotionState::Landing;
    }

    bWasFalling = bIsFalling;
    FAocietyMotionMatchingAnimInstanceProxy& Proxy =
        GetProxyOnGameThread<FAocietyMotionMatchingAnimInstanceProxy>();
    Proxy.SetLocomotionSpeed(
        Character ? Character->GetVelocity().Size2D() : 0.0f);
    Proxy.SetAirState(DesiredState);
}

void UAocietyMotionMatchingAnimInstance::ConfigureDatabase(
    UPoseSearchDatabase* InDatabase)
{
    MotionDatabase = InDatabase;
    GetProxyOnGameThread<FAocietyMotionMatchingAnimInstanceProxy>().SetDatabase(
        InDatabase);
}

FString UAocietyMotionMatchingAnimInstance::GetMotionMatchingState() const
{
    return GetProxyOnGameThread<FAocietyMotionMatchingAnimInstanceProxy>()
        .DescribeState();
}

int32 UAocietyMotionMatchingAnimInstance::GetIndexedPoseCount() const
{
    return GetProxyOnGameThread<FAocietyMotionMatchingAnimInstanceProxy>()
        .GetIndexedPoseCount();
}

FAnimInstanceProxy* UAocietyMotionMatchingAnimInstance::CreateAnimInstanceProxy()
{
    return new FAocietyMotionMatchingAnimInstanceProxy(this);
}
