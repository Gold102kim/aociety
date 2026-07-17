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

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Aociety")
    FString BackendURL = TEXT("http://127.0.0.1:8000");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Aociety")
    bool bAutoStartCapture = true;
};
