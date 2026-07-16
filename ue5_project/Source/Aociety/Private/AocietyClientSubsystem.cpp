// SPDX-License-Identifier: MIT
// Aociety UE5.8 客户端子系统 - 实现
// 路径: Source/Aociety/Private/AocietyClientSubsystem.cpp

#include "AocietyClientSubsystem.h"
#include "HttpModule.h"
#include "Interfaces/IHttpResponse.h"
#include "Json.h"
#include "JsonUtilities.h"
#include "TimerManager.h"
#include "Misc/Base64.h"
#include "Misc/DateTime.h"
#include "Misc/Guid.h"
#include "IWebSocket.h"
#include "WebSocketsModule.h"
#include "Sound/SoundWave.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Engine/World.h"

DEFINE_LOG_CATEGORY_STATIC(LogAociety, Log, All);

#define AOCITY_T() GetWorld() ? GetWorld()->GetTimerManager() : GetGameInstance()->GetTimerManager()

// ════════════════════════════════════════════════════════════════
// 生命周期
// ════════════════════════════════════════════════════════════════

void UAocietyClientSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    UE_LOG(LogAociety, Log, TEXT("[Aociety] Subsystem initialized"));
    if (bAutoConnect)
    {
        Connect();
    }
}

void UAocietyClientSubsystem::Deinitialize()
{
    Disconnect();
    Super::Deinitialize();
}

// ════════════════════════════════════════════════════════════════
// WebSocket
// ════════════════════════════════════════════════════════════════

bool UAocietyClientSubsystem::Connect()
{
    if (bIsConnected) return true;

    if (WS.IsValid())
    {
        WS->OnConnected().Clear();
        WS->OnMessage().Clear();
        WS->OnConnectionError().Clear();
        WS->OnClosed().Clear();
        WS->Close();
        WS.Reset();
    }

    FString WSURL = BackendURL.Replace(TEXT("http://"), TEXT("ws://")).Replace(TEXT("https://"), TEXT("wss://"));
    WSURL += TEXT("/ws/emotion");

    if (!FModuleManager::Get().IsModuleLoaded(TEXT("WebSockets")))
    {
        FModuleManager::Get().LoadModule(TEXT("WebSockets"));
    }

    WS = FWebSocketsModule::Get().CreateWebSocket(WSURL, TEXT("ws"));
    if (!WS.IsValid())
    {
        UE_LOG(LogAociety, Error, TEXT("[Aociety] Failed to create WebSocket: %s"), *WSURL);
        // 后退到 HTTP polling
        StartTimer();
        return false;
    }

    const TWeakObjectPtr<UAocietyClientSubsystem> WeakThis(this);

    WS->OnConnected().AddLambda([WeakThis]()
    {
        UAocietyClientSubsystem* Self = WeakThis.Get();
        if (!Self) return;
        Self->bIsConnected = true;
        UE_LOG(LogAociety, Log, TEXT("[Aociety] WebSocket 连接成功"));
        Self->StartTimer();
    });

    WS->OnMessage().AddLambda([WeakThis](const FString& Msg)
    {
        if (UAocietyClientSubsystem* Self = WeakThis.Get())
        {
            Self->OnWSMessage(Msg);
        }
    });

    WS->OnConnectionError().AddLambda([WeakThis](const FString& Err)
    {
        UAocietyClientSubsystem* Self = WeakThis.Get();
        if (!Self) return;
        Self->bIsConnected = false;
        UE_LOG(LogAociety, Warning, TEXT("[Aociety] WS 错误: %s"), *Err);
        if (UWorld* World = Self->GetWorld())
        {
            World->GetTimerManager().SetTimer(
                Self->Timer_Reconnect,
                [WeakThis]()
                {
                    if (UAocietyClientSubsystem* RetrySelf = WeakThis.Get())
                    {
                        RetrySelf->Connect();
                    }
                },
                5.0f, false);
        }
    });

    WS->OnClosed().AddLambda([WeakThis](int32 Code, const FString& Reason, bool bClean)
    {
        if (UAocietyClientSubsystem* Self = WeakThis.Get())
        {
            Self->bIsConnected = false;
            Self->StopTimer();
        }
    });

    WS->Connect();
    return true;
}

void UAocietyClientSubsystem::Disconnect()
{
    StopTimer();
    if (UWorld* World = GetWorld())
    {
        World->GetTimerManager().ClearTimer(Timer_Reconnect);
    }
    if (WS.IsValid())
    {
        WS->OnConnected().Clear();
        WS->OnMessage().Clear();
        WS->OnConnectionError().Clear();
        WS->OnClosed().Clear();
        WS->Close();
    }
    WS.Reset();
    bIsConnected = false;
}

bool UAocietyClientSubsystem::IsConnected() const
{
    return bIsConnected;
}

void UAocietyClientSubsystem::OnWSMessage(const FString& Msg)
{
    TSharedPtr<FJsonObject> Json;
    auto Reader = TJsonReaderFactory<>::Create(Msg);
    if (!FJsonSerializer::Deserialize(Reader, Json) || !Json.IsValid()) return;

    FAocietyEmotion E;
    E.Emotion = Json->GetStringField(TEXT("emotion"));
    E.Valence = Json->GetNumberField(TEXT("valence"));
    E.Arousal = Json->GetNumberField(TEXT("arousal"));
    E.SupportNeed = Json->GetNumberField(TEXT("support_need"));
    E.bDegraded = Json->HasField(TEXT("degraded")) && Json->GetBoolField(TEXT("degraded"));
    TSharedPtr<FJsonObject> TrendObj = Json->GetObjectField(TEXT("trend"));
    if (TrendObj.IsValid())
    {
        E.Trend = TrendObj->GetStringField(TEXT("label"));
        E.ValenceDelta = TrendObj->HasField(TEXT("valence_delta")) ? TrendObj->GetNumberField(TEXT("valence_delta")) : 0.0f;
        E.ArousalDelta = TrendObj->HasField(TEXT("arousal_delta")) ? TrendObj->GetNumberField(TEXT("arousal_delta")) : 0.0f;
    }
    EmitEmotionIfChanged(E);
    LastEmotion = E;
}

// ════════════════════════════════════════════════════════════════
// 数据推送
// ════════════════════════════════════════════════════════════════

void UAocietyClientSubsystem::PushCameraFrame(const TArray<uint8>& JPEGBytes, const FString& TextHint)
{
    if (JPEGBytes.Num() == 0) return;

    FString B64 = FBase64::Encode(JPEGBytes);
    FString Escaped = TextHint.Replace(TEXT("\""), TEXT("\\\""));

    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetURL(BackendURL + TEXT("/emotion/analyze"));
    Req->SetVerb(TEXT("POST"));
    Req->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    Req->SetContentAsString(
        FString::Printf(TEXT("{\"image_base64\":\"%s\",\"text_hint\":\"%s\"}"), *B64, *Escaped)
    );
    Req->ProcessRequest();
}

void UAocietyClientSubsystem::PushAudioChunk(const TArray<uint8>& PCM16Bytes)
{
    if (PCM16Bytes.Num() == 0) return;
    FString B64 = FBase64::Encode(PCM16Bytes);

    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetURL(BackendURL + TEXT("/emotion/analyze"));
    Req->SetVerb(TEXT("POST"));
    Req->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    Req->SetContentAsString(FString::Printf(TEXT("{\"audio_base64\":\"%s\"}"), *B64));
    Req->ProcessRequest();
}

void UAocietyClientSubsystem::PushTextHint(const FString& Text)
{
    if (Text.IsEmpty()) return;
    FString Esc = Text.Replace(TEXT("\""), TEXT("\\\""));

    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetURL(BackendURL + TEXT("/emotion/analyze"));
    Req->SetVerb(TEXT("POST"));
    Req->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    Req->SetContentAsString(FString::Printf(TEXT("{\"text_hint\":\"%s\"}"), *Esc));
    Req->ProcessRequest();
}

// ════════════════════════════════════════════════════════════════
// HTTP 调用
// ════════════════════════════════════════════════════════════════

void UAocietyClientSubsystem::RequestCurrentEmotion()
{
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetURL(BackendURL + TEXT("/emotion/state"));
    Req->SetVerb(TEXT("GET"));
    Req->OnProcessRequestComplete().BindUObject(this, &UAocietyClientSubsystem::OnHttpDone, FName("emotion"));
    Req->ProcessRequest();
}

void UAocietyClientSubsystem::RequestWorldState()
{
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetURL(BackendURL + TEXT("/world/state"));
    Req->SetVerb(TEXT("GET"));
    Req->OnProcessRequestComplete().BindUObject(this, &UAocietyClientSubsystem::OnHttpDone, FName("world"));
    Req->ProcessRequest();
}

void UAocietyClientSubsystem::RequestNPCList()
{
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetURL(BackendURL + TEXT("/npc/list"));
    Req->SetVerb(TEXT("GET"));
    Req->ProcessRequest();
}

void UAocietyClientSubsystem::RequestNPCCare(const FString& NpcId)
{
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetURL(BackendURL + TEXT("/emotion/care_with_voice"));
    Req->SetVerb(TEXT("POST"));
    Req->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    Req->SetContentAsString(FString::Printf(TEXT("{\"npc_id\":\"%s\"}"), *NpcId));
    Req->OnProcessRequestComplete().BindUObject(this, &UAocietyClientSubsystem::OnHttpDone, FName("care"));
    Req->ProcessRequest();
}

void UAocietyClientSubsystem::RequestNPCDialogue(const FString& NpcId,
                                                 const FString& PlayerInput,
                                                 const FString& District,
                                                 const FString& TopicId)
{
    if (NpcId.IsEmpty() || PlayerInput.IsEmpty()) return;
    const FString EscNpc = NpcId.Replace(TEXT("\\"), TEXT("\\\\")).Replace(TEXT("\""), TEXT("\\\""));
    const FString EscInput = PlayerInput.Replace(TEXT("\\"), TEXT("\\\\")).Replace(TEXT("\""), TEXT("\\\""));
    const FString EscDistrict = District.Replace(TEXT("\\"), TEXT("\\\\")).Replace(TEXT("\""), TEXT("\\\""));
    const FString EscTopic = TopicId.Replace(TEXT("\\"), TEXT("\\\\")).Replace(TEXT("\""), TEXT("\\\""));
    const bool bAmbient = TopicId == TEXT("ambient_resident_chat");
    const FString Mode = bAmbient ? TEXT("ambient") : TEXT("player");
    const FString CounterpartId = bAmbient
        ? (NpcId == TEXT("npc_01") ? TEXT("npc_02") : TEXT("npc_01"))
        : TEXT("");
    FVector PlayerLocation = FVector::ZeroVector;
    if (const APawn* PlayerPawn = UGameplayStatics::GetPlayerPawn(this, 0))
    {
        PlayerLocation = PlayerPawn->GetActorLocation();
    }
    const int64 EventTimestamp = FDateTime::UtcNow().ToUnixTimestamp();

    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetURL(BackendURL + TEXT("/forest/resident_chat"));
    Req->SetVerb(TEXT("POST"));
    Req->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    Req->SetContentAsString(FString::Printf(
        TEXT("{\"npc_id\":\"%s\",\"player_input\":\"%s\",\"mode\":\"%s\",\"counterpart_id\":\"%s\",\"scene_context\":{\"location\":\"forest_town\",\"interaction\":\"%s\",\"activity\":\"%s\",\"nearby_landmark\":\"%s\",\"event_timestamp\":%lld,\"player_position\":{\"x\":%.1f,\"y\":%.1f,\"z\":%.1f}}}"),
        *EscNpc, *EscInput, *Mode, *CounterpartId, *Mode, *EscTopic,
        *EscDistrict,
        static_cast<long long>(EventTimestamp), PlayerLocation.X,
        PlayerLocation.Y, PlayerLocation.Z));
    Req->OnProcessRequestComplete().BindUObject(
        this, &UAocietyClientSubsystem::OnDialogueHttpDone,
        NpcId, Mode, CounterpartId);
    Req->ProcessRequest();
}

void UAocietyClientSubsystem::RequestWorldAction(const FString& ActionType, const FString& District,
                                                  const TMap<FString, FString>& Payload)
{
    FString PayloadJson = TEXT("{");
    bool First = true;
    for (const auto& Pair : Payload)
    {
        if (!First) PayloadJson += TEXT(",");
        First = false;
        PayloadJson += FString::Printf(TEXT("\"%s\":\"%s\""), *Pair.Key, *Pair.Value);
    }
    PayloadJson += TEXT("}");

    FString Body = FString::Printf(
        TEXT("{\"action_type\":\"%s\",\"district\":\"%s\",\"payload\":%s}"),
        *ActionType, *District, *PayloadJson);

    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetURL(BackendURL + TEXT("/world/action"));
    Req->SetVerb(TEXT("POST"));
    Req->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    Req->SetContentAsString(Body);
    Req->ProcessRequest();
}

// ════════════════════════════════════════════════════════════════
// TTS 甜女声
// ════════════════════════════════════════════════════════════════

static const TMap<FString, FString> SWEET_VOICES_CN = {
    { TEXT("xiaoxiao"), TEXT("晓晓 - 甜暖年轻 ★推荐") },
    { TEXT("xiaoyi"), TEXT("晓伊 - 温暖自然") },
    { TEXT("xiaomeng"), TEXT("晓梦 - 可爱清新") },
    { TEXT("xiaomo"), TEXT("晓墨 - 文艺柔和") },
    { TEXT("xiaoxuan"), TEXT("晓萱 - 温润") },
    { TEXT("xiaorui"), TEXT("晓睿 - 成熟") },
};

TArray<FString> UAocietyClientSubsystem::ListTTSVoices() const
{
    TArray<FString> Result;
    for (const auto& Pair : SWEET_VOICES_CN) Result.Add(Pair.Key);
    return Result;
}

FString UAocietyClientSubsystem::GetVoiceCNName(const FString& VoiceKey) const
{
    if (const FString* Found = SWEET_VOICES_CN.Find(VoiceKey))
        return *Found;
    return TEXT("未知");
}

void UAocietyClientSubsystem::SetTTSVoice(const FString& VoiceName)
{
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetURL(BackendURL + TEXT("/tts/voices/") + VoiceName);
    Req->SetVerb(TEXT("POST"));
    Req->ProcessRequest();
    PreferredTTSVoice = VoiceName;
}

void UAocietyClientSubsystem::SynthesizeTTS(const FString& Text, const FString& VoiceName)
{
    FString Esc = Text.Replace(TEXT("\""), TEXT("\\\""));
    FString UseVoice = VoiceName.IsEmpty() ? PreferredTTSVoice : VoiceName;

    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetURL(BackendURL + TEXT("/tts/synthesize"));
    Req->SetVerb(TEXT("POST"));
    Req->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    Req->SetContentAsString(FString::Printf(
        TEXT("{\"text\":\"%s\",\"voice\":\"%s\"}"), *Esc, *UseVoice));
    Req->OnProcessRequestComplete().BindUObject(this, &UAocietyClientSubsystem::OnHttpDone, FName("tts"));
    Req->ProcessRequest();
}

// ════════════════════════════════════════════════════════════════
// 性格评估
// ════════════════════════════════════════════════════════════════

void UAocietyClientSubsystem::StartAssessment()
{
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetURL(BackendURL + TEXT("/assessment/start"));
    Req->SetVerb(TEXT("POST"));
    Req->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    Req->SetContentAsString(TEXT("{}"));
    Req->OnProcessRequestComplete().BindUObject(this, &UAocietyClientSubsystem::OnHttpDone, FName("ast_start"));
    Req->ProcessRequest();
}

void UAocietyClientSubsystem::SubmitAssessmentTurn(const FString& SessionId, const FString& UserInput)
{
    if (SessionId.IsEmpty()) return;
    FString Esc = UserInput.Replace(TEXT("\""), TEXT("\\\""));
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetURL(BackendURL + TEXT("/assessment/turn"));
    Req->SetVerb(TEXT("POST"));
    Req->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    Req->SetContentAsString(FString::Printf(
        TEXT("{\"session_id\":\"%s\",\"player_input\":\"%s\"}"), *SessionId, *Esc));
    Req->ProcessRequest();
}

void UAocietyClientSubsystem::FinishAssessment(const FString& SessionId)
{
    if (SessionId.IsEmpty()) return;
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetURL(BackendURL + TEXT("/assessment/finish/") + SessionId);
    Req->SetVerb(TEXT("POST"));
    Req->ProcessRequest();
}

// ════════════════════════════════════════════════════════════════
// 工具函数
// ════════════════════════════════════════════════════════════════

FString UAocietyClientSubsystem::ColorHexFromValence(float Valence) const
{
    // 0.0=红 0.3=橙 0.6=黄 0.8=绿 1.0=蓝
    if (Valence < 0.3f) return TEXT("#CC2F3E");                         // red
    if (Valence < 0.6f) return TEXT("#FF8C00");                         // orange
    if (Valence < 0.8f) return FString::Printf(TEXT("#33AA00"));        // 黄绿
    return TEXT("#22AA22");  // 绿
}

bool UAocietyClientSubsystem::ShouldTriggerCare() const
{
    return LastEmotion.SupportNeed > 0.6f ||
           LastEmotion.Emotion == TEXT("anger") ||
           LastEmotion.Emotion == TEXT("sadness") && LastEmotion.SupportNeed > 0.4f;
}

// ════════════════════════════════════════════════════════════════
// 内部辅助
// ════════════════════════════════════════════════════════════════

void UAocietyClientSubsystem::OnDialogueHttpDone(
    FHttpRequestPtr Req,
    FHttpResponsePtr Resp,
    bool bOK,
    FString RequestedNpcId,
    FString RequestedMode,
    FString RequestedCounterpartId)
{
    FAocietyNPCDialogue Dialogue;
    Dialogue.NpcId = RequestedNpcId;
    Dialogue.Source = TEXT("error");
    Dialogue.Model = TEXT("glm-5.2");
    Dialogue.Provider = TEXT("tokenhub");
    Dialogue.Mode = RequestedMode;
    Dialogue.CounterpartId = RequestedCounterpartId;

    auto Broadcast = [this, &Dialogue]()
    {
        OnNPCDialogue.Broadcast(Dialogue);
        if (!Dialogue.Message.IsEmpty())
        {
            OnTranscript.Broadcast(Dialogue.Message, TEXT("NPC对话(GLM)"));
        }
    };

    const int32 ResponseCode = Resp.IsValid() ? Resp->GetResponseCode() : 0;
    if (!bOK || !Resp.IsValid() || ResponseCode != 200)
    {
        Dialogue.Message = FString::Printf(
            TEXT("GLM 5.2 实时连接失败（HTTP %d）。"), ResponseCode);
        Dialogue.Mood = TEXT("请求失败");
        Dialogue.ErrorCode = TEXT("http_error");
        UE_LOG(LogAociety, Warning,
            TEXT("[Aociety][ForestAI] request failed: npc=%s HTTP=%d"),
            *RequestedNpcId, ResponseCode);
        Broadcast();
        return;
    }

    TSharedPtr<FJsonObject> Json;
    const FString Body = Resp->GetContentAsString();
    const auto Reader = TJsonReaderFactory<>::Create(Body);
    if (!FJsonSerializer::Deserialize(Reader, Json) || !Json.IsValid())
    {
        Dialogue.Message = TEXT("GLM 5.2 返回了无法解析的响应。");
        Dialogue.Mood = TEXT("请求失败");
        Dialogue.ErrorCode = TEXT("invalid_json");
        Broadcast();
        return;
    }

    auto ApplyFields = [&Dialogue](const TSharedPtr<FJsonObject>& Object)
    {
        if (!Object.IsValid()) return;
        if (Object->HasField(TEXT("npc_id"))) Dialogue.NpcId = Object->GetStringField(TEXT("npc_id"));
        if (Object->HasField(TEXT("message"))) Dialogue.Message = Object->GetStringField(TEXT("message"));
        if (Object->HasField(TEXT("mood"))) Dialogue.Mood = Object->GetStringField(TEXT("mood"));
        if (Object->HasField(TEXT("source"))) Dialogue.Source = Object->GetStringField(TEXT("source"));
        if (Object->HasField(TEXT("model"))) Dialogue.Model = Object->GetStringField(TEXT("model"));
        if (Object->HasField(TEXT("provider"))) Dialogue.Provider = Object->GetStringField(TEXT("provider"));
        if (Object->HasField(TEXT("mode"))) Dialogue.Mode = Object->GetStringField(TEXT("mode"));
        if (Object->HasField(TEXT("counterpart_id"))) Dialogue.CounterpartId = Object->GetStringField(TEXT("counterpart_id"));
        if (Object->HasField(TEXT("request_id"))) Dialogue.RequestId = Object->GetStringField(TEXT("request_id"));
        if (Object->HasField(TEXT("error_code"))) Dialogue.ErrorCode = Object->GetStringField(TEXT("error_code"));
    };

    ApplyFields(Json);
    if (Json->HasField(TEXT("dialogue")))
    {
        ApplyFields(Json->GetObjectField(TEXT("dialogue")));
    }

    if (!Dialogue.NpcId.Equals(RequestedNpcId, ESearchCase::CaseSensitive) ||
        !Dialogue.Mode.Equals(RequestedMode, ESearchCase::IgnoreCase) ||
        !Dialogue.CounterpartId.Equals(
            RequestedCounterpartId, ESearchCase::CaseSensitive))
    {
        UE_LOG(LogAociety, Warning,
            TEXT("[Aociety][ForestAI] response routing mismatch: requested=%s/%s/%s returned=%s/%s/%s"),
            *RequestedNpcId, *RequestedMode, *RequestedCounterpartId,
            *Dialogue.NpcId, *Dialogue.Mode, *Dialogue.CounterpartId);
    }
    Dialogue.NpcId = RequestedNpcId;
    Dialogue.Mode = RequestedMode;
    Dialogue.CounterpartId = RequestedCounterpartId;

    const bool bVerifiedLLM =
        Dialogue.Source.Equals(TEXT("llm"), ESearchCase::IgnoreCase) &&
        Dialogue.Model.Equals(TEXT("glm-5.2"), ESearchCase::IgnoreCase) &&
        Dialogue.Provider.Equals(TEXT("tokenhub"), ESearchCase::IgnoreCase) &&
        !Dialogue.Message.IsEmpty();
    if (Dialogue.Source.Equals(TEXT("llm"), ESearchCase::IgnoreCase) && !bVerifiedLLM)
    {
        Dialogue.Source = TEXT("error");
        Dialogue.Message = TEXT("响应来源校验失败，未显示非 GLM 5.2 内容。");
        Dialogue.Mood = TEXT("请求失败");
        Dialogue.ErrorCode = TEXT("unverified_llm_response");
    }
    else if (!bVerifiedLLM)
    {
        Dialogue.Source = TEXT("error");
        if (Dialogue.Message.IsEmpty())
        {
            Dialogue.Message = TEXT("GLM 5.2 实时思考请求失败。");
        }
        if (Dialogue.ErrorCode.IsEmpty())
        {
            Dialogue.ErrorCode = TEXT("llm_unavailable");
        }
    }

    UE_LOG(LogAociety, Log,
        TEXT("[Aociety][ForestAI] npc=%s source=%s provider=%s model=%s request=%s"),
        *Dialogue.NpcId, *Dialogue.Source, *Dialogue.Provider,
        *Dialogue.Model, *Dialogue.RequestId);
    Broadcast();
}

void UAocietyClientSubsystem::OnHttpDone(FHttpRequestPtr Req, FHttpResponsePtr Resp, bool bOK, FName Endpoint)
{
    if (!bOK || !Resp.IsValid() || Resp->GetResponseCode() != 200)
    {
        if (Endpoint == FName("care"))
        {
            UE_LOG(LogAociety, Warning, TEXT("[Aociety] care error: HTTP=%d"), Resp.IsValid() ? Resp->GetResponseCode() : 0);
        }
        return;
    }

    FString Body = Resp->GetContentAsString();
    TSharedPtr<FJsonObject> Json;
    auto Reader = TJsonReaderFactory<>::Create(Body);
    if (!FJsonSerializer::Deserialize(Reader, Json) || !Json.IsValid()) return;

    if (Endpoint == FName("emotion") || Endpoint == FName("state"))
    {
        FAocietyEmotion E;
        E.Emotion = Json->HasField(TEXT("emotion")) ? Json->GetStringField(TEXT("emotion")) : TEXT("unknown");
        E.Valence = Json->HasField(TEXT("valence")) ? Json->GetNumberField(TEXT("valence")) : 0.5f;
        E.Arousal = Json->HasField(TEXT("arousal")) ? Json->GetNumberField(TEXT("arousal")) : 0.0f;
        E.SupportNeed = Json->HasField(TEXT("support_need")) ? Json->GetNumberField(TEXT("support_need")) : 0.0f;
        E.bDegraded = Json->HasField(TEXT("degraded")) && Json->GetBoolField(TEXT("degraded"));
        if (Json->HasField(TEXT("trend")))
        {
            TSharedPtr<FJsonObject> TrendObj = Json->GetObjectField(TEXT("trend"));
            if (TrendObj.IsValid())
            {
                E.Trend = TrendObj->GetStringField(TEXT("label"));
            }
        }
        EmitEmotionIfChanged(E);
        LastEmotion = E;
    }
    else if (Endpoint == FName("care") || Endpoint == FName("tts"))
    {
        EmitCareFromJson(Json);
    }
    else if (Endpoint == FName("world"))
    {
        if (Json->HasField(TEXT("world_state")))
        {
            const TSharedPtr<FJsonObject> WorldStateObject = Json->GetObjectField(TEXT("world_state"));
            if (WorldStateObject.IsValid())
            {
                FAocietyWorldSnapshot W;
                W.Day = WorldStateObject->GetIntegerField(TEXT("day"));
                W.ClockMinutes = WorldStateObject->GetIntegerField(TEXT("clock_minutes"));
                W.TimePeriod = WorldStateObject->GetStringField(TEXT("time_period"));
                OnWorldUpdated.Broadcast(W);
            }
        }
    }
    else if (Endpoint == FName("ast_start"))
    {
        if (Json->HasField(TEXT("session_id")))
        {
            CurrentSessionId = Json->GetStringField(TEXT("session_id"));
            UE_LOG(LogAociety, Log, TEXT("[Aociety] 评估开始: %s"), *CurrentSessionId);
        }
    }
}

void UAocietyClientSubsystem::EmitCareFromJson(const TSharedPtr<FJsonObject>& Json)
{
    FNpcCareAudio Care;
    Care.NpcLine = Json->GetStringField(TEXT("npc_line"));
    Care.Action = Json->GetStringField(TEXT("action"));
    Care.CareLevel = Json->HasField(TEXT("care_level")) ? Json->GetStringField(TEXT("care_level")) : TEXT("nudge");
    Care.Duration = Json->HasField(TEXT("duration_seconds")) ? Json->GetNumberField(TEXT("duration_seconds")) : 5.0f;
    Care.VoiceName = Json->HasField(TEXT("voice")) ? Json->GetStringField(TEXT("voice")) : TEXT("xiaoxiao");
    Care.VoiceNameCN = Json->HasField(TEXT("voice_name_cn")) ? Json->GetStringField(TEXT("voice_name_cn")) : TEXT("晓晓");
    Care.AudioBase64 = Json->HasField(TEXT("audio_base64")) ? Json->GetStringField(TEXT("audio_base64")) : TEXT("");

    OnCareTriggered.Broadcast(Care);

    // 同时触发TTS事件
    OnTranscript.Broadcast(Care.NpcLine, TEXT("NPC关怀"));
}

void UAocietyClientSubsystem::EmitEmotionIfChanged(const FAocietyEmotion& New)
{
    bool bChanged = New.Emotion != LastEmotion.Emotion ||
                    FMath::Abs(New.Valence - LastEmotion.Valence) > 0.02f ||
                    FMath::Abs(New.Arousal - LastEmotion.Arousal) > 0.05f;
    if (bChanged)
    {
        OnEmotionUpdated.Broadcast(New);
        // UE only publishes game context and emotion state. Hardware owns the
        // proactive-care trigger, speech, and robot actions.
    }
}

void UAocietyClientSubsystem::StartTimer()
{
    if (UWorld* World = GetWorld())
    {
        World->GetTimerManager().SetTimer(
            Timer_Heartbeat,
            [this]() { RequestCurrentEmotion(); },
            HeartbeatInterval, true
        );
    }
}

void UAocietyClientSubsystem::StopTimer()
{
    if (UWorld* World = GetWorld())
    {
        World->GetTimerManager().ClearTimer(Timer_Heartbeat);
    }
}

void UAocietyClientSubsystem::EnsureConnection()
{
    if (!bIsConnected)
    {
        Connect();
    }
}

TArray<uint8> UAocietyClientSubsystem::DecodeBase64(const FString& B64)
{
    TArray<uint8> Result;
    FBase64::Decode(B64, Result);
    return Result;
}
