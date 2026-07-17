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
    if (bCapturing) return true;

    bCapturing = true;
    if (UWorld* World = GetWorld())
    {
        World->GetTimerManager().SetTimer(
            MicTimer, this, &UMicCaptureComponent::TickChunk,
            ChunkSeconds, true);
    }
    return true;
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
    int32 NumSamples = SampleRate * ChunkSeconds;
    TArray<uint8> PCM;
    PCM.SetNumZeroed(NumSamples * 2); // 16-bit mono

#if defined(WITH_RTAUDIO) && WITH_RTAUDIO
    // 通过 UE AudioCapture 录制
    // 实际实现需要 RAudio::FAudioCapture 实例化
    // 这一段请根据项目实际使用的捕获方式完成
#endif

    return PCM;
}
