// Copyright Aociety. All rights reserved.

#include "AocietyNPCBubbleWidget.h"

#include "Styling/AppStyle.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Text/STextBlock.h"

TSharedRef<SWidget> UAocietyNPCBubbleWidget::RebuildWidget()
{
    return SNew(SBorder)
        .BorderImage(FAppStyle::GetBrush(TEXT("WhiteBrush")))
        .BorderBackgroundColor(FLinearColor(0.012f, 0.02f, 0.035f, 0.96f))
        .Padding(FMargin(16.0f, 11.0f))
        [
            SAssignNew(SlateText, STextBlock)
            .Text(FText::FromString(BubbleText))
            .ColorAndOpacity(bIsThinking
                ? FLinearColor(1.0f, 0.78f, 0.32f, 1.0f)
                : FLinearColor(0.88f, 0.96f, 1.0f, 1.0f))
            .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 22))
            .AutoWrapText(true)
            .WrapTextAt(420.0f)
            .Justification(ETextJustify::Center)
        ];
}

void UAocietyNPCBubbleWidget::SetBubbleText(const FString& InText, bool bThinking)
{
    BubbleText = InText;
    bIsThinking = bThinking;
    if (SlateText.IsValid())
    {
        SlateText->SetText(FText::FromString(BubbleText));
        SlateText->SetColorAndOpacity(bIsThinking
            ? FSlateColor(FLinearColor(1.0f, 0.78f, 0.32f, 1.0f))
            : FSlateColor(FLinearColor(0.88f, 0.96f, 1.0f, 1.0f)));
    }
}
