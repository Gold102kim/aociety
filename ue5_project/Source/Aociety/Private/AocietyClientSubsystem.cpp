// SPDX-License-Identifier: MIT
// Aociety UE5.8 客户端子系统 - 实现
// 路径: Source/Aociety/Private/AocietyClientSubsystem.cpp

#include "AocietyClientSubsystem.h"
#include "AocietyRequestJson.h"
#include "AocietyConversationScope.h"
#include "AocietyDialogueValidation.h"
#include "HttpModule.h"
#include "Interfaces/IHttpResponse.h"
#include "Json.h"
#include "JsonUtilities.h"
#include "TimerManager.h"
#include "Misc/Base64.h"
#include "Misc/DateTime.h"
#include "Misc/Guid.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"
#include "IWebSocket.h"
#include "WebSocketsModule.h"
#include "Sound/SoundWave.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"

DEFINE_LOG_CATEGORY_STATIC(LogAociety, Log, All);

namespace
{
FString SerializeRequestBody(const TSharedRef<FJsonObject>& Object)
{
    return AocietyRequestJson::Serialize(Object);
}
}

// ════════════════════════════════════════════════════════════════
// 生命周期
// ════════════════════════════════════════════════════════════════

void UAocietyClientSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    bShuttingDown = false;
    ResidentConversationScope = FGuid::NewGuid().ToString(EGuidFormats::Digits);
    // GameInstance supplies the account/Agent scope after parsing its session.
    UE_LOG(LogAociety, Log, TEXT("[Aociety] Subsystem initialized"));
    if (bAutoConnect)
    {
        Connect();
    }
}

void UAocietyClientSubsystem::Deinitialize()
{
    bShuttingDown = true;
    SaveConversationHistory();
    Disconnect();
    Super::Deinitialize();
}

// ════════════════════════════════════════════════════════════════
// WebSocket
// ════════════════════════════════════════════════════════════════

bool UAocietyClientSubsystem::Connect()
{
    if (bShuttingDown) return false;
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

    if (!bEnableEmotionWebSocket)
    {
        if (bEnableEmotionPolling)
        {
            StartTimer();
            UE_LOG(LogAociety, Log,
                TEXT("[Aociety] Emotion WebSocket disabled; using opt-in HTTP polling"));
        }
        else
        {
            UE_LOG(LogAociety, Log,
                TEXT("[Aociety] Game-side emotion transport disabled; hardware care remains external"));
        }
        return true;
    }

    FString WSURL = CareBackendURL.Replace(TEXT("http://"), TEXT("ws://")).Replace(TEXT("https://"), TEXT("wss://"));
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
        if (Self->bEnableEmotionWebSocket)
        {
            if (UGameInstance* GameInstance = Self->GetGameInstance())
            {
                GameInstance->GetTimerManager().SetTimer(
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
    if (UGameInstance* GameInstance = GetGameInstance())
    {
        GameInstance->GetTimerManager().ClearTimer(Timer_Reconnect);
    }
    // Unbind before cancelling: cancellation may complete synchronously.
    for (const FHttpRequestPtr& Request : ActiveRequests)
    {
        Request->OnProcessRequestComplete().Unbind();
        Request->CancelRequest();
    }
    ActiveRequests.Reset();
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
    return bIsConnected ||
        (!bEnableEmotionWebSocket &&
            (!bEnableEmotionPolling || Timer_Heartbeat.IsValid()));
}

void UAocietyClientSubsystem::OnWSMessage(const FString& Msg)
{
    TSharedPtr<FJsonObject> Json;
    auto Reader = TJsonReaderFactory<>::Create(Msg);
    if (!FJsonSerializer::Deserialize(Reader, Json) || !Json.IsValid()) return;

    FAocietyEmotion E;
    Json->TryGetStringField(TEXT("emotion"), E.Emotion);
    Json->TryGetNumberField(TEXT("valence"), E.Valence);
    Json->TryGetNumberField(TEXT("arousal"), E.Arousal);
    Json->TryGetNumberField(TEXT("support_need"), E.SupportNeed);
    Json->TryGetBoolField(TEXT("degraded"), E.bDegraded);
    const TSharedPtr<FJsonObject>* TrendObj = nullptr;
    if (Json->TryGetObjectField(TEXT("trend"), TrendObj) && TrendObj && TrendObj->IsValid())
    {
        (*TrendObj)->TryGetStringField(TEXT("label"), E.Trend);
        (*TrendObj)->TryGetNumberField(TEXT("valence_delta"), E.ValenceDelta);
        (*TrendObj)->TryGetNumberField(TEXT("arousal_delta"), E.ArousalDelta);
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

    TSharedRef<FJsonObject> Body = MakeShared<FJsonObject>();
    Body->SetStringField(TEXT("image_base64"), FBase64::Encode(JPEGBytes));
    Body->SetStringField(TEXT("text_hint"), TextHint);

    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetURL(CareBackendURL + TEXT("/emotion/analyze"));
    Req->SetVerb(TEXT("POST"));
    Req->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    Req->SetContentAsString(SerializeRequestBody(Body));
    StartHttpRequest(Req);
}

void UAocietyClientSubsystem::PushAudioChunk(const TArray<uint8>& PCM16Bytes)
{
    if (PCM16Bytes.Num() == 0) return;
    TSharedRef<FJsonObject> Body = MakeShared<FJsonObject>();
    Body->SetStringField(TEXT("audio_base64"), FBase64::Encode(PCM16Bytes));

    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetURL(CareBackendURL + TEXT("/emotion/analyze"));
    Req->SetVerb(TEXT("POST"));
    Req->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    Req->SetContentAsString(SerializeRequestBody(Body));
    StartHttpRequest(Req);
}

void UAocietyClientSubsystem::PushTextHint(const FString& Text)
{
    if (Text.IsEmpty()) return;
    TSharedRef<FJsonObject> Body = MakeShared<FJsonObject>();
    Body->SetStringField(TEXT("text_hint"), Text);

    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetURL(CareBackendURL + TEXT("/emotion/analyze"));
    Req->SetVerb(TEXT("POST"));
    Req->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    Req->SetContentAsString(SerializeRequestBody(Body));
    StartHttpRequest(Req);
}

// ════════════════════════════════════════════════════════════════
// HTTP 调用
// ════════════════════════════════════════════════════════════════

void UAocietyClientSubsystem::StartHttpRequest(
    const TSharedRef<IHttpRequest, ESPMode::ThreadSafe>& Request,
    float TimeoutSeconds)
{
    const FHttpRequestCompleteDelegate Completion = Request->OnProcessRequestComplete();
    if (bShuttingDown || ActiveRequests.Num() >= 32)
    {
        if (!bShuttingDown) Completion.ExecuteIfBound(Request, nullptr, false);
        return;
    }
    Request->SetTimeout(FMath::Clamp(TimeoutSeconds, 1.0f, 60.0f));
    Request->SetDelegateThreadPolicy(EHttpRequestDelegateThreadPolicy::CompleteOnGameThread);
    const TWeakObjectPtr<UAocietyClientSubsystem> WeakThis(this);
    Request->OnProcessRequestComplete().BindLambda(
        [WeakThis, Completion](FHttpRequestPtr Completed, FHttpResponsePtr Response, bool bSuccess)
        {
            UAocietyClientSubsystem* Self = WeakThis.Get();
            // Some transports complete a rejected ProcessRequest immediately;
            // the removal guard makes that path and the fallback idempotent.
            if (!Self || Self->bShuttingDown || Self->ActiveRequests.Remove(Completed) == 0) return;
            Completion.ExecuteIfBound(Completed, Response, bSuccess);
        });
    ActiveRequests.Add(Request);
    if (!Request->ProcessRequest())
    {
        Request->OnProcessRequestComplete().ExecuteIfBound(Request, nullptr, false);
    }
}

void UAocietyClientSubsystem::RequestCurrentEmotion()
{
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetURL(CareBackendURL + TEXT("/emotion/state"));
    Req->SetVerb(TEXT("GET"));
    Req->OnProcessRequestComplete().BindUObject(this, &UAocietyClientSubsystem::OnHttpDone, FName("emotion"));
    StartHttpRequest(Req);
}

void UAocietyClientSubsystem::RequestWorldState()
{
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetURL(BackendURL + TEXT("/world/state"));
    Req->SetVerb(TEXT("GET"));
    Req->OnProcessRequestComplete().BindUObject(this, &UAocietyClientSubsystem::OnHttpDone, FName("world"));
    StartHttpRequest(Req);
}

void UAocietyClientSubsystem::RequestNPCList()
{
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetURL(BackendURL + TEXT("/npc/list"));
    Req->SetVerb(TEXT("GET"));
    StartHttpRequest(Req);
}

void UAocietyClientSubsystem::RequestNPCCare(const FString& NpcId)
{
    TSharedRef<FJsonObject> Body = MakeShared<FJsonObject>();
    Body->SetStringField(TEXT("npc_id"), NpcId);
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetURL(CareBackendURL + TEXT("/emotion/care_with_voice"));
    Req->SetVerb(TEXT("POST"));
    Req->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    Req->SetContentAsString(SerializeRequestBody(Body));
    Req->OnProcessRequestComplete().BindUObject(this, &UAocietyClientSubsystem::OnHttpDone, FName("care"));
    StartHttpRequest(Req, 45.0f);
}

void UAocietyClientSubsystem::RequestNPCDialogue(const FString& NpcId,
                                                 const FString& PlayerInput,
                                                 const FString& District,
                                                 const FString& TopicId)
{
    if (bShuttingDown || NpcId.IsEmpty() || PlayerInput.IsEmpty()) return;
    const bool bAmbient = TopicId == TEXT("ambient_resident_chat");
    const FString Mode = bAmbient ? TEXT("ambient") : TEXT("player");
    const FString CounterpartId = bAmbient
        ? (NpcId == TEXT("npc_01") ? TEXT("npc_02") : TEXT("npc_01"))
        : TEXT("");
    if (!bAmbient)
    {
        FAocietyConversationEntry PlayerEntry;
        PlayerEntry.NpcId = NpcId;
        PlayerEntry.Sender = TEXT("player");
        PlayerEntry.Text = PlayerInput;
        PlayerEntry.Source = TEXT("player");
        PlayerEntry.Model = TEXT("local-input");
        PlayerEntry.Timestamp = FDateTime::UtcNow().ToIso8601();
        PlayerEntry.bFromPlayer = true;
        AppendConversationEntry(PlayerEntry);
    }
    FVector PlayerLocation = FVector::ZeroVector;
    if (const APawn* PlayerPawn = UGameplayStatics::GetPlayerPawn(this, 0))
    {
        PlayerLocation = PlayerPawn->GetActorLocation();
    }
    const int64 EventTimestamp = FDateTime::UtcNow().ToUnixTimestamp();

    TSharedRef<FJsonObject> Position = MakeShared<FJsonObject>();
    Position->SetNumberField(TEXT("x"), PlayerLocation.X);
    Position->SetNumberField(TEXT("y"), PlayerLocation.Y);
    Position->SetNumberField(TEXT("z"), PlayerLocation.Z);
    TSharedRef<FJsonObject> SceneContext = MakeShared<FJsonObject>();
    SceneContext->SetStringField(TEXT("location"), TEXT("forest_town"));
    SceneContext->SetStringField(TEXT("interaction"), Mode);
    SceneContext->SetStringField(TEXT("activity"), TopicId);
    SceneContext->SetStringField(TEXT("nearby_landmark"), District);
    SceneContext->SetNumberField(TEXT("event_timestamp"), EventTimestamp);
    SceneContext->SetObjectField(TEXT("player_position"), Position);
    TSharedRef<FJsonObject> Body = MakeShared<FJsonObject>();
    Body->SetStringField(TEXT("npc_id"), NpcId);
    Body->SetStringField(TEXT("player_input"), PlayerInput);
    Body->SetStringField(TEXT("mode"), Mode);
    Body->SetStringField(TEXT("counterpart_id"), CounterpartId);
    Body->SetStringField(TEXT("conversation_scope"), ResidentConversationScope);
    Body->SetObjectField(TEXT("scene_context"), SceneContext);

    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetURL(BackendURL + TEXT("/forest/resident_chat"));
    Req->SetVerb(TEXT("POST"));
    Req->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    Req->SetContentAsString(SerializeRequestBody(Body));
    Req->OnProcessRequestComplete().BindUObject(
        this, &UAocietyClientSubsystem::OnDialogueHttpDone,
        NpcId, Mode, CounterpartId);
    StartHttpRequest(Req, 45.0f);
}

TArray<FAocietyConversationEntry>
UAocietyClientSubsystem::GetConversationHistory(const FString& NpcId) const
{
    if (const TArray<FAocietyConversationEntry>* History =
            ConversationHistory.Find(NpcId))
    {
        return *History;
    }
    return {};
}

TArray<FString> UAocietyClientSubsystem::GetConversationNpcIds() const
{
    TArray<FString> NpcIds;
    ConversationHistory.GetKeys(NpcIds);
    NpcIds.Sort();
    return NpcIds;
}

void UAocietyClientSubsystem::AppendConversationEntry(
    const FAocietyConversationEntry& Entry)
{
    if (ConversationNamespace.IsEmpty() || Entry.NpcId.IsEmpty() || Entry.Text.IsEmpty())
    {
        return;
    }

    TArray<FAocietyConversationEntry>& History =
        ConversationHistory.FindOrAdd(Entry.NpcId);
    History.Add(Entry);
    constexpr int32 MaxEntriesPerResident = 120;
    if (History.Num() > MaxEntriesPerResident)
    {
        History.RemoveAt(0, History.Num() - MaxEntriesPerResident);
    }
    SaveConversationHistory();
    OnConversationUpdated.Broadcast(Entry.NpcId, Entry);
}

void UAocietyClientSubsystem::ConfigureConversationScope(
    const FString& AccountId, const FString& AgentId)
{
    if (bShuttingDown) return;
    const FString NewNamespace = AocietyConversationScope::GetNamespace(AccountId, AgentId);
    if (NewNamespace == ConversationNamespace) return;
    SaveConversationHistory();
    // A late response from a previous identity must not enter the new inbox.
    Disconnect();
    ConversationNamespace = NewNamespace;
    ResidentConversationScope = FGuid::NewGuid().ToString(EGuidFormats::Digits);
    LoadConversationHistory();
}

FString UAocietyClientSubsystem::GetConversationHistoryPath() const
{
    return FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Aociety"),
        TEXT("Conversations"), ConversationNamespace, TEXT("ConversationHistory.json"));
}

void UAocietyClientSubsystem::LoadConversationHistory()
{
    ConversationHistory.Reset();
    if (ConversationNamespace.IsEmpty()) return;
    const FString Path = GetConversationHistoryPath();
    FString JsonText;
    if (!FFileHelper::LoadFileToString(JsonText, *Path))
    {
        return;
    }

    TSharedPtr<FJsonObject> Root;
    const TSharedRef<TJsonReader<>> Reader =
        TJsonReaderFactory<>::Create(JsonText);
    if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
    {
        UE_LOG(LogAociety, Warning,
            TEXT("[Aociety][Inbox] Could not parse %s"), *Path);
        return;
    }

    const TSharedPtr<FJsonObject>* Conversations = nullptr;
    if (!Root->TryGetObjectField(TEXT("conversations"), Conversations)
        || !Conversations || !Conversations->IsValid())
    {
        return;
    }

    for (const auto& Pair : (*Conversations)->Values)
    {
        const FString NpcId(Pair.Key);
        const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
        if (!Pair.Value.IsValid()
            || !Pair.Value->TryGetArray(Values)
            || !Values)
        {
            continue;
        }
        TArray<FAocietyConversationEntry>& History =
            ConversationHistory.FindOrAdd(NpcId);
        constexpr int32 MaxEntriesPerResident = 120;
        for (int32 Index = FMath::Max(0, Values->Num() - MaxEntriesPerResident); Index < Values->Num(); ++Index)
        {
            const TSharedPtr<FJsonValue>& Value = (*Values)[Index];
            const TSharedPtr<FJsonObject>* Object = nullptr;
            if (!Value.IsValid()
                || !Value->TryGetObject(Object)
                || !Object
                || !Object->IsValid())
            {
                continue;
            }
            FAocietyConversationEntry Entry;
            Entry.NpcId = NpcId;
            (*Object)->TryGetStringField(TEXT("sender"), Entry.Sender);
            (*Object)->TryGetStringField(TEXT("text"), Entry.Text);
            (*Object)->TryGetStringField(TEXT("source"), Entry.Source);
            (*Object)->TryGetStringField(TEXT("model"), Entry.Model);
            (*Object)->TryGetStringField(TEXT("timestamp"), Entry.Timestamp);
            (*Object)->TryGetBoolField(TEXT("from_player"), Entry.bFromPlayer);
            if (!Entry.Text.IsEmpty())
            {
                History.Add(Entry);
            }
        }
    }
}

void UAocietyClientSubsystem::SaveConversationHistory() const
{
    if (ConversationNamespace.IsEmpty()) return;
    TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
    Root->SetNumberField(TEXT("version"), 1);
    TSharedRef<FJsonObject> Conversations = MakeShared<FJsonObject>();
    for (const auto& Pair : ConversationHistory)
    {
        TArray<TSharedPtr<FJsonValue>> Values;
        Values.Reserve(Pair.Value.Num());
        for (const FAocietyConversationEntry& Entry : Pair.Value)
        {
            TSharedRef<FJsonObject> Object = MakeShared<FJsonObject>();
            Object->SetStringField(TEXT("sender"), Entry.Sender);
            Object->SetStringField(TEXT("text"), Entry.Text);
            Object->SetStringField(TEXT("source"), Entry.Source);
            Object->SetStringField(TEXT("model"), Entry.Model);
            Object->SetStringField(TEXT("timestamp"), Entry.Timestamp);
            Object->SetBoolField(TEXT("from_player"), Entry.bFromPlayer);
            Values.Add(MakeShared<FJsonValueObject>(Object));
        }
        Conversations->SetArrayField(Pair.Key, Values);
    }
    Root->SetObjectField(TEXT("conversations"), Conversations);

    FString JsonText;
    const TSharedRef<TJsonWriter<>> Writer =
        TJsonWriterFactory<>::Create(&JsonText);
    if (!FJsonSerializer::Serialize(Root, Writer))
    {
        return;
    }
    const FString Path = GetConversationHistoryPath();
    const FString Directory = FPaths::GetPath(Path);
    IFileManager::Get().MakeDirectory(*Directory, true);
    FFileHelper::SaveStringToFile(
        JsonText,
        *Path,
        FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
}

void UAocietyClientSubsystem::RequestWorldAction(const FString& ActionType, const FString& District,
                                                  const TMap<FString, FString>& Payload)
{
    TSharedRef<FJsonObject> PayloadJson = MakeShared<FJsonObject>();
    for (const auto& Pair : Payload)
    {
        PayloadJson->SetStringField(Pair.Key, Pair.Value);
    }
    TSharedRef<FJsonObject> Body = MakeShared<FJsonObject>();
    Body->SetStringField(TEXT("action_type"), ActionType);
    Body->SetStringField(TEXT("district"), District);
    Body->SetObjectField(TEXT("payload"), PayloadJson);

    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetURL(BackendURL + TEXT("/world/action"));
    Req->SetVerb(TEXT("POST"));
    Req->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    Req->SetContentAsString(SerializeRequestBody(Body));
    StartHttpRequest(Req);
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
    Req->SetURL(CareBackendURL + TEXT("/tts/voices/") + VoiceName);
    Req->SetVerb(TEXT("POST"));
    StartHttpRequest(Req);
    PreferredTTSVoice = VoiceName;
}

void UAocietyClientSubsystem::SynthesizeTTS(const FString& Text, const FString& VoiceName)
{
    FString UseVoice = VoiceName.IsEmpty() ? PreferredTTSVoice : VoiceName;
    TSharedRef<FJsonObject> Body = MakeShared<FJsonObject>();
    Body->SetStringField(TEXT("text"), Text);
    Body->SetStringField(TEXT("voice"), UseVoice);

    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetURL(CareBackendURL + TEXT("/tts/synthesize"));
    Req->SetVerb(TEXT("POST"));
    Req->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    Req->SetContentAsString(SerializeRequestBody(Body));
    Req->OnProcessRequestComplete().BindUObject(this, &UAocietyClientSubsystem::OnHttpDone, FName("tts"));
    StartHttpRequest(Req, 45.0f);
}

// ════════════════════════════════════════════════════════════════
// 性格评估
// ════════════════════════════════════════════════════════════════

void UAocietyClientSubsystem::StartAssessment()
{
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetURL(CareBackendURL + TEXT("/assessment/start"));
    Req->SetVerb(TEXT("POST"));
    Req->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    Req->SetContentAsString(TEXT("{}"));
    Req->OnProcessRequestComplete().BindUObject(this, &UAocietyClientSubsystem::OnHttpDone, FName("ast_start"));
    StartHttpRequest(Req);
}

void UAocietyClientSubsystem::SubmitAssessmentTurn(const FString& SessionId, const FString& UserInput)
{
    if (SessionId.IsEmpty()) return;
    TSharedRef<FJsonObject> Body = MakeShared<FJsonObject>();
    Body->SetStringField(TEXT("session_id"), SessionId);
    Body->SetStringField(TEXT("player_input"), UserInput);
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetURL(CareBackendURL + TEXT("/assessment/turn"));
    Req->SetVerb(TEXT("POST"));
    Req->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    Req->SetContentAsString(SerializeRequestBody(Body));
    StartHttpRequest(Req, 45.0f);
}

void UAocietyClientSubsystem::FinishAssessment(const FString& SessionId)
{
    if (SessionId.IsEmpty()) return;
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
    Req->SetURL(CareBackendURL + TEXT("/assessment/finish/") + SessionId);
    Req->SetVerb(TEXT("POST"));
    StartHttpRequest(Req, 45.0f);
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
    Dialogue.Source = TEXT("error");

    auto Broadcast = [this, &Dialogue, &RequestedNpcId, &RequestedMode, &RequestedCounterpartId]()
    {
        if (Dialogue.Source != TEXT("llm"))
        {
            // Local errors still reach the requested resident's UI; these are
            // routing fields, never evidence that response metadata existed.
            Dialogue.NpcId = RequestedNpcId;
            Dialogue.Mode = RequestedMode;
            Dialogue.CounterpartId = RequestedCounterpartId;
        }
        if (!Dialogue.Message.IsEmpty())
        {
            FAocietyConversationEntry Entry;
            Entry.NpcId = Dialogue.NpcId;
            Entry.Sender = Dialogue.NpcId;
            Entry.Text = Dialogue.Message;
            Entry.Source = Dialogue.Source;
            Entry.Model = Dialogue.Model;
            Entry.Timestamp = FDateTime::UtcNow().ToIso8601();
            Entry.bFromPlayer = false;
            AppendConversationEntry(Entry);
        }
        OnNPCDialogue.Broadcast(Dialogue);
        if (!Dialogue.Message.IsEmpty())
        {
            OnTranscript.Broadcast(Dialogue.Message, TEXT("NPC对话(DeepSeek)"));
        }
    };

    const int32 ResponseCode = Resp.IsValid() ? Resp->GetResponseCode() : 0;
    if (!bOK || !Resp.IsValid() || ResponseCode != 200)
    {
        Dialogue.Message = FString::Printf(
            TEXT("DeepSeek V4 Flash 实时连接失败（HTTP %d）。"), ResponseCode);
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
        Dialogue.Message = TEXT("DeepSeek V4 Flash 返回了无法解析的响应。");
        Dialogue.Mood = TEXT("请求失败");
        Dialogue.ErrorCode = TEXT("invalid_json");
        Broadcast();
        return;
    }

    AocietyDialogueValidation::FMetadata Metadata;
    TSharedPtr<FJsonObject> Payload;
    if (!AocietyDialogueValidation::TryReadMetadata(Json, Metadata, Payload))
    {
        Dialogue.Message = TEXT("居民响应缺少有效来源或路由信息，未显示未经验证的内容。");
        Dialogue.Mood = TEXT("请求失败");
        Dialogue.ErrorCode = TEXT("invalid_response_metadata");
        Broadcast();
        return;
    }
    Dialogue.NpcId = Metadata.NpcId;
    Dialogue.Source = Metadata.Source;
    Dialogue.Model = Metadata.Model;
    Dialogue.Provider = Metadata.Provider;
    Dialogue.Mode = Metadata.Mode;
    Dialogue.CounterpartId = Metadata.CounterpartId;
    Payload->TryGetStringField(TEXT("message"), Dialogue.Message);
    Dialogue.Message.TrimStartAndEndInline();
    Payload->TryGetStringField(TEXT("mood"), Dialogue.Mood);
    Payload->TryGetStringField(TEXT("request_id"), Dialogue.RequestId);
    Payload->TryGetStringField(TEXT("error_code"), Dialogue.ErrorCode);

    if (!AocietyDialogueValidation::MatchesRequest(Metadata,
            RequestedNpcId, RequestedMode, RequestedCounterpartId))
    {
        UE_LOG(LogAociety, Warning,
            TEXT("[Aociety][ForestAI] response routing mismatch: requested=%s/%s/%s returned=%s/%s/%s"),
            *RequestedNpcId, *RequestedMode, *RequestedCounterpartId,
            *Dialogue.NpcId, *Dialogue.Mode, *Dialogue.CounterpartId);
        Dialogue.Source = TEXT("error");
        Dialogue.Message = TEXT("居民响应与本次请求不匹配，未显示错误路由的内容。");
        Dialogue.Mood = TEXT("请求失败");
        Dialogue.ErrorCode = TEXT("response_routing_mismatch");
        Broadcast();
        return;
    }
    const bool bVerifiedLLM =
        AocietyDialogueValidation::IsVerifiedLLM(Metadata) &&
        !Dialogue.Message.IsEmpty();
    if (Dialogue.Source.Equals(TEXT("llm"), ESearchCase::IgnoreCase) && !bVerifiedLLM)
    {
        Dialogue.Source = TEXT("error");
        Dialogue.Message = TEXT("响应来源校验失败，未显示非 DeepSeek V4 Flash 内容。");
        Dialogue.Mood = TEXT("请求失败");
        Dialogue.ErrorCode = TEXT("unverified_llm_response");
    }
    else if (!bVerifiedLLM)
    {
        Dialogue.Source = TEXT("error");
        if (Dialogue.Message.IsEmpty())
        {
            Dialogue.Message = TEXT("DeepSeek V4 Flash 实时思考请求失败。");
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
        E.Emotion = TEXT("unknown");
        Json->TryGetStringField(TEXT("emotion"), E.Emotion);
        Json->TryGetNumberField(TEXT("valence"), E.Valence);
        Json->TryGetNumberField(TEXT("arousal"), E.Arousal);
        Json->TryGetNumberField(TEXT("support_need"), E.SupportNeed);
        Json->TryGetBoolField(TEXT("degraded"), E.bDegraded);
        const TSharedPtr<FJsonObject>* TrendObj = nullptr;
        if (Json->TryGetObjectField(TEXT("trend"), TrendObj) && TrendObj && TrendObj->IsValid())
        {
            (*TrendObj)->TryGetStringField(TEXT("label"), E.Trend);
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
        const TSharedPtr<FJsonObject>* WorldStateObject = nullptr;
        if (Json->TryGetObjectField(TEXT("world_state"), WorldStateObject) && WorldStateObject && WorldStateObject->IsValid())
        {
            FAocietyWorldSnapshot W;
            (*WorldStateObject)->TryGetNumberField(TEXT("day"), W.Day);
            (*WorldStateObject)->TryGetNumberField(TEXT("clock_minutes"), W.ClockMinutes);
            (*WorldStateObject)->TryGetStringField(TEXT("time_period"), W.TimePeriod);
            OnWorldUpdated.Broadcast(W);
        }
    }
    else if (Endpoint == FName("ast_start"))
    {
        if (Json->TryGetStringField(TEXT("session_id"), CurrentSessionId))
        {
            UE_LOG(LogAociety, Log, TEXT("[Aociety] 评估开始: %s"), *CurrentSessionId);
        }
    }
}

void UAocietyClientSubsystem::EmitCareFromJson(const TSharedPtr<FJsonObject>& Json)
{
    FNpcCareAudio Care;
    if (!Json.IsValid() || !Json->TryGetStringField(TEXT("npc_line"), Care.NpcLine) || Care.NpcLine.IsEmpty()) return;
    Json->TryGetStringField(TEXT("action"), Care.Action);
    Care.CareLevel = TEXT("nudge");
    Care.VoiceName = TEXT("xiaoxiao");
    Care.VoiceNameCN = TEXT("晓晓");
    Json->TryGetStringField(TEXT("care_level"), Care.CareLevel);
    Json->TryGetNumberField(TEXT("duration_seconds"), Care.Duration);
    Json->TryGetStringField(TEXT("voice"), Care.VoiceName);
    Json->TryGetStringField(TEXT("voice_name_cn"), Care.VoiceNameCN);
    Json->TryGetStringField(TEXT("audio_base64"), Care.AudioBase64);

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
    if (UGameInstance* GameInstance = GetGameInstance())
    {
        const TWeakObjectPtr<UAocietyClientSubsystem> WeakThis(this);
        GameInstance->GetTimerManager().SetTimer(
            Timer_Heartbeat,
            [WeakThis]()
            {
                if (UAocietyClientSubsystem* Self = WeakThis.Get())
                {
                    if (!Self->bShuttingDown) Self->RequestCurrentEmotion();
                }
            },
            FMath::Max(0.5f, HeartbeatInterval), true
        );
    }
}

void UAocietyClientSubsystem::StopTimer()
{
    if (UGameInstance* GameInstance = GetGameInstance())
    {
        GameInstance->GetTimerManager().ClearTimer(Timer_Heartbeat);
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
