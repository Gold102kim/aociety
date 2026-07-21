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
    virtual void Tick(float DeltaSeconds) override;

private:
    UFUNCTION()
    void HandleDialogueTrigger(AActor* TriggerActor, AActor* OtherActor);

    UFUNCTION()
    void HandleDialogueTriggerEnd(AActor* TriggerActor, AActor* OtherActor);

    UFUNCTION()
    void HandleNPCDialogue(FAocietyNPCDialogue Dialogue);

    void StartAmbientNPCConversation();
    void UpdateWorldEnvironment(float DeltaSeconds);
    void InitializeWorldEnvironment();

    TMap<TWeakObjectPtr<AActor>, double> LastTriggerTimes;
    FTimerHandle AmbientConversationTimer;
    bool bAmbientSpeakerIsNpc01 = true;

    float WorldClockMinutes = 8.0f * 60.0f;
    float WorldDayLengthSeconds = 600.0f;
    float WeatherElapsedSeconds = 0.0f;
    int32 WeatherState = 0;
    bool bWorldEnvironmentInitialized = false;
    TWeakObjectPtr<class ADirectionalLight> SunLight;
    TWeakObjectPtr<class ASkyLight> SkyLight;
    TWeakObjectPtr<class AExponentialHeightFog> HeightFog;
    TArray<TWeakObjectPtr<class ULightComponent>> NightLights;
    TMap<TWeakObjectPtr<class ULightComponent>, float> OriginalLightIntensities;

    UPROPERTY(Transient)
    TObjectPtr<class UNiagaraComponent> WeatherParticles;

};
