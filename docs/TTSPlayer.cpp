// SPDX-License-Identifier: MIT
// Aociety UE5.8 甜女声播放器 - 实现
// 路径: Source/Aociety/Private/TTSPlayer.cpp

#include "TTSPlayer.h"
#include "AocietyClientSubsystem.h"
#include "Engine/GameInstance.h"
#include "Sound/SoundWave.h"
#include "Kismet/GameplayStatics.h"
#include "Components/AudioComponent.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

UTTSPlayer::UTTSPlayer()
{
    PrimaryComponentTick.bCanEverTick = false;
}

void UTTSPlayer::PlaySweetVoiceFromBase64(const FString& AudioBase64)
{
    if (AudioBase64.IsEmpty()) return;

    TArray<uint8> Bytes;
    FBase64::Decode(AudioBase64, Bytes);
    if (Bytes.Num() == 0) return;

    // 写入临时 MP3 文件
    FString TempPath = FPaths::ProjectIntermediateDir() / TEXT("AocietyTTS") /
                       FString::Printf(TEXT("sweet_%s.mp3"),
                           *FGuid::NewGuid().ToString(EGuidFormats::Short));

    if (!FFileHelper::SaveArrayToFile(Bytes, *TempPath))
    {
        UE_LOG(LogTemp, Error, TEXT("[TTS] Failed to save: %s"), *TempPath);
        return;
    }

    PlayMP3File(TempPath);
}

void UTTSPlayer::PlayMP3File(const FString& FilePath)
{
    // UE 5.4+ 内置 MP3 解码
    USoundWave* Wave = NewObject<USoundWave>();
    if (Wave->ImportAudioFromFile(*FilePath))
    {
        ActiveAudioComp = UGameplayStatics::SpawnSound2D(this, Wave);
        CachedAudioFilePath = FilePath;

        // 清理老文件
        if (FPaths::FileExists(FilePath))
        {
            // 10 秒后删除
            FTimerHandle Handle;
            if (UWorld* W = GetWorld())
            {
                W->GetTimerManager().SetTimer(Handle,
                    [FilePath]() { IFileManager::Get().Delete(*FilePath, false, true); },
                    10.0f, false);
            }
        }
    }
}
