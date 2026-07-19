// Copyright Aociety. All rights reserved.

#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimInstanceProxy.h"
#include "Animation/AnimNodeSpaceConversions.h"
#include "AnimNodes/AnimNode_RetargetPoseFromMesh.h"
#include "BoneControllers/AnimNode_ModifyBone.h"
#include "AocietyEcyRetargetAnimInstance.generated.h"

class UIKRetargeter;
class USkeletalMeshComponent;

USTRUCT()
struct AOCIETY_API FAocietyEcyRetargetAnimInstanceProxy : public FAnimInstanceProxy
{
    GENERATED_BODY()

    FAocietyEcyRetargetAnimInstanceProxy();
    explicit FAocietyEcyRetargetAnimInstanceProxy(UAnimInstance* Instance);

    virtual void Initialize(UAnimInstance* Instance) override;
    virtual FAnimNode_Base* GetCustomRootNode() override;
    virtual void GetCustomNodes(TArray<FAnimNode_Base*>& OutNodes) override;

    bool Configure(
        UIKRetargeter* InRetargeter,
        USkeletalMeshComponent* SourceMesh,
        USkeletalMeshComponent* TargetMesh);
    FString DescribeState() const;

private:
    void ConfigureGraph();

    FAnimNode_RetargetPoseFromMesh RetargetNode;
    FAnimNode_ConvertLocalToComponentSpace LocalToComponentNode;
    FAnimNode_ModifyBone RootTranslationFix;
    FAnimNode_ModifyBone HipsTranslationFix;
    FAnimNode_ConvertComponentToLocalSpace ComponentToLocalNode;
    FVector RootReferenceTranslation = FVector::ZeroVector;
    FVector HipsReferenceTranslation = FVector::ZeroVector;
    bool bRootTranslationFixReady = false;
    bool bHipsTranslationFixReady = false;
};

UCLASS(Transient, NotBlueprintable)
class AOCIETY_API UAocietyEcyRetargetAnimInstance : public UAnimInstance
{
    GENERATED_BODY()

public:
    bool ConfigureRetarget(
        UIKRetargeter* InRetargeter,
        USkeletalMeshComponent* SourceMesh);
    FString GetRetargetState() const;

protected:
    virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;

private:
    UPROPERTY(Transient)
    TObjectPtr<UIKRetargeter> RetargeterAsset;

    UPROPERTY(Transient)
    TObjectPtr<USkeletalMeshComponent> MotionSourceMesh;
};
