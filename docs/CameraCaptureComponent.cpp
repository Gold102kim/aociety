// SPDX-License-Identifier: MIT
// Aociety UE5.8 摄像头采集组件 - 实现
// 路径: Source/Aociety/Private/CameraCaptureComponent.cpp

#include "CameraCaptureComponent.h"
#include "Engine/World.h"
#include "TimerManager.h"
#include "Misc/Base64.h"
#include "Misc/FileHelper.h"
#include "IImageWrapper.h"
#include "IImageWrapperModule.h"
#include "Modules/ModuleManager.h"

#if WITH_OPENCV_PLUGIN
// 需要 OpenCV UE Plugin
#include "PreOpenCVHeaders.h"
#include "opencv2/opencv.hpp"
#endif

UCameraCaptureComponent::UCameraCaptureComponent()
{
    PrimaryComponentTick.bCanEverTick = false;
}

bool UCameraCaptureComponent::StartCapture()
{
    if (bCapturing) return true;

#if WITH_OPENCV_PLUGIN
    cv::VideoCapture Cap(CameraID);
    if (!Cap.isOpened()) return false;

    Cap.set(cv::CAP_PROP_FRAME_WIDTH, Width);
    Cap.set(cv::CAP_PROP_FRAME_HEIGHT, Height);
    Cap.set(cv::CAP_PROP_FPS, FPS);

    CameraHandle = new cv::VideoCapture(Cap);
    bCapturing = true;

    if (UWorld* World = GetWorld())
    {
        World->GetTimerManager().SetTimer(
            FrameTimer, this, &UCameraCaptureComponent::TickFrame,
            1.0f / FPS, true);
    }
    return true;
#else
    // 无OpenCV，使用UE的内置方式或发出警告
    UE_LOG(LogTemp, Warning, TEXT("[Camera] 请安装 OpenCV UE Plugin"));
    return false;
#endif
}

void UCameraCaptureComponent::StopCapture()
{
    bCapturing = false;
    if (UWorld* World = GetWorld())
    {
        World->GetTimerManager().ClearTimer(FrameTimer);
    }
#if WITH_OPENCV_PLUGIN
    if (CameraHandle)
    {
        delete (cv::VideoCapture*)CameraHandle;
        CameraHandle = nullptr;
    }
#endif
}

void UCameraCaptureComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    StopCapture();
    Super::EndPlay(Reason);
}

void UCameraCaptureComponent::TickFrame()
{
    TArray<uint8> JPEG = CaptureFrameToJPEG();
    if (JPEG.Num() > 0)
    {
        OnFrameCaptured.Broadcast(JPEG);
    }
}

TArray<uint8> UCameraCaptureComponent::CaptureFrameToJPEG()
{
    TArray<uint8> Result;
#if WITH_OPENCV_PLUGIN
    cv::VideoCapture* Cap = (cv::VideoCapture*)CameraHandle;
    if (!Cap || !Cap->isOpened()) return Result;

    cv::Mat Frame;
    if (!Cap->read(Frame)) return Result;

    std::vector<uchar> Buf;
    cv::imencode(".jpg", Frame, Buf, { cv::IMWRITE_JPEG_QUALITY, JPEGQuality });

    Result.SetNumUninitialized(Buf.size());
    FMemory::Memcpy(Result.GetData(), Buf.data(), Buf.size());
#endif
    return Result;
}
