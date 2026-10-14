// Copyright Aociety. All rights reserved.
#pragma once

#include "Dom/JsonObject.h"

namespace AocietyDialogueValidation
{
struct FMetadata
{
    FString NpcId;
    FString Source;
    FString Model;
    FString Provider;
    FString Mode;
    FString CounterpartId;
};

inline bool TryReadMetadata(const TSharedPtr<FJsonObject>& Root,
    FMetadata& Metadata, TSharedPtr<FJsonObject>& Payload)
{
    Metadata = {};
    Payload.Reset();
    if (!Root.IsValid()) return false;
    Payload = Root;
    if (Root->HasField(TEXT("dialogue")))
    {
        const TSharedPtr<FJsonObject>* Nested = nullptr;
        if (!Root->TryGetObjectField(TEXT("dialogue"), Nested) || !Nested || !Nested->IsValid()) return false;
        // One object is authoritative. Do not fill missing nested metadata
        // with unrelated top-level fields or request-side defaults.
        Payload = *Nested;
    }
    return Payload->TryGetStringField(TEXT("npc_id"), Metadata.NpcId)
        && !Metadata.NpcId.IsEmpty()
        && Payload->TryGetStringField(TEXT("source"), Metadata.Source)
        && !Metadata.Source.IsEmpty()
        && Payload->TryGetStringField(TEXT("model"), Metadata.Model)
        && !Metadata.Model.IsEmpty()
        && Payload->TryGetStringField(TEXT("provider"), Metadata.Provider)
        && !Metadata.Provider.IsEmpty()
        && Payload->TryGetStringField(TEXT("mode"), Metadata.Mode)
        && !Metadata.Mode.IsEmpty()
        && Payload->TryGetStringField(TEXT("counterpart_id"), Metadata.CounterpartId);
}

inline bool MatchesRequest(const FMetadata& Metadata, const FString& NpcId,
    const FString& Mode, const FString& CounterpartId)
{
    return Metadata.NpcId.Equals(NpcId, ESearchCase::CaseSensitive)
        && Metadata.Mode.Equals(Mode, ESearchCase::CaseSensitive)
        && Metadata.CounterpartId.Equals(CounterpartId, ESearchCase::CaseSensitive);
}

inline bool IsVerifiedLLM(const FMetadata& Metadata)
{
    return Metadata.Source.Equals(TEXT("llm"), ESearchCase::CaseSensitive)
        && Metadata.Model.Equals(TEXT("deepseek-v4-flash"), ESearchCase::CaseSensitive)
        && Metadata.Provider.Equals(TEXT("deepseek"), ESearchCase::CaseSensitive);
}
}
