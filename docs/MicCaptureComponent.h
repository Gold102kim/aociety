// SPDX-License-Identifier: MIT
// Aociety UE5.8 麦克风采集组件
// 路径: Source/Aociety/Public/MicCaptureComponent.h

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "MicCaptureComponent.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnMicChunk, const TArray<uint8>&, PCM16);

UCLASS(ClassGroup=(Aociety), meta=(BlueprintSpawnableComponent))
class UMicCaptureComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UMicCaptureComponent();

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Mic")
    int32 SampleRate = 16000;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Mic")
    float ChunkSeconds = 1.0f;

    UPROPERTY(BlueprintAssignable, Category="Mic")
    FOnMicChunk OnMicChunk;

    UFUNCTION(BlueprintCallable, Category="Mic")
    bool StartCapture();

    UFUNCTION(BlueprintCallable, Category="Mic")
    void StopCapture();

protected:
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;

private:
    bool bCapturing = false;
    FTimerHandle MicTimer;

    void TickChunk();
    TArray<uint8> CapturePCMChunk();
};
