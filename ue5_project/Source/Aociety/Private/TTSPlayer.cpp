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
    // UE 5.8 no longer exposes USoundWave::ImportAudioFromFile. Keep the
    // downloaded voice file for a runtime decoder while dialogue and subtitles
    // remain fully functional.
    CachedAudioFilePath = FilePath;
    UE_LOG(LogTemp, Verbose, TEXT("[TTS] Voice cached for runtime decoder: %s"), *FilePath);
}
