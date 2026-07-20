// Copyright Aociety. 保留所有权利.
// BP_AocietyGameInstance - 自动连接到后端

#pragma once

#include "CoreMinimal.h"
#include "Engine/GameInstance.h"
#include "AocietyGameInstance.generated.h"

UCLASS()
class AOCIETY_API UAocietyGameInstance : public UGameInstance
{
    GENERATED_BODY()

public:
    virtual void Init() override;
    virtual void Shutdown() override;

    // Forest resident/world service.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Aociety")
    FString BackendURL = TEXT("http://127.0.0.1:8000");

    // Hardware-side emotion/TTS/assessment service.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Aociety")
    FString CareBackendURL = TEXT("http://127.0.0.1:8010");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Aociety")
    bool bAutoStartCapture = true;

    UPROPERTY(BlueprintReadOnly, Category="Aociety|Launcher")
    bool bLauncherSessionValid = false;

    UPROPERTY(BlueprintReadOnly, Category="Aociety|Launcher")
    FString LauncherSessionError;

    UPROPERTY(BlueprintReadOnly, Category="Aociety|Launcher")
    FString LauncherLaunchId;

    UPROPERTY(BlueprintReadOnly, Category="Aociety|Launcher")
    FString LauncherAccountId;

    UPROPERTY(BlueprintReadOnly, Category="Aociety|Launcher")
    FString LauncherDisplayName;

    UPROPERTY(BlueprintReadOnly, Category="Aociety|Launcher")
    FString LauncherAgentId;

    UPROPERTY(BlueprintReadOnly, Category="Aociety|Launcher")
    FString LauncherBaseModelId;

private:
    bool LoadLauncherSession();
};
