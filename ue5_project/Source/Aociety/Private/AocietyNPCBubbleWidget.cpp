// Copyright Aociety. All rights reserved.

#include "AocietyNPCBubbleWidget.h"

#include "Styling/CoreStyle.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"

TSharedRef<SWidget> UAocietyNPCBubbleWidget::RebuildWidget()
{
    return SNew(SBox)
        .WidthOverride(512.0f)
        .HeightOverride(210.0f)
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
                    .ColorAndOpacity(FLinearColor(1.0f, 0.96f, 0.88f, 1.0f))
                    .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 22))
                    .ShadowOffset(FVector2D(2.0f, 2.0f))
                    .ShadowColorAndOpacity(FLinearColor(0.0f, 0.0f, 0.0f, 0.95f))
                ]
                + SHorizontalBox::Slot()
                .AutoWidth()
                .VAlign(VAlign_Center)
                [
                    SAssignNew(StatusText, STextBlock)
                    .Text(FText::FromString(GetStatusLabel()))
                    .ColorAndOpacity(GetStatusColor())
                    .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 15))
                    .ShadowOffset(FVector2D(1.5f, 1.5f))
                    .ShadowColorAndOpacity(FLinearColor::Black)
                ]
            ]
            + SVerticalBox::Slot()
            .FillHeight(1.0f)
            .Padding(FMargin(0.0f, 8.0f, 0.0f, 5.0f))
            .VAlign(VAlign_Center)
            [
                SAssignNew(MessageText, STextBlock)
                .Text(FText::FromString(Message))
                .ColorAndOpacity(FLinearColor::White)
                .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 21))
                .AutoWrapText(true)
                .WrapTextAt(500.0f)
                .Justification(ETextJustify::Center)
                .ShadowOffset(FVector2D(2.0f, 2.0f))
                .ShadowColorAndOpacity(FLinearColor(0.0f, 0.0f, 0.0f, 1.0f))
            ]
            + SVerticalBox::Slot()
            .AutoHeight()
            .HAlign(HAlign_Center)
            [
                SAssignNew(MetadataText, STextBlock)
                .Text(FText::FromString(FString::Printf(
                    TEXT("source=%s  ·  model=%s"), *Source, *Model)))
                .ColorAndOpacity(FLinearColor(0.86f, 0.88f, 0.92f, 1.0f))
                .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 13))
                .ShadowOffset(FVector2D(1.5f, 1.5f))
                .ShadowColorAndOpacity(FLinearColor::Black)
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
        return FLinearColor(1.0f, 0.58f, 0.16f, 1.0f);
    }
    if (bIsListening)
    {
        return FLinearColor(0.56f, 0.90f, 0.48f, 1.0f);
    }
    if (bIsRealtimeResponse)
    {
        return FLinearColor(0.32f, 1.0f, 0.58f, 1.0f);
    }
    if (Source.Equals(TEXT("error"), ESearchCase::IgnoreCase) ||
        Model.Equals(TEXT("unavailable"), ESearchCase::IgnoreCase))
    {
        return FLinearColor(1.0f, 0.32f, 0.28f, 1.0f);
    }
    return FLinearColor(0.86f, 0.78f, 0.66f, 1.0f);
}
