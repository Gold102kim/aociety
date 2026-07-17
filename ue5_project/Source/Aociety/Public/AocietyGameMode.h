// Copyright Aociety. 保留所有权利.
// AocietyGameMode - 主游戏模式

#pragma once

#include "CoreMinimal.h"
#include "AocietyClientSubsystem.h"
#include "GameFramework/GameModeBase.h"
#include "AocietyGameMode.generated.h"

UCLASS()
class AOCIETY_API AAocietyGameMode : public AGameModeBase
{
    GENERATED_BODY()

public:
    AAocietyGameMode();

    virtual void BeginPlay() override;

private:
    UFUNCTION()
    void HandleDialogueTrigger(AActor* TriggerActor, AActor* OtherActor);

    UFUNCTION()
    void HandleDialogueTriggerEnd(AActor* TriggerActor, AActor* OtherActor);

    UFUNCTION()
    void HandleNPCDialogue(FAocietyNPCDialogue Dialogue);

    void StartAmbientNPCConversation();

    TMap<TWeakObjectPtr<AActor>, double> LastTriggerTimes;
    FTimerHandle AmbientConversationTimer;
    bool bAmbientSpeakerIsNpc01 = true;
};
