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
    void SetIdle(const FString& InDisplayName);
    void SetThinking(const FString& InDisplayName, const FString& InModel);
    void SetListening(
        const FString& InDisplayName,
        const FString& InSpeakerName,
        const FString& InModel);
    void SetDialogue(
        const FString& InDisplayName,
        const FString& InMessage,
        const FString& InSource,
        const FString& InModel);

protected:
    virtual TSharedRef<SWidget> RebuildWidget() override;

private:
    void RefreshSlateState();
    FString GetStatusLabel() const;
    FLinearColor GetStatusColor() const;

    FString DisplayName = TEXT("小镇居民");
    FString Message = TEXT("你好");
    FString Source = TEXT("pending");
    FString Model = TEXT("deepseek-v4-flash");
    bool bIsThinking = false;
    bool bIsListening = false;
    bool bIsRealtimeResponse = false;
    TSharedPtr<STextBlock> NameText;
    TSharedPtr<STextBlock> StatusText;
    TSharedPtr<STextBlock> MessageText;
    TSharedPtr<STextBlock> MetadataText;
};
