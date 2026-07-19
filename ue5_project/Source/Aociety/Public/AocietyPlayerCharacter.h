// Copyright Aociety. All rights reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "AocietyPlayerCharacter.generated.h"

class UCameraComponent;
class USpringArmComponent;
class USkeletalMeshComponent;
class UPoseSearchDatabase;
class UIKRetargeter;
class AAocietyNPCCharacter;
class UAocietyConversationWidget;

UCLASS()
class AOCIETY_API AAocietyPlayerCharacter : public ACharacter
{
    GENERATED_BODY()

public:
    AAocietyPlayerCharacter();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;

    void SetNearbyNPC(AAocietyNPCCharacter* NPC);
    void ClearNearbyNPC(AAocietyNPCCharacter* NPC);

protected:
    virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;

private:
    void MoveForward(float Value);
    void MoveRight(float Value);
    void Interact();
    void ToggleInbox();
    void CloseConversation();
    void RunRuntimeAudit(float DeltaSeconds);
    void CaptureRuntimeAuditScreenshot(const TCHAR* FileName) const;

    UPROPERTY(VisibleAnywhere, Category="Aociety|Camera")
    TObjectPtr<USpringArmComponent> CameraBoom;

    UPROPERTY(VisibleAnywhere, Category="Aociety|Camera")
    TObjectPtr<UCameraComponent> FollowCamera;

    UPROPERTY(VisibleAnywhere, Category="Aociety|Animation")
    TObjectPtr<USkeletalMeshComponent> MotionDriverMesh;

    UPROPERTY(Transient)
    TObjectPtr<UPoseSearchDatabase> MotionDatabase;

    UPROPERTY(Transient)
    TObjectPtr<UIKRetargeter> EcyRetargeter;

    UPROPERTY(Transient)
    TObjectPtr<UAocietyConversationWidget> ConversationWidget;

    TWeakObjectPtr<AAocietyNPCCharacter> NearbyNPC;
    float MotionEvidenceAccumulator = 0.0f;
    FVector PreviousLeftFootLocation = FVector::ZeroVector;
    FVector PreviousActorLocation = FVector::ZeroVector;
    bool bHasPreviousLeftFootLocation = false;
    bool bHasPreviousActorLocation = false;
    bool bInitialCameraPitchApplied = false;
    bool bRuntimeAuditEnabled = false;
    bool bRuntimeAuditIdleCaptured = false;
    bool bRuntimeAuditWalkCaptured = false;
    bool bRuntimeAuditJumpStarted = false;
    bool bRuntimeAuditJumpCaptured = false;
    bool bRuntimeAuditFinalCaptured = false;
    bool bRuntimeAuditNPCViewSet = false;
    bool bRuntimeAuditNPCThinkingCaptured = false;
    bool bRuntimeAuditNPCReplyCaptured = false;
    bool bRuntimeAuditPlayerInteractionStarted = false;
    bool bRuntimeAuditPlayerPendingCaptured = false;
    bool bRuntimeAuditPlayerReplyCaptured = false;
    float RuntimeAuditElapsed = 0.0f;
};
