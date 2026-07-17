// SPDX-License-Identifier: MIT
// Aociety UE5.8 甜女声播放器
// 路径: Source/Aociety/Private/TTSPlayer.h

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "TTSPlayer.generated.h"

UCLASS(ClassGroup=(Aociety))
class UTTSPlayer : public UActorComponent
{
    GENERATED_BODY()

public:
    UTTSPlayer();

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="TTS")
    FString CachedAudioFilePath;

    UFUNCTION(BlueprintCallable, Category="TTS")
    void PlaySweetVoiceFromBase64(const FString& AudioBase64);

    UFUNCTION(BlueprintCallable, Category="TTS")
    void PlayMP3File(const FString& FilePath);

protected:
    UPROPERTY()
    class UAudioComponent* ActiveAudioComp = nullptr;
};
