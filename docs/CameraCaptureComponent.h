// SPDX-License-Identifier: MIT
// Aociety UE5.8 摄像头采集组件 (基于 OpenCV UE Plugin 或 USB Camera)
// 路径: Source/Aociety/Public/CameraCaptureComponent.h

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "CameraCaptureComponent.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnFrameCaptured, const TArray<uint8>&, JPEGBytes);

UCLASS(ClassGroup=(Aociety), meta=(BlueprintSpawnableComponent))
class UCameraCaptureComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UCameraCaptureComponent();

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera")
    int32 CameraID = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera")
    int32 Width = 640;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera")
    int32 Height = 480;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera")
    float FPS = 15.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Camera")
    int32 JPEGQuality = 75;

    UPROPERTY(BlueprintAssignable, Category="Camera")
    FOnFrameCaptured OnFrameCaptured;

    UFUNCTION(BlueprintCallable, Category="Camera")
    bool StartCapture();

    UFUNCTION(BlueprintCallable, Category="Camera")
    void StopCapture();

    UFUNCTION(BlueprintCallable, BlueprintPure, Category="Camera")
    bool IsCapturing() const { return bCapturing; }

protected:
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;

private:
    bool bCapturing = false;
    void* CameraHandle = nullptr; // 兼容 OpenCV UE Plugin / FFrameGrabber
    FTimerHandle FrameTimer;

    void TickFrame();
    TArray<uint8> CaptureFrameToJPEG();
};
