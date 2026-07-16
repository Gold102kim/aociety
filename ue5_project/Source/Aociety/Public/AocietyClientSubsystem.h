// SPDX-License-Identifier: MIT
// Aociety UE5.8 客户端子系统 - 完整实现
// 路径: Source/Aociety/Public/AocietyClientSubsystem.h

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Interfaces/IHttpRequest.h"
#include "AocietyClientSubsystem.generated.h"

USTRUCT(BlueprintType)
struct FAocietyEmotion
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category="Aociety") FString Emotion = TEXT("neutral");
    UPROPERTY(BlueprintReadOnly, Category="Aociety") float Valence = 0.5f;
    UPROPERTY(BlueprintReadOnly, Category="Aociety") float Arousal = 0.0f;
    UPROPERTY(BlueprintReadOnly, Category="Aociety") float SupportNeed = 0.0f;
    UPROPERTY(BlueprintReadOnly, Category="Aociety") FString Trend = TEXT("stable");
    UPROPERTY(BlueprintReadOnly, Category="Aociety") float ValenceDelta = 0.0f;
    UPROPERTY(BlueprintReadOnly, Category="Aociety") float ArousalDelta = 0.0f;
    UPROPERTY(BlueprintReadOnly, Category="Aociety") bool bDegraded = true;
};

USTRUCT(BlueprintType)
struct FNpcCareAudio
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly) FString NpcLine;
    UPROPERTY(BlueprintReadOnly) FString Action;
    UPROPERTY(BlueprintReadOnly) FString CareLevel;       // nudge/care/guard
    UPROPERTY(BlueprintReadOnly) float Duration = 5.0f;
    UPROPERTY(BlueprintReadOnly) FString VoiceName;        // xiaoxiao
    UPROPERTY(BlueprintReadOnly) FString VoiceNameCN;      // 晓晓
    UPROPERTY(BlueprintReadOnly) FString AudioBase64;      // MP3 base64
};

USTRUCT(BlueprintType)
struct FAocietyWorldSnapshot
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly) int32 Day = 1;
    UPROPERTY(BlueprintReadOnly) int32 ClockMinutes = 480;
    UPROPERTY(BlueprintReadOnly) FString TimePeriod;
};

USTRUCT(BlueprintType)
struct FAocietyNPCInfo
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly) FString Id;
    UPROPERTY(BlueprintReadOnly) FString Name;
    UPROPERTY(BlueprintReadOnly) FString District;
    UPROPERTY(BlueprintReadOnly) FString Mood;
    UPROPERTY(BlueprintReadOnly) float PositionX = 0.0f;
    UPROPERTY(BlueprintReadOnly) float PositionY = 0.0f;
};

USTRUCT(BlueprintType)
struct FAocietyNPCDialogue
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category="Aociety|NPC") FString NpcId;
    UPROPERTY(BlueprintReadOnly, Category="Aociety|NPC") FString Message;
    UPROPERTY(BlueprintReadOnly, Category="Aociety|NPC") FString TopicId;
    UPROPERTY(BlueprintReadOnly, Category="Aociety|NPC") FString Mood;
    UPROPERTY(BlueprintReadOnly, Category="Aociety|NPC") FString Action;
    UPROPERTY(BlueprintReadOnly, Category="Aociety|NPC") FString Source;
    UPROPERTY(BlueprintReadOnly, Category="Aociety|NPC") FString Model;
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnAocietyEmotion, FAocietyEmotion, Emotion);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnAocietyCare, FNpcCareAudio, Care);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnAocietyWorld, FAocietyWorldSnapshot, World);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnAocietyTranscript, FString, Text, FString, Source);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnAocietyNPCDialogue, FAocietyNPCDialogue, Dialogue);

UCLASS()
class AOCIETY_API UAocietyClientSubsystem : public UGameInstanceSubsystem
{
    GENERATED_BODY()

public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;

    // ─── 服务端配置 ───
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Aociety|Config")
    FString BackendURL = TEXT("http://127.0.0.1:8000");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Aociety|Config")
    float HeartbeatInterval = 2.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Aociety|Config")
    bool bAutoConnect = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Aociety|Config")
    FString PreferredTTSVoice = TEXT("xiaoxiao");

    // ─── 事件 ───
    UPROPERTY(BlueprintAssignable, Category="Aociety|Events")
    FOnAocietyEmotion OnEmotionUpdated;

    UPROPERTY(BlueprintAssignable, Category="Aociety|Events")
    FOnAocietyCare OnCareTriggered;

    UPROPERTY(BlueprintAssignable, Category="Aociety|Events")
    FOnAocietyWorld OnWorldUpdated;

    UPROPERTY(BlueprintAssignable, Category="Aociety|Events")
    FOnAocietyTranscript OnTranscript;

    UPROPERTY(BlueprintAssignable, Category="Aociety|Events")
    FOnAocietyNPCDialogue OnNPCDialogue;

    // ─── 连接管理 ───
    UFUNCTION(BlueprintCallable, Category="Aociety|Network")
    bool Connect();

    UFUNCTION(BlueprintCallable, Category="Aociety|Network")
    void Disconnect();

    UFUNCTION(BlueprintCallable, Category="Aociety|Network")
    bool IsConnected() const;

    // ─── 实时数据推送 (每帧调用) ───
    UFUNCTION(BlueprintCallable, Category="Aociety|Capture")
    void PushCameraFrame(const TArray<uint8>& JPEGBytes, const FString& TextHint = TEXT(""));

    UFUNCTION(BlueprintCallable, Category="Aociety|Capture")
    void PushAudioChunk(const TArray<uint8>& PCM16Bytes);

    UFUNCTION(BlueprintCallable, Category="Aociety|Capture")
    void PushTextHint(const FString& Text);

    // ─── HTTP 调用 ───
    UFUNCTION(BlueprintCallable, Category="Aociety|Emotion")
    void RequestCurrentEmotion();

    UFUNCTION(BlueprintCallable, Category="Aociety|World")
    void RequestWorldState();

    UFUNCTION(BlueprintCallable, Category="Aociety|World")
    void RequestNPCList();

    UFUNCTION(BlueprintCallable, Category="Aociety|World")
    void RequestNPCCare(const FString& NpcId);

    // Send player input to the in-game GLM NPC agent. The backend also
    // receives the latest affect state and returns a world-aware reply.
    UFUNCTION(BlueprintCallable, Category="Aociety|NPC")
    void RequestNPCDialogue(const FString& NpcId, const FString& PlayerInput,
                            const FString& District = TEXT(""),
                            const FString& TopicId = TEXT(""));

    UFUNCTION(BlueprintCallable, Category="Aociety|World")
    void RequestWorldAction(const FString& ActionType, const FString& District,
                           const TMap<FString, FString>& Payload);

    // ─── TTS ───
    UFUNCTION(BlueprintCallable, Category="Aociety|TTS")
    void SynthesizeTTS(const FString& Text, const FString& VoiceName = TEXT("xiaoxiao"));

    UFUNCTION(BlueprintCallable, Category="Aociety|TTS")
    void SetTTSVoice(const FString& VoiceName);

    UFUNCTION(BlueprintCallable, Category="Aociety|TTS")
    TArray<FString> ListTTSVoices() const;

    UFUNCTION(BlueprintCallable, Category="Aociety|TTS")
    FString GetVoiceCNName(const FString& VoiceKey) const;

    // ─── 性格评估 ───
    UFUNCTION(BlueprintCallable, Category="Aociety|Assessment")
    void StartAssessment();

    UFUNCTION(BlueprintCallable, Category="Aociety|Assessment")
    void SubmitAssessmentTurn(const FString& SessionId, const FString& UserInput);

    UFUNCTION(BlueprintCallable, Category="Aociety|Assessment")
    void FinishAssessment(const FString& SessionId);

    // ─── 工具 ───
    UFUNCTION(BlueprintCallable, Category="Aociety|Utils")
    FString ColorHexFromValence(float Valence) const;

    UFUNCTION(BlueprintCallable, Category="Aociety|Utils")
    bool ShouldTriggerCare() const;

private:
    FAocietyEmotion LastEmotion;
    TSharedPtr<class IWebSocket> WS;

    FString CurrentSessionId;
    bool bIsConnected = false;

    FTimerHandle Timer_Heartbeat;
    FTimerHandle Timer_Reconnect;

    void EnsureConnection();
    void OnHttpDone(FHttpRequestPtr Req, FHttpResponsePtr Resp, bool bOK, FName Endpoint);
    void OnWSMessage(const FString& Msg);
    void EmitEmotionIfChanged(const FAocietyEmotion& New);
    void EmitCareFromJson(const TSharedPtr<class FJsonObject>& Json);
    void StartTimer();
    void StopTimer();

    static TArray<uint8> DecodeBase64(const FString& B64);
};
