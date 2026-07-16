// Copyright Aociety. All rights reserved.

#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "AocietyNPCBubbleWidget.generated.h"

class STextBlock;

UCLASS()
class AOCIETY_API UAocietyNPCBubbleWidget : public UUserWidget
{
    GENERATED_BODY()

public:
    void SetBubbleText(const FString& InText, bool bThinking = false);

protected:
    virtual TSharedRef<SWidget> RebuildWidget() override;

private:
    FString BubbleText = TEXT("AI 居民 · GLM 5.2");
    bool bIsThinking = false;
    TSharedPtr<STextBlock> SlateText;
};
