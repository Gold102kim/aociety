# Aociety 情感计算系统 - UE5.8 对接完整指南

> 本文档保留情感系统的详细实现参考。当前架构已拆分：居民/世界服务使用 `8000`，情感/TTS/评估服务使用 `8010`。文中的情感接口示例应使用 `CareBackendURL=http://127.0.0.1:8010`。

---

## 📋 架构概览

```
┌───────────────────────────────────────────────────────────┐
│                   Unreal Engine 5.8                       │
│                                                          │
│  CameraCapture (WebCam 0) ──────►  JPEG frame ──┐        │
│  MicCapture (Default) ───────────► PCM16 ────┐  │        │
│                                              │  │        │
│  Bone Mesh / Pose Component ───────────────┐  │  │        │
│                                            │  │  │        │
│                                            ▼  ▼  ▼        │
│                                    ┌──────────────────┐   │
│                                    │ AocietyClientSub.│   │
│                                    │  (C++/BP)        │   │
│                                    └────────┬─────────┘   │
│                                             │             │
│  ┌──────────────────────────────────────────┤             │
│  │   EmotionUpdate Event                     │             │
│  │   NPCProactiveCare Event                  │             │
│  │   TTSSynthComplete Event                  │             │
│  │   WorldStateUpdated Event                 │             │
│  └──────────────────────────────────────────┘             │
└─────────────────────────┬─────────────────────────────────┘
                          │ HTTP REST + WebSocket
┌─────────────────────────▼─────────────────────────────────┐
│     Python Backend (FastAPI @ 127.0.0.1:8000)            │
│     ... (Python services)                                  │
└───────────────────────────────────────────────────────────┘
```

---

## 🔧 1. C++ 类 - AocietyClientSubsystem

这是核心 UE 类，处理所有通信逻辑。

### `Source/Aociety/Public/AocietyClientSubsystem.h`

```cpp
#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Interfaces/IHttpRequest.h"
#include "Modules/ModuleManager.h"
#include "AocietyClientSubsystem.generated.h"

USTRUCT(BlueprintType)
struct FAocietyEmotion
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly) FString Emotion;
    UPROPERTY(BlueprintReadOnly) float Valence = 0.5f;
    UPROPERTY(BlueprintReadOnly) float Arousal = 0.0f;
    UPROPERTY(BlueprintReadOnly) float SupportNeed = 0.0f;
    UPROPERTY(BlueprintReadOnly) FString Trend;
    UPROPERTY(BlueprintReadOnly) TArray<float> ValenceDelta;
    UPROPERTY(BlueprintReadOnly) TArray<FString> TopCandidates;
    UPROPERTY(BlueprintReadOnly) bool bDegraded = false;
};

USTRUCT(BlueprintType)
struct FNpcCareResponse
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly) FString NpcLine;
    UPROPERTY(BlueprintReadOnly) FString Action;
    UPROPERTY(BlueprintReadOnly) FString CareLevel;
    UPROPERTY(BlueprintReadOnly) float Duration = 5.0f;
    UPROPERTY(BlueprintReadOnly) FString VoiceName;       // "xiaoxiao"
    UPROPERTY(BlueprintReadOnly) FString VoiceNameCN;     // "晓晓"
    UPROPERTY(BlueprintReadOnly) TArray<uint8> AudioData;  // MP3 bytes
};

USTRUCT(BlueprintType)
struct FAocietyWorldState
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly) int32 Day = 1;
    UPROPERTY(BlueprintReadOnly) int32 ClockMinutes = 480;
    UPROPERTY(BlueprintReadOnly) FString TimePeriod;
    UPROPERTY(BlueprintReadOnly) TArray<FAocietyNPC> NPCs;
};

USTRUCT(BlueprintType)
struct FAocietyNPC
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly) FString NpcId;
    UPROPERTY(BlueprintReadOnly) FString Name;
    UPROPERTY(BlueprintReadOnly) FString District;
    UPROPERTY(BlueprintReadOnly) FString Mood;
    UPROPERTY(BlueprintReadOnly) FString Activity;
};

// Events
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnEmotionUpdated, FAocietyEmotion, Emotion);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnCareTriggered, FNpcCareResponse, Care);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnTTSReady, FNpcCareResponse, Care);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnWorldUpdated, FAocietyWorldState, World);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnTranscript, FString, Text);

UCLASS()
class AOCITY_API UAocietyClientSubsystem : public UGameInstanceSubsystem
{
    GENERATED_BODY()

public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;

    // ═══ 配置 ═══
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString BackendURL = TEXT("http://127.0.0.1:8000");
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float EmotionUpdateInterval = 2.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) bool bAutoStart = true;

    // ═══ 事件 ═══
    UPROPERTY(BlueprintAssignable) FOnEmotionUpdated OnEmotionUpdated;
    UPROPERTY(BlueprintAssignable) FOnCareTriggered OnCareTriggered;
    UPROPERTY(BlueprintAssignable) FOnTTSReady OnTTSReady;
    UPROPERTY(BlueprintAssignable) FOnWorldUpdated OnWorldUpdated;
    UPROPERTY(BlueprintAssignable) FOnTranscript OnTranscript;

    // ═══ 摄像头/麦克风流 ═══
    UFUNCTION(BlueprintCallable, Category="Aociety|Capture")
    void StartCapture(int32 CameraID = 0, int32 Width = 640, int32 Height = 480);

    UFUNCTION(BlueprintCallable, Category="Aociety|Emotion")
    void PushCameraFrame(const TArray<uint8>& JPEGBytes, const FString& TextHint = TEXT(""));

    UFUNCTION(BlueprintCallable, Category="Aociety|Emotion")
    void PushAudioChunk(const TArray<uint8>& PCM16Bytes);

    UFUNCTION(BlueprintCallable, Category="Aociety|Emotion")
    void PushTextHint(const FString& Text);

    // ═══ WebSocket 实时流 ═══
    UFUNCTION(BlueprintCallable, Category="Aociety|Network")
    bool ConnectWebSocket();

    UFUNCTION(BlueprintCallable, Category="Aociety|Network")
    void DisconnectWebSocket();

    // ═══ HTTP 调用 ═══
    UFUNCTION(BlueprintCallable, Category="Aociety|Emotion")
    void RequestCurrentEmotion();

    UFUNCTION(BlueprintCallable, Category="Aociety|Network")
    void RequestWorldState();

    UFUNCTION(BlueprintCallable, Category="Aociety|Network")
    void RequestNPCCare(const FString& NpcId);

    // ═══ TTS ═══
    UFUNCTION(BlueprintCallable, Category="Aociety|TTS")
    void SynthesizeTTS(const FString& Text, const FString& VoiceName = TEXT("xiaoxiao"));

    UFUNCTION(BlueprintCallable, Category="Aociety|TTS")
    void SetTTSVoice(const FString& VoiceName);

    UFUNCTION(BlueprintCallable, Category="Aociety|TTS")
    TArray<FString> ListTTSVoices() const;

    // ═══ 性格评估 ═══
    UFUNCTION(BlueprintCallable, Category="Aociety|Assessment")
    void StartAssessment();

    UFUNCTION(BlueprintCallable, Category="Aociety|Assessment")
    void SubmitAssessmentTurn(const FString& SessionId, const FString& UserInput);

private:
    // 心跳定时器
    FTimerHandle HeartbeatTimer;
    FTimerHandle CaptureTimer;

    // WebSocket
    TSharedPtr<class IWebSocket> WebSocket;

    // 上次情感帧 (用于趋势对比)
    FAocietyEmotion LastEmotion;

    // 内部辅助
    void OnHttpResponse(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bSuccess, FName Endpoint);
    void OnWebSocketMessage(const FString& Message);
    void EmitEmotionIfChanged(const FAocietyEmotion& NewEmotion);
    void CheckCareAutoTrigger();
};
```

### `Source/Aociety/Private/AocietyClientSubsystem.cpp`

```cpp
#include "AocietyClientSubsystem.h"
#include "HttpModule.h"
#include "Interfaces/IHttpResponse.h"
#include "Json.h"
#include "JsonUtilities.h"
#include "TimerManager.h"
#include "Misc/Base64.h"
#include "Misc/Paths.h"
#include "HAL/PlatformFilemanager.h"
#include "IPlatformFile.h"

DEFINE_LOG_CATEGORY_STATIC(LogAociety, Log, All);

// ═══ 生命周期 ═══

void UAocietyClientSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);

    UE_LOG(LogAociety, Log, TEXT("[Aociety] Subsystem initialized, backend=%s"), *BackendURL);

    if (bAutoStart)
    {
        ConnectWebSocket();
        StartCapture(0, 640, 480);
    }
}

void UAocietyClientSubsystem::Deinitialize()
{
    DisconnectWebSocket();
    Super::Deinitialize();
}

// ═══ 摄像头推送（每秒约15帧） ═══

void UAocietyClientSubsystem::StartCapture(int32 CameraID, int32 Width, int32 Height)
{
    UE_LOG(LogAociety, Log, TEXT("[Aociety] StartCapture %dx%d @ camera %d"), Width, Height, CameraID);

    if (UWorld* World = GetWorld())
    {
        World->GetTimerManager().SetTimer(
            CaptureTimer,
            [this]()
            {
                // 在UE5中使用 FFrameGrabber 或 USB Camera 插件获取摄像头帧
                // 这里留给项目的具体实现 - 本类提供 API 入口
                // 实际帧捕获代码应该调用并 PushCameraFrame
            },
            1.0f / 15.0f,
            true
        );
    }
}

void UAocietyClientSubsystem::PushCameraFrame(const TArray<uint8>& JPEGBytes, const FString& TextHint)
{
    if (JPEGBytes.Num() == 0) return;

    FString Base64 = FBase64::Encode(JPEGBytes);

    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
    Request->SetURL(BackendURL + TEXT("/emotion/analyze"));
    Request->SetVerb(TEXT("POST"));
    Request->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    Request->SetContentAsString(
        FString::Printf(TEXT("{\"image_base64\":\"%s\",\"text_hint\":\"%s\",\"timestamp_ms\":%lld}"),
            *Base64, *TextHint, FDateTime::UtcNow().GetTicks() / 1000)
    );
    Request->OnProcessRequestComplete().BindUObject(this, &UAocietyClientSubsystem::OnHttpResponse, FName("emotion"));
    Request->ProcessRequest();
}

void UAocietyClientSubsystem::PushAudioChunk(const TArray<uint8>& PCM16Bytes)
{
    if (PCM16Bytes.Num() == 0) return;
    FString Base64 = FBase64::Encode(PCM16Bytes);

    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
    Request->SetURL(BackendURL + TEXT("/emotion/analyze"));
    Request->SetVerb(TEXT("POST"));
    Request->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    Request->SetContentAsString(
        FString::Printf(TEXT("{\"audio_base64\":\"%s\",\"timestamp_ms\":%lld}"),
            *Base64, FDateTime::UtcNow().GetTicks() / 1000)
    );
    Request->OnProcessRequestComplete().BindUObject(this, &UAocietyClientSubsystem::OnHttpResponse, FName("emotion"));
    Request->ProcessRequest();
}

void UAocietyClientSubsystem::PushTextHint(const FString& Text)
{
    if (Text.IsEmpty()) return;

    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
    Request->SetURL(BackendURL + TEXT("/emotion/analyze"));
    Request->SetVerb(TEXT("POST"));
    Request->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    FString EscapedText = Text.Replace(TEXT("\""), TEXT("\\\""));
    Request->SetContentAsString(
        FString::Printf(TEXT("{\"text_hint\":\"%s\"}"), *EscapedText)
    );
    Request->OnProcessRequestComplete().BindUObject(this, &UAocietyClientSubsystem::OnHttpResponse, FName("emotion"));
    Request->ProcessRequest();
}

// ═══ WebSocket 实时双向流 ═══

bool UAocietyClientSubsystem::ConnectWebSocket()
{
    FString WSURL = BackendURL.Replace(TEXT("http://"), TEXT("ws://")).Replace(TEXT("https://"), TEXT("wss://"));
    WSURL += TEXT("/ws/emotion");

    FModuleManager& ModuleManager = FModuleManager::Get();
    if (!ModuleManager.IsModuleLoaded(TEXT("WebSockets")))
    {
        ModuleManager.LoadModule(TEXT("WebSockets"));
    }

    WebSocket = FWebSocketsModule::Get().CreateWebSocket(WSURL, TEXT("ws"));

    if (!WebSocket.IsValid())
    {
        UE_LOG(LogAociety, Error, TEXT("[Aociety] WebSocket 创建失败: %s"), *WSURL);
        return false;
    }

    WebSocket->OnConnected().AddLambda([]()
    {
        UE_LOG(LogAociety, Log, TEXT("[Aociety] WebSocket 已连接"));
    });

    WebSocket->OnMessage().AddLambda([this](const FString& Message)
    {
        OnWebSocketMessage(Message);
    });

    WebSocket->OnConnectionError().AddLambda([](const FString& Error)
    {
        UE_LOG(LogAociety, Error, TEXT("[Aociety] WebSocket 错误: %s"), *Error);
    });

    WebSocket->Connect();

    // 启动心跳
    if (UWorld* World = GetWorld())
    {
        World->GetTimerManager().SetTimer(
            HeartbeatTimer,
            [this]() { RequestCurrentEmotion(); CheckCareAutoTrigger(); },
            EmotionUpdateInterval,
            true
        );
    }
    return true;
}

void UAocietyClientSubsystem::DisconnectWebSocket()
{
    if (WebSocket.IsValid() && WebSocket->IsConnected())
    {
        WebSocket->Close();
    }
    WebSocket.Reset();

    if (UWorld* World = GetWorld())
    {
        World->GetTimerManager().ClearTimer(HeartbeatTimer);
    }
}

void UAocietyClientSubsystem::OnWebSocketMessage(const FString& Message)
{
    TSharedPtr<FJsonObject> Json;
    TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Message);

    if (!FJsonSerializer::Deserialize(Reader, Json) || !Json.IsValid())
    {
        return;
    }

    FAocietyEmotion Emotion;
    Emotion.Emotion = Json->GetStringField(TEXT("emotion"));
    Emotion.Valence = Json->GetNumberField(TEXT("valence"));
    Emotion.Arousal = Json->GetNumberField(TEXT("arousal"));
    Emotion.SupportNeed = Json->GetNumberField(TEXT("support_need"));
    Emotion.bDegraded = Json->GetBoolField(TEXT("degraded"));

    TSharedPtr<FJsonObject> TrendObj = Json->GetObjectField(TEXT("trend"));
    if (TrendObj.IsValid())
    {
        Emotion.Trend = TrendObj->GetStringField(TEXT("label"));
    }

    EmitEmotionIfChanged(Emotion);
    LastEmotion = Emotion;
}

// ═══ HTTP REST ═══

void UAocietyClientSubsystem::RequestCurrentEmotion()
{
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
    Request->SetURL(BackendURL + TEXT("/emotion/state"));
    Request->SetVerb(TEXT("GET"));
    Request->OnProcessRequestComplete().BindUObject(this, &UAocietyClientSubsystem::OnHttpResponse, FName("state"));
    Request->ProcessRequest();
}

void UAocietyClientSubsystem::RequestWorldState()
{
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
    Request->SetURL(BackendURL + TEXT("/world/state"));
    Request->SetVerb(TEXT("GET"));
    Request->OnProcessRequestComplete().BindUObject(this, &UAocietyClientSubsystem::OnHttpResponse, FName("world"));
    Request->ProcessRequest();
}

void UAocietyClientSubsystem::RequestNPCCare(const FString& NpcId)
{
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
    Request->SetURL(BackendURL + TEXT("/emotion/care_with_voice"));
    Request->SetVerb(TEXT("POST"));
    Request->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    Request->SetContentAsString(
        FString::Printf(TEXT("{\"npc_id\":\"%s\"}"), *NpcId)
    );
    Request->OnProcessRequestComplete().BindUObject(this, &UAocietyClientSubsystem::OnHttpResponse, FName("care"));
    Request->ProcessRequest();
}

// ═══ TTS 甜女声 ═══

void UAocietyClientSubsystem::SetTTSVoice(const FString& VoiceName)
{
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
    Request->SetURL(BackendURL + TEXT("/tts/voices/") + VoiceName);
    Request->SetVerb(TEXT("POST"));
    Request->ProcessRequest();
}

void UAocietyClientSubsystem::SynthesizeTTS(const FString& Text, const FString& VoiceName)
{
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
    Request->SetURL(BackendURL + TEXT("/tts/synthesize"));
    Request->SetVerb(TEXT("POST"));
    Request->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    FString EscapedText = Text.Replace(TEXT("\""), TEXT("\\\""));
    Request->SetContentAsString(
        FString::Printf(TEXT("{\"text\":\"%s\",\"voice\":\"%s\"}"),
            *EscapedText, *VoiceName)
    );
    Request->OnProcessRequestComplete().BindUObject(this, &UAocietyClientSubsystem::OnHttpResponse, FName("tts"));
    Request->ProcessRequest();
}

TArray<FString> UAocietyClientSubsystem::ListTTSVoices() const
{
    return { TEXT("xiaoxiao"), TEXT("xiaoyi"), TEXT("xiaomeng"), TEXT("xiaomo"), TEXT("xiaoxuan") };
}

// ═══ 性格评估 ═══

void UAocietyClientSubsystem::StartAssessment()
{
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
    Request->SetURL(BackendURL + TEXT("/assessment/start"));
    Request->SetVerb(TEXT("POST"));
    Request->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    Request->SetContentAsString(TEXT("{}"));
    Request->ProcessRequest();
}

void UAocietyClientSubsystem::SubmitAssessmentTurn(const FString& SessionId, const FString& UserInput)
{
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
    Request->SetURL(BackendURL + TEXT("/assessment/turn"));
    Request->SetVerb(TEXT("POST"));
    Request->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    FString EscapedInput = UserInput.Replace(TEXT("\""), TEXT("\\\""));
    Request->SetContentAsString(
        FString::Printf(TEXT("{\"session_id\":\"%s\",\"player_input\":\"%s\"}"),
            *SessionId, *EscapedInput)
    );
    Request->ProcessRequest();
}

// ═══ 内部辅助 ═══

void UAocietyClientSubsystem::OnHttpResponse(
    FHttpRequestPtr Request,
    FHttpResponsePtr Response,
    bool bSuccess,
    FName Endpoint)
{
    if (!bSuccess || !Response.IsValid() || Response->GetResponseCode() != 200)
    {
        UE_LOG(LogAociety, Warning, TEXT("[Aociety] HTTP %s 失败"), *Endpoint.ToString());
        return;
    }

    FString Body = Response->GetContentAsString();
    TSharedPtr<FJsonObject> Json;
    TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Body);

    if (!FJsonSerializer::Deserialize(Reader, Json) || !Json.IsValid())
    {
        return;
    }

    if (Endpoint == FName("emotion") || Endpoint == FName("state"))
    {
        // Parse emotion packet
        FAocietyEmotion Emotion;
        Emotion.Emotion = Json->GetStringField(TEXT("emotion"));
        Emotion.Valence = Json->GetNumberField(TEXT("valence"));
        Emotion.Arousal = Json->GetNumberField(TEXT("arousal"));
        Emotion.SupportNeed = Json->GetNumberField(TEXT("support_need"));
        Emotion.bDegraded = Json->GetBoolField(TEXT("degraded"));

        EmitEmotionIfChanged(Emotion);
        LastEmotion = Emotion;
    }
    else if (Endpoint == FName("care"))
    {
        FNpcCareResponse Care;
        Care.NpcLine = Json->GetStringField(TEXT("npc_line"));
        Care.Action = Json->GetStringField(TEXT("action"));
        Care.CareLevel = Json->GetStringField(TEXT("care_level"));
        Care.Duration = Json->GetNumberField(TEXT("duration_seconds"));
        Care.VoiceName = Json->GetStringField(TEXT("voice"));
        Care.VoiceNameCN = Json->GetStringField(TEXT("voice_name_cn"));

        FString AudioB64 = Json->GetStringField(TEXT("audio_base64"));
        if (!AudioB64.IsEmpty())
        {
            FBase64::Decode(AudioB64, Care.AudioData);
        }

        OnCareTriggered.Broadcast(Care);
        OnTTSReady.Broadcast(Care);
    }
    else if (Endpoint == FName("tts"))
    {
        FNpcCareResponse Care;
        Care.NpcLine = Json->GetStringField(TEXT("text"));
        Care.VoiceName = Json->GetStringField(TEXT("voice"));
        Care.VoiceNameCN = Json->GetStringField(TEXT("voice_name_cn"));
        FString AudioB64 = Json->GetStringField(TEXT("audio_base64"));
        if (!AudioB64.IsEmpty())
        {
            FBase64::Decode(AudioB64, Care.AudioData);
        }
        OnTTSReady.Broadcast(Care);
    }
    else if (Endpoint == FName("world"))
    {
        const TSharedPtr<FJsonObject>* WorldStateObj;
        if (Json->GetObjectField(TEXT("world_state"), WorldStateObj) && WorldStateObj && (*WorldStateObj).IsValid())
        {
            FAocietyWorldState World;
            World.Day = (*WorldStateObj)->GetIntegerField(TEXT("day"));
            World.ClockMinutes = (*WorldStateObj)->GetIntegerField(TEXT("clock_minutes"));
            World.TimePeriod = (*WorldStateObj)->GetStringField(TEXT("time_period"));
            OnWorldUpdated.Broadcast(World);
        }
    }
}

void UAocietyClientSubsystem::EmitEmotionIfChanged(const FAocietyEmotion& NewEmotion)
{
    if (FMath::Abs(NewEmotion.Valence - LastEmotion.Valence) > 0.02f ||
        FMath::Abs(NewEmotion.Arousal - LastEmotion.Arousal) > 0.05f ||
        NewEmotion.Emotion != LastEmotion.Emotion ||
        NewEmotion.SupportNeed != LastEmotion.SupportNeed)
    {
        OnEmotionUpdated.Broadcast(NewEmotion);
    }
}

void UAocietyClientSubsystem::CheckCareAutoTrigger()
{
    if (LastEmotion.SupportNeed > 0.75f || LastEmotion.Emotion == TEXT("anger"))
    {
        RequestNPCCare(TEXT("npc_01"));
    }
}
```

---

## 🎮 2. 蓝图示例 (Blueprint Examples)

### 蓝图事件图
```
[AocietyGameInstance] → 自动启动 → ConnectWebSocket() + StartCapture()

[Camera Capture Component] (每 ~66ms)
  → 取得 JPEG bytes
  → Subsystem.PushCameraFrame(bytes, "")

[Heartbeat Timer] (每 2s)
  → Subsystem.RequestCurrentEmotion()

[OnEmotionUpdated Event]
  → 更新 HUD 显示效价/唤醒度圆环
  → 根据 support_need 决定是否触发NPC关怀
  → [如果 support_need > 0.6] → Subsystem.RequestNPCCare("npc_01")

[OnTTSReady Event]
  → 把 Care.AudioData 写入 WAV 文件
  → 通过 USoundWaveProcedural 播放甜女声

[Player 走近 NPC] 
  → Subsystem.RequestNPCCare(NPC.Id)
```

### UMG Widget 绑定伪代码

```cpp
// BP_EmotionHUD
Event Pre Construct:
    GameInstance → GetSubsystem(AocietyClientSubsystem)
    → Bind Event to OnEmotionUpdated
    → Bind Event to OnCareTriggered

Event OnEmotionUpdated(Emotion):
    UpdateEmotionRing(Emotion.Valence, Emotion.Arousal, Emotion.SupportNeed)
    UpdateTrendArrow(Emotion.Trend)
    UpdateText("情绪: " + Emotion.Emotion)

Event OnCareTriggered(Care):
    ShowBubble(Care.NpcLine, Care.CareLevel, Care.Action)
    Set SweetVoice Audio (Care.AudioData)
```

---

## 🔊 3. 播放甜女声（TTS）

### 方法 A：用 UE5 SoundWave 播放 MP3
```cpp
// 把 MP3 bytes 转成 USoundWave
USoundWave* CreateSoundWaveFromMP3(const TArray<uint8>& MP3Data)
{
    USoundWave* SoundWave = NewObject<USoundWave>();
    // UE 5.x 内置 MP3 解码
    FSoundWavePCMReader Reader = FSoundWavePCMReader(MP3Data);
    // ... 解码填充
    return SoundWave;
}

// 播放
UAudioComponent* AC = UGameplayStatics::SpawnSound2D(this, CreateSoundWaveFromMP3(Care.AudioData));
```

### 方法 B：用 UAsset 资产
- 让 TTS 输出的 MP3 保存到本地
- 通过 USoundCue 加载后用 `UGameplayStatics::PlaySound2D`

---

## 🎬 4. 摄像头集成

### `Source/Aociety/Public/CameraCaptureComponent.h`

```cpp
UCLASS(ClassGroup=(Aociety), meta=(BlueprintSpawnableComponent))
class UCameraCaptureComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UCameraCaptureComponent();

    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 CameraID = 0;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 Width = 640;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 Height = 480;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float FPS = 15.0f;

protected:
    virtual void BeginPlay() override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType,
        FActorComponentTickFunction* ThisTickFunction) override;

private:
    void* CaptureHandle = nullptr;  // FFrameGrabber / OpenCV handle
    FTimerHandle FrameTimer;

    void CaptureFrame();
};

// 实际实现会使用:
// 1. FFrameGrabber  - 编辑器/PIE
// 2. USB Camera Plugin (FFmpeg) - 桌面应用
// 3. OpenCV UE Plugin - 跨平台
```

---

## 🎤 5. 麦克风集成

```cpp
// UCameraCaptureComponent 同样方式实现，或者用：
// - Audio Capture Component (UE5 内置)
// - 将 PCM16 转发到 Python 后端 /emotion/analyze 端点
```

---

## 📱 6. UMG HUD 示例

### BP_EmotionHUD 组件

```
CanvasPanel
├── [Top-Right] EmotionIndicator
│   ├── CircularProgress (Valence: 0-1 → 颜色)
│   ├── CircularProgress (Arousal: 0-1 → 大小)
│   └── Text("情绪标签")
├── [Top-Left] ActionSuggestion
│   └── VerticalScroll (NPC care bubbles)
└── [Bottom] StatusBar
    ├── Text("效价:0.6 唤醒:0.7 关怀:0.5")
    └── ProgressBar (Support Need)

颜色映射:
  效价 0.0-0.3 → 红
  效价 0.3-0.6 → 黄
  效价 0.6-1.0 → 绿

关怀气泡颜色:
  level=nudge → 蓝色
  level=care  → 紫色
  level=guard → 红色
```

---

## 🚀 7. 启动顺序（蓝图 BeginPlay）

```
AocietyGameInstance.BeginPlay:
    1. Get Subsystem (AocietyClientSubsystem)
    2. Set BackendURL = "http://127.0.0.1:8000"
    3. Subsystem.ConnectWebSocket()
    4. Subsystem.Bind to OnEmotionUpdated → HUD
    5. Subsystem.Bind to OnCareTriggered → NPC SpeechUI
    6. Subsystem.Bind to OnTTSReady → AudioComponent
    7. Spawn Actor with CameraCaptureComponent
    8. Spawn Actor with MicCaptureComponent

BeginPlay 后自动:
    - 每 66ms 摄像头帧推送到后端
    - 每 1s 音频块推送到后端
    - 每 2s 通过 WebSocket 拉取最新状态
    - 检测支持需求触发 NPC 关怀
```

---

## 🎯 8. 高级：NPC 关怀蓝图节点

### `BP_NPC_Memory`
```
Event ActorBeginOverlap (Player):
    Get Game Instance
    → Get AocietyClientSubsystem
    → Bind OnCareTriggered to OnReceivedCare
    → Async Action: Wait 0.3s
    → Subsystem.RequestNPCCare(self.NpcId)

Event OnReceivedCare(Care):
    If Care.CareLevel == "guard":
        Show UI Bubble
        Play Audio (Care.AudioData)
    ElseIf Care.CareLevel == "care":
        Set NPC.Mood = "Friendly"
        Show UI Bubble
        Play Audio
    Else (nudge):
        Show small notification
```

---

## 📂 9. 推荐依赖（UE5 Plugins）

- **WebSockets** (内置)
- **HTTP** (内置)
- **VaRest** 或 **JSON Blueprint Utilities** — JSON序列化
- **CameraCapture** 或自写 OpenCV 桥接
- **AudioCapture** (内置)
- **USoundWave** + FreeType (可选，用于在UE中可视化频谱)

---

## 🔑 10. 关键事件订阅示例 (Blueprint 蓝图)

```
变量: AocietyClient (GameInstance Subsystem Reference)

Event BeginPlay:
    AocietyClient = GetGameInstanceSubsystem(AocietyClient)
    BindEventTo OnEmotionUpdated → OnEmotionReceived_Custom
    BindEventTo OnCareTriggered → OnCareReceived_Custom
    BindEventTo OnTTSReady → OnTTSReady_Custom
    Call Connect Web Socket

Event OnEmotionReceived_Custom(Emotion):
    SetText("情绪", Emotion.Emotion)
    SetProgressBar("Valence", Emotion.Valence)
    SetProgressBar("Arousal", Emotion.Arousal)
    SetProgressBar("CareNeed", Emotion.SupportNeed)
    SetColor("MoodColor", ColorFromValence(Emotion.Valence))

Event OnCareReceived_Custom(Care):
    ShowBubble(Care.NpcLine)
    If Care.AudioData exists:
        Save Audio to temp.wav
        Play Sound at Location

Event OnTTSReady_Custom(Care):
    CreateSoundWave from AudioData
    PlaySound2D
    Schedule: 0.3s 后销毁临时文件
```

---

## ✅ 11. 验收清单

- [ ] UE5 C++ 编译通过（`WebSockets`, `HTTP`, `Json` 模块）
- [ ] WebSocket 稳定连接（断线重连）
- [ ] 摄像头每 15fps 推送 → 后端响应 < 200ms
- [ ] 麦克风每 1s 推送 → 后端响应 < 1s
- [ ] 情感显示圆环/颜色实时刷新
- [ ] 主动关怀触发（support_need > 0.6）
- [ ] TTS 甜女声播放可听（晓晓音色）
- [ ] 性格评估流程 8 轮对话完成
- [ ] 离线降级（GLM不可用时）不崩

---

## 🔗 完整模块依赖 (UE5 Build.cs)

```csharp
PublicDependencyModuleNames.AddRange(new[]
{
    "Core", "CoreUObject", "Engine", "InputCore",
    "HTTP", "Json", "JsonUtilities",
    "WebSockets", "Sockets", "Networking",
    "RHI", "RenderCore",
    "AudioMixer", "SignalProcessing"
});

PrivateDependencyModuleNames.AddRange(new[]
{
    "Projects",
    "ApplicationCore"
});
```
