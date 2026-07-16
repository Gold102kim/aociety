// Copyright Aociety. All rights reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "AocietyNPCCharacter.generated.h"

class UTextRenderComponent;
class UWidgetComponent;

UCLASS()
class AOCIETY_API AAocietyNPCCharacter : public ACharacter
{
    GENERATED_BODY()

public:
    AAocietyNPCCharacter();

    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;

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
    void ShowDialogue(const FString& Line, float Duration = 10.0f);

    UFUNCTION(BlueprintCallable, Category="Aociety|NPC")
    void ShowThinking();

private:
    void PickWanderTarget();
    void ClearDialogue();

    UPROPERTY(VisibleAnywhere, Category="Aociety|NPC")
    TObjectPtr<UTextRenderComponent> Nameplate;

    UPROPERTY(VisibleAnywhere, Category="Aociety|NPC")
    TObjectPtr<UTextRenderComponent> SpeechBubble;

    UPROPERTY(VisibleAnywhere, Category="Aociety|NPC")
    TObjectPtr<UWidgetComponent> SolidBubble;

    FVector HomeLocation = FVector::ZeroVector;
    FVector WanderTarget = FVector::ZeroVector;
    float TimeUntilNextTarget = 0.0f;
    FTimerHandle DialogueTimer;
    bool bWasMoving = false;
};
