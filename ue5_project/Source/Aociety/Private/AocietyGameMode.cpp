// Copyright Aociety. 保留所有权利.

#include "AocietyGameMode.h"
#include "AocietyClientSubsystem.h"
#include "AocietyPlayerCharacter.h"
#include "AocietyNPCCharacter.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Kismet/GameplayStatics.h"
#include "TimerManager.h"

namespace
{
AAocietyNPCCharacter* FindResidentNPC(
    const UObject* WorldContext,
    const FString& NpcId)
{
    if (!WorldContext || NpcId.IsEmpty())
    {
        return nullptr;
    }

    TArray<AActor*> MatchingActors;
    UGameplayStatics::GetAllActorsWithTag(
        WorldContext, FName(*NpcId), MatchingActors);
    for (AActor* Actor : MatchingActors)
    {
        if (AAocietyNPCCharacter* NPC = Cast<AAocietyNPCCharacter>(Actor))
        {
            return NPC;
        }
    }
    return nullptr;
}

FString GetResidentDisplayName(
    const UObject* WorldContext,
    const FString& NpcId)
{
    if (const AAocietyNPCCharacter* NPC = FindResidentNPC(WorldContext, NpcId))
    {
        return NPC->DisplayName;
    }
    if (NpcId == TEXT("npc_01"))
    {
        return TEXT("林汐");
    }
    if (NpcId == TEXT("npc_02"))
    {
        return TEXT("小樱");
    }
    return TEXT("小镇居民");
}
}

AAocietyGameMode::AAocietyGameMode()
{
    DefaultPawnClass = AAocietyPlayerCharacter::StaticClass();
}

void AAocietyGameMode::BeginPlay()
{
    Super::BeginPlay();

    TArray<AActor*> DialogueTriggers;
    UGameplayStatics::GetAllActorsWithTag(
        this, FName("AocietyDialogueTrigger"), DialogueTriggers);

    for (AActor* Trigger : DialogueTriggers)
    {
        if (IsValid(Trigger))
        {
            Trigger->OnActorBeginOverlap.AddDynamic(
                this, &AAocietyGameMode::HandleDialogueTrigger);
            Trigger->OnActorEndOverlap.AddDynamic(
                this, &AAocietyGameMode::HandleDialogueTriggerEnd);
        }
    }

    if (UGameInstance* GameInstance = GetGameInstance())
    {
        if (UAocietyClientSubsystem* Client =
                GameInstance->GetSubsystem<UAocietyClientSubsystem>())
        {
            Client->OnNPCDialogue.AddDynamic(
                this, &AAocietyGameMode::HandleNPCDialogue);
        }
    }

    UE_LOG(LogTemp, Log, TEXT("[AocietyGameMode] Bound %d DeepSeek dialogue triggers"),
           DialogueTriggers.Num());

    GetWorldTimerManager().SetTimer(
        AmbientConversationTimer, this,
        &AAocietyGameMode::StartAmbientNPCConversation,
        32.0f, true, 14.0f);
}

void AAocietyGameMode::HandleDialogueTrigger(AActor* TriggerActor, AActor* OtherActor)
{
    AAocietyPlayerCharacter* Player = Cast<AAocietyPlayerCharacter>(OtherActor);
    if (!IsValid(TriggerActor) || !IsValid(Player))
    {
        return;
    }

    FString NpcId;
    for (const FName& Tag : TriggerActor->Tags)
    {
        const FString TagText = Tag.ToString();
        if (TagText.StartsWith(TEXT("npc_")))
        {
            NpcId = TagText;
            break;
        }
    }
    if (NpcId.IsEmpty())
    {
        return;
    }

    TArray<AActor*> MatchingNPCs;
    UGameplayStatics::GetAllActorsWithTag(this, FName(*NpcId), MatchingNPCs);
    for (AActor* Actor : MatchingNPCs)
    {
        if (AAocietyNPCCharacter* NPC = Cast<AAocietyNPCCharacter>(Actor))
        {
            Player->SetNearbyNPC(NPC);
            return;
        }
    }
}

void AAocietyGameMode::HandleDialogueTriggerEnd(
    AActor* TriggerActor, AActor* OtherActor)
{
    AAocietyPlayerCharacter* Player = Cast<AAocietyPlayerCharacter>(OtherActor);
    if (!IsValid(TriggerActor) || !IsValid(Player))
    {
        return;
    }

    for (const FName& Tag : TriggerActor->Tags)
    {
        const FString TagText = Tag.ToString();
        if (!TagText.StartsWith(TEXT("npc_")))
        {
            continue;
        }
        TArray<AActor*> MatchingNPCs;
        UGameplayStatics::GetAllActorsWithTag(this, Tag, MatchingNPCs);
        for (AActor* Actor : MatchingNPCs)
        {
            if (AAocietyNPCCharacter* NPC = Cast<AAocietyNPCCharacter>(Actor))
            {
                Player->ClearNearbyNPC(NPC);
            }
        }
    }
}

void AAocietyGameMode::HandleNPCDialogue(FAocietyNPCDialogue Dialogue)
{
    AAocietyNPCCharacter* Speaker = FindResidentNPC(this, Dialogue.NpcId);
    const FString SpeakerName = Speaker
        ? Speaker->DisplayName
        : GetResidentDisplayName(this, Dialogue.NpcId);
    const FString Attribution = Dialogue.Model.IsEmpty()
        ? Dialogue.Source
        : FString::Printf(TEXT("%s / %s"), *Dialogue.Source, *Dialogue.Model);

    UE_LOG(LogTemp, Log, TEXT("[Aociety][NPC] %s: %s (%s)"),
           *Dialogue.NpcId, *Dialogue.Message, *Attribution);

    if (GEngine && !Dialogue.Message.IsEmpty())
    {
        GEngine->AddOnScreenDebugMessage(
            -1, 12.0f, FColor(160, 235, 255),
            FString::Printf(TEXT("%s：%s\n[%s]"),
                *SpeakerName, *Dialogue.Message, *Attribution));
    }

    if (!Speaker)
    {
        UE_LOG(LogTemp, Warning,
            TEXT("[Aociety][NPC] No world actor found for %s"),
            *Dialogue.NpcId);
        return;
    }

    const bool bAmbient = Dialogue.Mode.Equals(
        TEXT("ambient"), ESearchCase::IgnoreCase) &&
        !Dialogue.CounterpartId.IsEmpty();
    AAocietyNPCCharacter* Listener = bAmbient
        ? FindResidentNPC(this, Dialogue.CounterpartId)
        : nullptr;
    const FString ListenerName = bAmbient
        ? GetResidentDisplayName(this, Dialogue.CounterpartId)
        : FString();
    const FString VisibleLine = bAmbient
        ? FString::Printf(TEXT("对 %s：%s"),
            *ListenerName, *Dialogue.Message)
        : Dialogue.Message;

    Speaker->ShowDialogue(
        VisibleLine,
        Dialogue.Source.IsEmpty() ? TEXT("error") : Dialogue.Source,
        Dialogue.Model.IsEmpty() ? TEXT("unavailable") : Dialogue.Model,
        12.0f);

    if (Listener)
    {
        Speaker->FocusOnActor(Listener, 12.0f);
        Listener->FocusOnActor(Speaker, 12.0f);
        Listener->ShowListening(SpeakerName, 12.0f);
    }
}

void AAocietyGameMode::StartAmbientNPCConversation()
{
    UGameInstance* GameInstance = GetGameInstance();
    UAocietyClientSubsystem* Client = GameInstance
        ? GameInstance->GetSubsystem<UAocietyClientSubsystem>()
        : nullptr;
    if (!Client)
    {
        return;
    }

    const FString SpeakerId = bAmbientSpeakerIsNpc01 ? TEXT("npc_01") : TEXT("npc_02");
    const FString ListenerId = bAmbientSpeakerIsNpc01 ? TEXT("npc_02") : TEXT("npc_01");
    bAmbientSpeakerIsNpc01 = !bAmbientSpeakerIsNpc01;

    AAocietyNPCCharacter* Speaker = FindResidentNPC(this, SpeakerId);
    AAocietyNPCCharacter* Listener = FindResidentNPC(this, ListenerId);
    const FString ListenerName = GetResidentDisplayName(this, ListenerId);
    if (Speaker)
    {
        Speaker->ShowThinking();
    }
    if (Listener)
    {
        Listener->ShowListening(
            Speaker ? Speaker->DisplayName : GetResidentDisplayName(this, SpeakerId),
            12.0f);
    }
    if (Speaker && Listener)
    {
        Speaker->FocusOnActor(Listener, 12.0f);
        Listener->FocusOnActor(Speaker, 12.0f);
    }

    Client->RequestNPCDialogue(
        SpeakerId,
        FString::Printf(
            TEXT("你正在森林小镇里散步，并遇到了居民 %s。请结合当前环境和你自己的性格，对对方自然说一句简短的话，不要提到你是AI。"),
            *ListenerName),
        TEXT("forest_town"),
        TEXT("ambient_resident_chat"));
}
