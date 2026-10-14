// Copyright Aociety. All rights reserved.
#pragma once

#include "AocietyRequestJson.h"
#include "Misc/SecureHash.h"

namespace AocietyConversationScope
{
inline FString GetNamespace(const FString& AccountId, const FString& AgentId)
{
    if (AccountId.IsEmpty() || AgentId.IsEmpty())
    {
#if UE_BUILD_SHIPPING
        return {};
#else
        return TEXT("development-local");
#endif
    }
    const TSharedRef<FJsonObject> Identity = MakeShared<FJsonObject>();
    Identity->SetStringField(TEXT("account"), AccountId);
    Identity->SetStringField(TEXT("agent"), AgentId);
    const FString Serialized = AocietyRequestJson::Serialize(Identity);
    const FTCHARToUTF8 Bytes(*Serialized);
    // This digest only creates a bounded, path-safe namespace. It does not
    // authenticate an account or provide filesystem access control.
    return FMD5::HashBytes(reinterpret_cast<const uint8*>(Bytes.Get()), Bytes.Length());
}
}
