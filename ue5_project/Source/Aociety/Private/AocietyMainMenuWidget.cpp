// Copyright Aociety. All rights reserved.

#include "AocietyMainMenuWidget.h"

#include "AocietyMainMenuGameMode.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/SOverlay.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"

namespace
{
const FLinearColor BackgroundColor(0.012f, 0.020f, 0.034f, 1.0f);
const FLinearColor PanelColor(0.025f, 0.045f, 0.065f, 0.94f);
const FLinearColor AccentColor(0.20f, 0.92f, 0.78f, 1.0f);
const FLinearColor MutedColor(0.56f, 0.64f, 0.70f, 1.0f);
}

TSharedRef<SWidget> UAocietyMainMenuWidget::RebuildWidget()
{
    return SNew(SOverlay)
        + SOverlay::Slot()
        [
            SNew(SBorder)
            .BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush")))
            .BorderBackgroundColor(BackgroundColor)
        ]
        + SOverlay::Slot()
        .HAlign(HAlign_Right)
        [
            SNew(SBox)
            .WidthOverride(540.0f)
            [
                SNew(SBorder)
                .BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush")))
                .BorderBackgroundColor(FLinearColor(0.025f, 0.12f, 0.12f, 0.22f))
            ]
        ]
        + SOverlay::Slot()
        .Padding(FMargin(72.0f, 52.0f))
        [
            SNew(SVerticalBox)
            + SVerticalBox::Slot()
            .AutoHeight()
            [
                SNew(SHorizontalBox)
                + SHorizontalBox::Slot()
                .AutoWidth()
                .VAlign(VAlign_Center)
                [
                    SNew(SBorder)
                    .BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush")))
                    .BorderBackgroundColor(AccentColor)
                    .Padding(FMargin(10.0f, 5.0f))
                    [
                        SNew(STextBlock)
                        .Text(FText::FromString(TEXT("E")))
                        .ColorAndOpacity(BackgroundColor)
                        .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 18))
                    ]
                ]
                + SHorizontalBox::Slot()
                .AutoWidth()
                .Padding(FMargin(14.0f, 0.0f))
                .VAlign(VAlign_Center)
                [
                    SNew(STextBlock)
                    .Text(FText::FromString(TEXT("ECHOVERSE")))
                    .ColorAndOpacity(FLinearColor::White)
                    .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 20))
                ]
                + SHorizontalBox::Slot()
                .FillWidth(1.0f)
                + SHorizontalBox::Slot()
                .AutoWidth()
                .VAlign(VAlign_Center)
                [
                    SNew(STextBlock)
                    .Text(FText::FromString(TEXT("●  神经链接已就绪")))
                    .ColorAndOpacity(AccentColor)
                    .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 14))
                ]
            ]
            + SVerticalBox::Slot()
            .FillHeight(1.0f)
            .Padding(FMargin(0.0f, 42.0f, 0.0f, 30.0f))
            [
                SNew(SHorizontalBox)
                + SHorizontalBox::Slot()
                .FillWidth(1.0f)
                .VAlign(VAlign_Center)
                [
                    SNew(SVerticalBox)
                    + SVerticalBox::Slot()
                    .AutoHeight()
                    [
                        SNew(STextBlock)
                        .Text(FText::FromString(TEXT("YOUR OTHER SELF\nIS WAITING")))
                        .ColorAndOpacity(AccentColor)
                        .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 15))
                    ]
                    + SVerticalBox::Slot()
                    .AutoHeight()
                    .Padding(FMargin(0.0f, 20.0f, 0.0f, 0.0f))
                    [
                        SNew(STextBlock)
                        .Text(FText::FromString(TEXT("另一个世界，\n正在记住你。")))
                        .ColorAndOpacity(FLinearColor(0.95f, 0.98f, 1.0f, 1.0f))
                        .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 58))
                        .LineHeightPercentage(0.92f)
                    ]
                    + SVerticalBox::Slot()
                    .AutoHeight()
                    .Padding(FMargin(0.0f, 24.0f, 0.0f, 0.0f))
                    [
                        SNew(STextBlock)
                        .Text(FText::FromString(TEXT("进入属于你的数字世界。每一次选择、相遇与行动，\n都会成为虚拟分身继续成长的记忆。")))
                        .ColorAndOpacity(MutedColor)
                        .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 18))
                        .LineHeightPercentage(1.35f)
                    ]
                ]
                + SHorizontalBox::Slot()
                .AutoWidth()
                .VAlign(VAlign_Center)
                [
                    SNew(SBox)
                    .WidthOverride(410.0f)
                    [
                        SNew(SBorder)
                        .BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush")))
                        .BorderBackgroundColor(PanelColor)
                        .Padding(FMargin(36.0f, 42.0f))
                        [
                            SNew(SVerticalBox)
                            + SVerticalBox::Slot()
                            .AutoHeight()
                            [
                                SNew(STextBlock)
                                .Text(FText::FromString(TEXT("欢迎回来")))
                                .ColorAndOpacity(FLinearColor::White)
                                .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 28))
                            ]
                            + SVerticalBox::Slot()
                            .AutoHeight()
                            .Padding(FMargin(0.0f, 8.0f, 0.0f, 30.0f))
                            [
                                SNew(STextBlock)
                                .Text(FText::FromString(TEXT("世界连接稳定，居民服务在线。")))
                                .ColorAndOpacity(MutedColor)
                                .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 15))
                            ]
                            + SVerticalBox::Slot()
                            .AutoHeight()
                            [
                                SNew(SButton)
                                .ContentPadding(FMargin(24.0f, 16.0f))
                                .ButtonColorAndOpacity(AccentColor)
                                .OnClicked(FOnClicked::CreateUObject(
                                    this,
                                    &UAocietyMainMenuWidget::HandleEnterWorld))
                                [
                                    SNew(STextBlock)
                                    .Text(FText::FromString(TEXT("进入世界")))
                                    .Justification(ETextJustify::Center)
                                    .ColorAndOpacity(FLinearColor::White)
                                    .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 20))
                                ]
                            ]
                            + SVerticalBox::Slot()
                            .AutoHeight()
                            .Padding(FMargin(0.0f, 14.0f, 0.0f, 0.0f))
                            [
                                SNew(SButton)
                                .ContentPadding(FMargin(24.0f, 13.0f))
                                .ButtonColorAndOpacity(FLinearColor(0.12f, 0.16f, 0.20f, 1.0f))
                                .OnClicked(FOnClicked::CreateUObject(
                                    this,
                                    &UAocietyMainMenuWidget::HandleQuitGame))
                                [
                                    SNew(STextBlock)
                                    .Text(FText::FromString(TEXT("退出游戏")))
                                    .Justification(ETextJustify::Center)
                                    .ColorAndOpacity(FLinearColor(0.82f, 0.86f, 0.90f, 1.0f))
                                    .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 16))
                                ]
                            ]
                            + SVerticalBox::Slot()
                            .AutoHeight()
                            .Padding(FMargin(0.0f, 28.0f, 0.0f, 0.0f))
                            [
                                SNew(STextBlock)
                                .Text(FText::FromString(TEXT("PRE-ALPHA  ·  LAUNCHER SESSION VERIFIED")))
                                .ColorAndOpacity(FLinearColor(0.36f, 0.48f, 0.52f, 1.0f))
                                .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 11))
                                .Justification(ETextJustify::Center)
                            ]
                        ]
                    ]
                ]
            ]
            + SVerticalBox::Slot()
            .AutoHeight()
            [
                SNew(SHorizontalBox)
                + SHorizontalBox::Slot()
                .FillWidth(1.0f)
                [
                    SNew(STextBlock)
                    .Text(FText::FromString(TEXT("AOCIETY NETWORK  /  ECHOVERSE")))
                    .ColorAndOpacity(FLinearColor(0.32f, 0.40f, 0.44f, 1.0f))
                    .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 12))
                ]
                + SHorizontalBox::Slot()
                .AutoWidth()
                [
                    SNew(STextBlock)
                    .Text(FText::FromString(TEXT("BUILD 0.4  ·  简体中文")))
                    .ColorAndOpacity(FLinearColor(0.32f, 0.40f, 0.44f, 1.0f))
                    .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 12))
                ]
            ]
        ];
}

FReply UAocietyMainMenuWidget::HandleEnterWorld()
{
    if (UWorld* World = GetWorld())
    {
        if (AAocietyMainMenuGameMode* GameMode =
                World->GetAuthGameMode<AAocietyMainMenuGameMode>())
        {
            GameMode->EnterWorld();
        }
    }
    return FReply::Handled();
}

FReply UAocietyMainMenuWidget::HandleQuitGame()
{
    APlayerController* PlayerController = GetOwningPlayer();
    UKismetSystemLibrary::QuitGame(
        this,
        PlayerController,
        EQuitPreference::Quit,
        false);
    return FReply::Handled();
}
