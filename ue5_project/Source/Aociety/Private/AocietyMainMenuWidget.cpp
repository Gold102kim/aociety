// Copyright Aociety. All rights reserved.

#include "AocietyMainMenuWidget.h"

#include "AocietyMainMenuGameMode.h"
#include "Brushes/SlateColorBrush.h"
#include "Brushes/SlateDynamicImageBrush.h"
#include "Engine/Engine.h"
#include "GameFramework/GameUserSettings.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Misc/Paths.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScaleBox.h"
#include "Widgets/Layout/SWidgetSwitcher.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Text/STextBlock.h"

namespace
{
const FLinearColor MenuTextColor(0.96f, 0.88f, 0.70f, 1.0f);
const FLinearColor MutedTextColor(0.75f, 0.66f, 0.54f, 1.0f);
const FLinearColor SelectionColor(0.38f, 0.16f, 0.055f, 0.88f);
const FLinearColor SelectionHoverColor(0.62f, 0.34f, 0.10f, 0.92f);
}

TSharedRef<SWidget> UAocietyMainMenuWidget::RebuildWidget()
{
    const FString MenuImagePath = FPaths::ConvertRelativePathToFull(
        FPaths::ProjectContentDir() / TEXT("Slate/AocietyMenuBackdrop.jpg"));
    MenuBackgroundBrush = MakeShared<FSlateDynamicImageBrush>(
        FName(*MenuImagePath),
        FVector2D(1920.0f, 1080.0f));

    const FString MenuLogoPath = FPaths::ConvertRelativePathToFull(
        FPaths::ProjectContentDir() / TEXT("Slate/AocietyLogoOverlay.png"));
    MenuLogoBrush = MakeShared<FSlateDynamicImageBrush>(
        FName(*MenuLogoPath),
        FVector2D(987.0f, 500.0f));

    NormalMenuButtonStyle = FButtonStyle()
        .SetNormal(FSlateColorBrush(FLinearColor(0.0f, 0.0f, 0.0f, 0.04f)))
        .SetHovered(FSlateColorBrush(SelectionColor))
        .SetPressed(FSlateColorBrush(SelectionHoverColor));

    SelectedMenuButtonStyle = FButtonStyle()
        .SetNormal(FSlateColorBrush(SelectionColor))
        .SetHovered(FSlateColorBrush(SelectionHoverColor))
        .SetPressed(FSlateColorBrush(SelectionHoverColor));

    auto MakeMenuButton = [this](
        const FString& Label,
        const FOnClicked& OnClicked,
        const bool bSelected = false)
    {
        return SNew(SButton)
            .ButtonStyle(bSelected ? &SelectedMenuButtonStyle : &NormalMenuButtonStyle)
            .ContentPadding(FMargin(12.0f, 5.0f))
            .OnClicked(OnClicked)
            [
                SNew(STextBlock)
                .Text(FText::FromString(Label))
                .Justification(ETextJustify::Center)
                .ColorAndOpacity(MenuTextColor)
                .ShadowOffset(FVector2D(1.0f, 1.0f))
                .ShadowColorAndOpacity(FLinearColor(0.0f, 0.0f, 0.0f, 0.9f))
                .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 18))
            ];
    };

    const TSharedRef<SWidget> MainMenuPanel =
        SNew(SVerticalBox)
        + SVerticalBox::Slot()
        .AutoHeight()
        .Padding(FMargin(0.0f, 0.0f, 0.0f, 7.0f))
        [
            SNew(STextBlock)
            .Text(FText::FromString(TEXT("MAIN MENU")))
            .Justification(ETextJustify::Center)
            .ColorAndOpacity(MutedTextColor)
            .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 12))
        ]
        + SVerticalBox::Slot()
        .AutoHeight()
        [
            MakeMenuButton(
                TEXT("进入世界"),
                FOnClicked::CreateUObject(this, &UAocietyMainMenuWidget::HandleEnterWorld),
                true)
        ]
        + SVerticalBox::Slot()
        .AutoHeight()
        [
            MakeMenuButton(
                TEXT("游戏设置"),
                FOnClicked::CreateUObject(this, &UAocietyMainMenuWidget::HandleOpenSettings))
        ]
        + SVerticalBox::Slot()
        .AutoHeight()
        [
            MakeMenuButton(
                TEXT("世界档案"),
                FOnClicked::CreateUObject(this, &UAocietyMainMenuWidget::HandleOpenArchive))
        ]
        + SVerticalBox::Slot()
        .AutoHeight()
        [
            MakeMenuButton(
                TEXT("退出游戏"),
                FOnClicked::CreateUObject(this, &UAocietyMainMenuWidget::HandleQuitGame))
        ];

    const TSharedRef<SWidget> SettingsPanel =
        SNew(SVerticalBox)
        + SVerticalBox::Slot()
        .AutoHeight()
        .Padding(FMargin(0.0f, 0.0f, 0.0f, 8.0f))
        [
            SNew(STextBlock)
            .Text(FText::FromString(TEXT("游戏设置")))
            .Justification(ETextJustify::Center)
            .ColorAndOpacity(MenuTextColor)
            .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 22))
        ]
        + SVerticalBox::Slot()
        .AutoHeight()
        [
            SNew(SButton)
            .ButtonStyle(&SelectedMenuButtonStyle)
            .ContentPadding(FMargin(12.0f, 7.0f))
            .OnClicked(FOnClicked::CreateUObject(
                this,
                &UAocietyMainMenuWidget::HandleToggleFullscreen))
            [
                SAssignNew(DisplayModeText, STextBlock)
                .Text(GetDisplayModeText())
                .Justification(ETextJustify::Center)
                .ColorAndOpacity(MenuTextColor)
                .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 17))
            ]
        ]
        + SVerticalBox::Slot()
        .AutoHeight()
        [
            MakeMenuButton(
                TEXT("返回主菜单"),
                FOnClicked::CreateUObject(this, &UAocietyMainMenuWidget::HandleBackToMainMenu))
        ];

    const TSharedRef<SWidget> ArchivePanel =
        SNew(SVerticalBox)
        + SVerticalBox::Slot()
        .AutoHeight()
        .Padding(FMargin(0.0f, 0.0f, 0.0f, 10.0f))
        [
            SNew(STextBlock)
            .Text(FText::FromString(TEXT("世界档案")))
            .Justification(ETextJustify::Center)
            .ColorAndOpacity(MenuTextColor)
            .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 22))
        ]
        + SVerticalBox::Slot()
        .AutoHeight()
        .Padding(FMargin(0.0f, 0.0f, 0.0f, 14.0f))
        [
            SNew(STextBlock)
            .Text(FText::FromString(TEXT("AOCIETY · 城镇纪元\n世界连接状态：稳定\n居民服务：在线")))
            .Justification(ETextJustify::Center)
            .ColorAndOpacity(MutedTextColor)
            .LineHeightPercentage(1.35f)
            .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 15))
        ]
        + SVerticalBox::Slot()
        .AutoHeight()
        [
            MakeMenuButton(
                TEXT("返回主菜单"),
                FOnClicked::CreateUObject(this, &UAocietyMainMenuWidget::HandleBackToMainMenu),
                true)
        ];

    return SNew(SOverlay)
        + SOverlay::Slot()
        [
            SNew(SScaleBox)
            .Stretch(EStretch::ScaleToFill)
            .StretchDirection(EStretchDirection::Both)
            [
                SNew(SImage)
                .Image(MenuBackgroundBrush.Get())
            ]
        ]
        + SOverlay::Slot()
        [
            SNew(SBorder)
            .BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush")))
            .BorderBackgroundColor(FLinearColor(0.05f, 0.018f, 0.008f, 0.14f))
        ]
        + SOverlay::Slot()
        .HAlign(HAlign_Center)
        .VAlign(VAlign_Top)
        .Padding(FMargin(0.0f, 22.0f, 0.0f, 0.0f))
        [
            SNew(SBox)
            .WidthOverride(680.0f)
            .HeightOverride(344.0f)
            [
                SNew(SScaleBox)
                .Stretch(EStretch::ScaleToFit)
                [
                    SNew(SImage)
                    .Image(MenuLogoBrush.Get())
                ]
            ]
        ]
        + SOverlay::Slot()
        .HAlign(HAlign_Center)
        .VAlign(VAlign_Center)
        .Padding(FMargin(0.0f, 255.0f, 0.0f, 0.0f))
        [
            SNew(SBox)
            .WidthOverride(380.0f)
            .HeightOverride(260.0f)
            [
                SAssignNew(MenuSwitcher, SWidgetSwitcher)
                + SWidgetSwitcher::Slot()
                [
                    MainMenuPanel
                ]
                + SWidgetSwitcher::Slot()
                [
                    SettingsPanel
                ]
                + SWidgetSwitcher::Slot()
                [
                    ArchivePanel
                ]
            ]
        ]
        + SOverlay::Slot()
        .VAlign(VAlign_Bottom)
        .Padding(FMargin(38.0f, 0.0f, 38.0f, 22.0f))
        [
            SNew(SHorizontalBox)
            + SHorizontalBox::Slot()
            .FillWidth(1.0f)
            [
                SNew(STextBlock)
                .Text(FText::FromString(TEXT("鼠标选择  ·  点击确认")))
                .ColorAndOpacity(MutedTextColor)
                .ShadowOffset(FVector2D(1.0f, 1.0f))
                .ShadowColorAndOpacity(FLinearColor::Black)
                .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 12))
            ]
            + SHorizontalBox::Slot()
            .AutoWidth()
            [
                SNew(STextBlock)
                .Text(FText::FromString(TEXT("AOCIETY  PRE-ALPHA  ·  BUILD 0.4")))
                .ColorAndOpacity(MutedTextColor)
                .ShadowOffset(FVector2D(1.0f, 1.0f))
                .ShadowColorAndOpacity(FLinearColor::Black)
                .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 12))
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

FReply UAocietyMainMenuWidget::HandleOpenSettings()
{
    if (MenuSwitcher.IsValid())
    {
        MenuSwitcher->SetActiveWidgetIndex(1);
    }
    return FReply::Handled();
}

FReply UAocietyMainMenuWidget::HandleOpenArchive()
{
    if (MenuSwitcher.IsValid())
    {
        MenuSwitcher->SetActiveWidgetIndex(2);
    }
    return FReply::Handled();
}

FReply UAocietyMainMenuWidget::HandleBackToMainMenu()
{
    if (MenuSwitcher.IsValid())
    {
        MenuSwitcher->SetActiveWidgetIndex(0);
    }
    return FReply::Handled();
}

FReply UAocietyMainMenuWidget::HandleToggleFullscreen()
{
    if (GEngine)
    {
        if (UGameUserSettings* UserSettings = GEngine->GetGameUserSettings())
        {
            const bool bIsWindowed =
                UserSettings->GetFullscreenMode() == EWindowMode::Windowed;
            UserSettings->SetFullscreenMode(
                bIsWindowed ? EWindowMode::Fullscreen : EWindowMode::Windowed);
            UserSettings->ApplySettings(false);
            if (DisplayModeText.IsValid())
            {
                DisplayModeText->SetText(GetDisplayModeText());
            }
        }
    }
    return FReply::Handled();
}

FText UAocietyMainMenuWidget::GetDisplayModeText() const
{
    if (GEngine)
    {
        if (const UGameUserSettings* UserSettings = GEngine->GetGameUserSettings())
        {
            const bool bIsWindowed =
                UserSettings->GetFullscreenMode() == EWindowMode::Windowed;
            return FText::FromString(
                bIsWindowed ? TEXT("显示模式  <  窗口化  >") : TEXT("显示模式  <  全屏  >"));
        }
    }
    return FText::FromString(TEXT("显示模式  <  窗口化  >"));
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
