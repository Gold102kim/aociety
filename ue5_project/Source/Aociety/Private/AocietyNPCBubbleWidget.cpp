// Copyright Aociety. All rights reserved.

#include "AocietyNPCBubbleWidget.h"

#include "Engine/Texture2D.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Text/STextBlock.h"

TSharedRef<SWidget> UAocietyNPCBubbleWidget::RebuildWidget()
{
    BubbleTexture = LoadObject<UTexture2D>(
        nullptr, TEXT("/Game/Aociety/UI/T_SpeechBubble_Ivory.T_SpeechBubble_Ivory"));
    BubbleBrush.SetResourceObject(BubbleTexture);
    BubbleBrush.ImageSize = FVector2D(512.0f, 256.0f);
    BubbleBrush.DrawAs = ESlateBrushDrawType::Image;

    return SNew(SBox)
        .WidthOverride(512.0f)
        .HeightOverride(256.0f)
        [
            SNew(SOverlay)
            + SOverlay::Slot()
            [
                SNew(SImage)
                .Image(&BubbleBrush)
            ]
            + SOverlay::Slot()
            .Padding(FMargin(50.0f, 30.0f, 50.0f, 66.0f))
            [
                SNew(SVerticalBox)
                + SVerticalBox::Slot()
                .AutoHeight()
                [
                    SNew(SHorizontalBox)
                    + SHorizontalBox::Slot()
                    .FillWidth(1.0f)
                    .VAlign(VAlign_Center)
                    [
                        SAssignNew(NameText, STextBlock)
                        .Text(FText::FromString(DisplayName))
                        .ColorAndOpacity(FLinearColor(0.20f, 0.15f, 0.11f, 1.0f))
                        .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 19))
                    ]
                    + SHorizontalBox::Slot()
                    .AutoWidth()
                    .VAlign(VAlign_Center)
                    [
                        SAssignNew(StatusText, STextBlock)
                        .Text(FText::FromString(GetStatusLabel()))
                        .ColorAndOpacity(GetStatusColor())
                        .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 13))
                    ]
                ]
                + SVerticalBox::Slot()
                .FillHeight(1.0f)
                .Padding(FMargin(0.0f, 9.0f, 0.0f, 6.0f))
                .VAlign(VAlign_Center)
                [
                    SAssignNew(MessageText, STextBlock)
                    .Text(FText::FromString(Message))
                    .ColorAndOpacity(FLinearColor(0.23f, 0.18f, 0.14f, 1.0f))
                    .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 19))
                    .AutoWrapText(true)
                    .WrapTextAt(402.0f)
                    .Justification(ETextJustify::Center)
                ]
                + SVerticalBox::Slot()
                .AutoHeight()
                .HAlign(HAlign_Center)
                [
                    SAssignNew(MetadataText, STextBlock)
                    .Text(FText::FromString(FString::Printf(
                        TEXT("source=%s  ·  model=%s"), *Source, *Model)))
                    .ColorAndOpacity(FLinearColor(0.48f, 0.42f, 0.35f, 1.0f))
                    .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 12))
                ]
            ]
        ];
}

void UAocietyNPCBubbleWidget::SetIdle(const FString& InDisplayName)
{
    DisplayName = InDisplayName;
    Message = TEXT("正在小镇中散步");
    Source = TEXT("idle");
    Model = TEXT("deepseek-v4-flash");
    bIsThinking = false;
    bIsListening = false;
    bIsRealtimeResponse = false;
    RefreshSlateState();
}

void UAocietyNPCBubbleWidget::SetThinking(
    const FString& InDisplayName,
    const FString& InModel)
{
    DisplayName = InDisplayName;
    Message = TEXT("正在观察你和周围环境…");
    Source = TEXT("pending");
    Model = InModel.IsEmpty() ? TEXT("deepseek-v4-flash") : InModel;
    bIsThinking = true;
    bIsListening = false;
    bIsRealtimeResponse = false;
    RefreshSlateState();
}

void UAocietyNPCBubbleWidget::SetListening(
    const FString& InDisplayName,
    const FString& InSpeakerName,
    const FString& InModel)
{
    DisplayName = InDisplayName;
    Message = FString::Printf(TEXT("正在听 %s 说话…"), *InSpeakerName);
    Source = TEXT("pending");
    Model = InModel.IsEmpty() ? TEXT("deepseek-v4-flash") : InModel;
    bIsThinking = false;
    bIsListening = true;
    bIsRealtimeResponse = false;
    RefreshSlateState();
}

void UAocietyNPCBubbleWidget::SetDialogue(
    const FString& InDisplayName,
    const FString& InMessage,
    const FString& InSource,
    const FString& InModel)
{
    DisplayName = InDisplayName;
    Message = InMessage;
    Source = InSource.IsEmpty() ? TEXT("unknown") : InSource;
    Model = InModel.IsEmpty() ? TEXT("unknown") : InModel;
    bIsThinking = false;
    bIsListening = false;
    bIsRealtimeResponse = Source.Equals(TEXT("llm"), ESearchCase::IgnoreCase);
    RefreshSlateState();
}

void UAocietyNPCBubbleWidget::RefreshSlateState()
{
    if (NameText.IsValid())
    {
        NameText->SetText(FText::FromString(DisplayName));
    }
    if (StatusText.IsValid())
    {
        StatusText->SetText(FText::FromString(GetStatusLabel()));
        StatusText->SetColorAndOpacity(FSlateColor(GetStatusColor()));
    }
    if (MessageText.IsValid())
    {
        MessageText->SetText(FText::FromString(Message));
    }
    if (MetadataText.IsValid())
    {
        MetadataText->SetText(FText::FromString(FString::Printf(
            TEXT("source=%s  ·  model=%s"), *Source, *Model)));
    }
}

FString UAocietyNPCBubbleWidget::GetStatusLabel() const
{
    if (bIsThinking)
    {
        return TEXT("● 实时思考");
    }
    if (bIsListening)
    {
        return TEXT("● 正在倾听");
    }
    if (bIsRealtimeResponse)
    {
        return TEXT("● 实时生成");
    }
    if (Source.Equals(TEXT("error"), ESearchCase::IgnoreCase) ||
        Model.Equals(TEXT("unavailable"), ESearchCase::IgnoreCase))
    {
        return TEXT("● 请求失败");
    }
    return TEXT("● 本地回复");
}

FLinearColor UAocietyNPCBubbleWidget::GetStatusColor() const
{
    if (bIsThinking)
    {
        return FLinearColor(0.76f, 0.43f, 0.16f, 1.0f);
    }
    if (bIsListening)
    {
        return FLinearColor(0.42f, 0.50f, 0.32f, 1.0f);
    }
    if (bIsRealtimeResponse)
    {
        return FLinearColor(0.35f, 0.52f, 0.38f, 1.0f);
    }
    if (Source.Equals(TEXT("error"), ESearchCase::IgnoreCase) ||
        Model.Equals(TEXT("unavailable"), ESearchCase::IgnoreCase))
    {
        return FLinearColor(0.68f, 0.29f, 0.25f, 1.0f);
    }
    return FLinearColor(0.51f, 0.43f, 0.34f, 1.0f);
}
