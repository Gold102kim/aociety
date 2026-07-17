// Copyright Aociety. All rights reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "AocietyNPCCharacter.generated.h"

class UTextRenderComponent;
class UWidgetComponent;
class USkeletalMeshComponent;

UCLASS()
class AOCIETY_API AAocietyNPCCharacter : public ACharacter
{
    GENERATED_BODY()

public:
    AAocietyNPCCharacter();

    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;

    USkeletalMeshComponent* GetResidentVisual() const { return ResidentVisual; }

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Aociety|NPC")
    FString NpcId = TEXT("npc_01");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Aociety|NPC")
    FString DisplayName = TEXT("居民");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Aociety|NPC")
    float WanderRadius = 420.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Aociety|NPC")
    float WanderSpeed = 105.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Aociety|NPC")
    bool bEnableWander = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Aociety|Animation")
    TObjectPtr<class UAnimSequence> IdleAnimation;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Aociety|Animation")
    TObjectPtr<class UAnimSequence> WalkAnimation;

    UFUNCTION(BlueprintCallable, Category="Aociety|NPC")
    void ShowDialogue(
        const FString& Line,
        const FString& Source,
        const FString& Model,
        float Duration);

    UFUNCTION(BlueprintCallable, Category="Aociety|NPC")
    void ShowThinking();

    UFUNCTION(BlueprintCallable, Category="Aociety|NPC")
    void ShowListening(const FString& SpeakerName, float Duration = 30.0f);

    UFUNCTION(BlueprintCallable, Category="Aociety|NPC")
    void FocusOnActor(AActor* OtherActor, float Duration = 30.0f);

private:
    void PickWanderTarget();
    void BeginWanderPause();
    void PlayLocomotionAnimation(bool bMoving);
    void ClearDialogue();

    UPROPERTY(VisibleAnywhere, Category="Aociety|NPC")
    TObjectPtr<UTextRenderComponent> Nameplate;

    UPROPERTY(VisibleAnywhere, Category="Aociety|NPC")
    TObjectPtr<UTextRenderComponent> SpeechBubble;

    UPROPERTY(VisibleAnywhere, Category="Aociety|NPC")
    TObjectPtr<UWidgetComponent> SolidBubble;

    UPROPERTY(VisibleAnywhere, Category="Aociety|NPC")
    TObjectPtr<USkeletalMeshComponent> ResidentVisual;

    FVector HomeLocation = FVector::ZeroVector;
    FVector WanderTarget = FVector::ZeroVector;
    float TimeUntilNextTarget = 0.0f;
    FTimerHandle DialogueTimer;
    bool bWasMoving = false;
    bool bWaitingAtTarget = true;
    double FocusEndTime = 0.0;
    TWeakObjectPtr<AActor> FocusActor;

    UPROPERTY(Transient)
    TObjectPtr<class UAnimSequence> ActiveAnimation;
};
