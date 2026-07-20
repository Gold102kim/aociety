// Copyright Aociety. All rights reserved.

#include "AocietyPauseMenuWidget.h"

#include "Blueprint/WidgetBlueprintLibrary.h"
#include "Framework/Application/SlateApplication.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Text/STextBlock.h"

TSharedRef<SWidget> UAocietyPauseMenuWidget::RebuildWidget()
{
    return SNew(SOverlay)
        + SOverlay::Slot()
        .HAlign(HAlign_Center)
        .VAlign(VAlign_Center)
        [
            SNew(SBox)
            .WidthOverride(420.0f)
            .HeightOverride(300.0f)
            [
                SNew(SBorder)
                .BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush")))
                .BorderBackgroundColor(FLinearColor(0.025f, 0.035f, 0.055f, 0.97f))
                .Padding(FMargin(34.0f))
                [
                    SNew(SVerticalBox)
                    + SVerticalBox::Slot()
                    .AutoHeight()
                    .HAlign(HAlign_Center)
                    .Padding(FMargin(0.0f, 0.0f, 0.0f, 28.0f))
                    [
                        SNew(STextBlock)
                        .Text(FText::FromString(TEXT("AOCIETY")))
                        .ColorAndOpacity(FLinearColor(0.92f, 0.96f, 1.0f, 1.0f))
                        .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 28))
                    ]
                    + SVerticalBox::Slot()
                    .AutoHeight()
                    .Padding(FMargin(0.0f, 0.0f, 0.0f, 12.0f))
                    [
                        SNew(SButton)
                        .HAlign(HAlign_Center)
                        .OnClicked_UObject(this, &UAocietyPauseMenuWidget::HandleResumeClicked)
                        [
                            SNew(STextBlock)
                            .Text(FText::FromString(TEXT("返回游戏")))
                            .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 19))
                        ]
                    ]
                    + SVerticalBox::Slot()
                    .AutoHeight()
                    [
                        SNew(SButton)
                        .HAlign(HAlign_Center)
                        .OnClicked_UObject(this, &UAocietyPauseMenuWidget::HandleQuitClicked)
                        [
                            SNew(STextBlock)
                            .Text(FText::FromString(TEXT("退出游戏")))
                            .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 19))
                        ]
                    ]
                ]
            ]
        ];
}

void UAocietyPauseMenuWidget::Open(APlayerController* PlayerController)
{
    OwningController = PlayerController;
    SetVisibility(ESlateVisibility::Visible);
    ApplyInputMode(true);
}

void UAocietyPauseMenuWidget::Close()
{
    SetVisibility(ESlateVisibility::Collapsed);
    ApplyInputMode(false);
}

bool UAocietyPauseMenuWidget::IsMenuOpen() const
{
    return GetVisibility() != ESlateVisibility::Collapsed
        && GetVisibility() != ESlateVisibility::Hidden;
}

FReply UAocietyPauseMenuWidget::HandleResumeClicked()
{
    Close();
    return FReply::Handled();
}

FReply UAocietyPauseMenuWidget::HandleQuitClicked()
{
    if (APlayerController* Controller = OwningController.Get())
    {
        UKismetSystemLibrary::QuitGame(
            Controller, nullptr, EQuitPreference::Quit, false);
    }
    return FReply::Handled();
}

void UAocietyPauseMenuWidget::ApplyInputMode(bool bEnableUI)
{
    APlayerController* Controller = OwningController.Get();
    if (!Controller)
    {
        return;
    }

    if (bEnableUI)
    {
        Controller->SetPause(true);
        FInputModeGameAndUI InputMode;
        InputMode.SetWidgetToFocus(TakeWidget());
        InputMode.SetHideCursorDuringCapture(false);
        InputMode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
        Controller->SetInputMode(InputMode);
        Controller->bShowMouseCursor = true;
    }
    else
    {
        Controller->SetPause(false);
        FInputModeGameOnly InputMode;
        Controller->SetInputMode(InputMode);
        Controller->bShowMouseCursor = false;
        if (FSlateApplication::IsInitialized())
        {
            FSlateApplication::Get().ClearKeyboardFocus(EFocusCause::Cleared);
        }
    }
}
