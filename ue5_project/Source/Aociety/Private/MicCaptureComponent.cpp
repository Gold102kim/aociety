// SPDX-License-Identifier: MIT
// Aociety UE5.8 麦克风采集组件 - 实现
// 路径: Source/Aociety/Private/MicCaptureComponent.cpp

#include "MicCaptureComponent.h"
#include "Engine/World.h"
#include "TimerManager.h"
#include "AudioCaptureCore.h"

#if defined(WITH_RTAUDIO) && WITH_RTAUDIO
#include "AudioCapture.h"
#endif

UMicCaptureComponent::UMicCaptureComponent()
{
    PrimaryComponentTick.bCanEverTick = false;
}

bool UMicCaptureComponent::StartCapture()
{
    // The UE adapter is not implemented. Do not report a successful recording
    // or send generated silence to the hardware emotion service as real audio.
    UE_LOG(LogTemp, Warning, TEXT("[Mic] Game-side capture unavailable; use the external hardware capture service"));
    return false;
}

void UMicCaptureComponent::StopCapture()
{
    bCapturing = false;
    if (UWorld* World = GetWorld())
    {
        World->GetTimerManager().ClearTimer(MicTimer);
    }
}

void UMicCaptureComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    StopCapture();
    Super::EndPlay(Reason);
}

void UMicCaptureComponent::TickChunk()
{
    TArray<uint8> Data = CapturePCMChunk();
    if (Data.Num() > 0)
    {
        OnMicChunk.Broadcast(Data);
    }
}

TArray<uint8> UMicCaptureComponent::CapturePCMChunk()
{
    return {};
}
