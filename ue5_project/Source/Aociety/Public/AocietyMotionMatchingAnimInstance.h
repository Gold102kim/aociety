// Copyright Aociety. All rights reserved.

#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimInstanceProxy.h"
#include "Animation/AnimNode_SequencePlayer.h"
#include "Animation/AnimNodeSpaceConversions.h"
#include "AnimNodes/AnimNode_TwoWayBlend.h"
#include "BoneControllers/AnimNode_StrideWarping.h"
#include "PoseSearch/AnimNode_MotionMatching.h"
#include "PoseSearch/AnimNode_PoseSearchHistoryCollector.h"
#include "AocietyMotionMatchingAnimInstance.generated.h"

class UPoseSearchDatabase;
class UAnimSequenceBase;

enum class EAocietyAirLocomotionState : uint8
{
    Grounded,
    Jumping,
    Falling,
    Landing,
};

USTRUCT()
struct AOCIETY_API FAocietyMotionMatchingAnimInstanceProxy : public FAnimInstanceProxy
{
    GENERATED_BODY()

    FAocietyMotionMatchingAnimInstanceProxy();
    explicit FAocietyMotionMatchingAnimInstanceProxy(UAnimInstance* Instance);

    virtual void Initialize(UAnimInstance* Instance) override;
    virtual FAnimNode_Base* GetCustomRootNode() override;
    virtual void GetCustomNodes(TArray<FAnimNode_Base*>& OutNodes) override;

    void SetDatabase(UPoseSearchDatabase* InDatabase);
    void ConfigureAirAnimations(
        UAnimSequenceBase* InJumpAnimation,
        UAnimSequenceBase* InFallAnimation,
        UAnimSequenceBase* InLandAnimation);
    void SetLocomotionSpeed(float InSpeed);
    void SetAirState(EAocietyAirLocomotionState InState);
    FString DescribeState() const;
    int32 GetIndexedPoseCount() const;

private:
    void ConfigureGraph();

    FAnimNode_MotionMatching MotionMatchingNode;
    FAnimNode_ConvertLocalToComponentSpace GroundLocalToComponentNode;
    FAnimNode_StrideWarping StrideWarpingNode;
    FAnimNode_ConvertComponentToLocalSpace GroundComponentToLocalNode;
    FAnimNode_SequencePlayer_Standalone AirSequenceNode;
    FAnimNode_TwoWayBlend GroundAirBlendNode;
    FAnimNode_PoseSearchHistoryCollector PoseHistoryNode;
    TWeakObjectPtr<UPoseSearchDatabase> Database;
    TWeakObjectPtr<UAnimSequenceBase> JumpAnimation;
    TWeakObjectPtr<UAnimSequenceBase> FallAnimation;
    TWeakObjectPtr<UAnimSequenceBase> LandAnimation;
    EAocietyAirLocomotionState AirState = EAocietyAirLocomotionState::Grounded;
};

UCLASS(Transient, NotBlueprintable)
class AOCIETY_API UAocietyMotionMatchingAnimInstance : public UAnimInstance
{
    GENERATED_BODY()

public:
    UAocietyMotionMatchingAnimInstance();
    void ConfigureDatabase(UPoseSearchDatabase* InDatabase);
    FString GetMotionMatchingState() const;
    int32 GetIndexedPoseCount() const;

    virtual void NativeInitializeAnimation() override;
    virtual void NativeUpdateAnimation(float DeltaSeconds) override;

protected:
    virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;

private:
    UPROPERTY(Transient)
    TObjectPtr<UPoseSearchDatabase> MotionDatabase;

    UPROPERTY(Transient)
    TObjectPtr<UAnimSequenceBase> JumpAnimation;

    UPROPERTY(Transient)
    TObjectPtr<UAnimSequenceBase> FallAnimation;

    UPROPERTY(Transient)
    TObjectPtr<UAnimSequenceBase> LandAnimation;

    bool bWasFalling = false;
    float LandingTimeRemaining = 0.0f;
};
