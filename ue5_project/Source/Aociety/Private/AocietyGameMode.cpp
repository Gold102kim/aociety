// Copyright Aociety. 保留所有权利.

#include "AocietyGameMode.h"
#include "AocietyClientSubsystem.h"
#include "AocietyPlayerCharacter.h"
#include "AocietyNPCCharacter.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Kismet/GameplayStatics.h"
#include "TimerManager.h"

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

    UE_LOG(LogTemp, Log, TEXT("[AocietyGameMode] Bound %d GLM dialogue triggers"),
           DialogueTriggers.Num());

    GetWorldTimerManager().SetTimer(
        AmbientConversationTimer, this,
        &AAocietyGameMode::StartAmbientNPCConversation,
        24.0f, true, 14.0f);
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
                *Dialogue.NpcId, *Dialogue.Message, *Attribution));
    }

    TArray<AActor*> MatchingNPCs;
    UGameplayStatics::GetAllActorsWithTag(
        this, FName(*Dialogue.NpcId), MatchingNPCs);
    for (AActor* Actor : MatchingNPCs)
    {
        if (AAocietyNPCCharacter* NPC = Cast<AAocietyNPCCharacter>(Actor))
        {
            const FString VisibleLine = AmbientListenerId.IsEmpty()
                ? Dialogue.Message
                : FString::Printf(TEXT("对 %s：%s"),
                    *AmbientListenerId, *Dialogue.Message);
            NPC->ShowDialogue(VisibleLine, 12.0f);
        }
    }
    AmbientListenerId.Reset();
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
    AmbientListenerId = bAmbientSpeakerIsNpc01 ? TEXT("npc_02") : TEXT("npc_01");
    bAmbientSpeakerIsNpc01 = !bAmbientSpeakerIsNpc01;

    TArray<AActor*> MatchingNPCs;
    UGameplayStatics::GetAllActorsWithTag(this, FName(*SpeakerId), MatchingNPCs);
    for (AActor* Actor : MatchingNPCs)
    {
        if (AAocietyNPCCharacter* NPC = Cast<AAocietyNPCCharacter>(Actor))
        {
            NPC->ShowThinking();
        }
    }

    Client->RequestNPCDialogue(
        SpeakerId,
        FString::Printf(
            TEXT("你正在森林小镇里散步，并遇到了居民 %s。请结合当前环境和你自己的性格，对对方自然说一句简短的话，不要提到你是AI。"),
            *AmbientListenerId),
        TEXT("forest_town"),
        TEXT("ambient_resident_chat"));
}
