// Copyright Aociety. All rights reserved.

#pragma once

#include "CoreMinimal.h"
#include "Commandlets/Commandlet.h"
#include "AocietyMotionAssetBuilderCommandlet.generated.h"

UCLASS()
class AOCIETYEDITOR_API UAocietyMotionAssetBuilderCommandlet : public UCommandlet
{
    GENERATED_BODY()

public:
    UAocietyMotionAssetBuilderCommandlet();
    virtual int32 Main(const FString& Params) override;
};
