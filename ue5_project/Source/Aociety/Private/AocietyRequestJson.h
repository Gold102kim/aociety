// Copyright Aociety. All rights reserved.
#pragma once

#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"

namespace AocietyRequestJson
{
inline FString Serialize(const TSharedRef<FJsonObject>& Object)
{
    FString Body;
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Body);
    FJsonSerializer::Serialize(Object, Writer);
    return Body;
}
}
