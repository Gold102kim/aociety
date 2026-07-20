// Copyright Aociety. All rights reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "AocietyMainMenuGameMode.generated.h"

UCLASS()
class AOCIETY_API AAocietyMainMenuGameMode : public AGameModeBase
{
    GENERATED_BODY()

public:
    AAocietyMainMenuGameMode();

    virtual void BeginPlay() override;
    void EnterWorld();

private:
    void CaptureMenuAudit();

    FTimerHandle AutoEnterTimer;
    FTimerHandle AuditTimer;
    bool bTransitionStarted = false;
};
