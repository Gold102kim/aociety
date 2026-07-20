// Copyright Aociety. All rights reserved.

#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "Input/Reply.h"
#include "AocietyMainMenuWidget.generated.h"

UCLASS()
class AOCIETY_API UAocietyMainMenuWidget : public UUserWidget
{
    GENERATED_BODY()

protected:
    virtual TSharedRef<SWidget> RebuildWidget() override;

private:
    FReply HandleEnterWorld();
    FReply HandleQuitGame();
};
