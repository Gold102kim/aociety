// Copyright Aociety. All rights reserved.

#include "AocietyConversationWidget.h"

#include "AocietyNPCCharacter.h"
#include "EngineUtils.h"
#include "Framework/Application/SlateApplication.h"
#include "GameFramework/PlayerController.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Text/STextBlock.h"

TSharedRef<SWidget> UAocietyConversationWidget::RebuildWidget()
{
    return SNew(SOverlay)
        + SOverlay::Slot()
        .HAlign(HAlign_Center)
        .VAlign(VAlign_Center)
        [
            SNew(SBox)
            .WidthOverride(920.0f)
            .HeightOverride(640.0f)
            [
                SNew(SBorder)
                .BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush")))
                .BorderBackgroundColor(FLinearColor(0.025f, 0.035f, 0.055f, 0.94f))
                .Padding(FMargin(28.0f))
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
                            SAssignNew(HeaderText, STextBlock)
                            .Text(FText::FromString(TEXT("居民收件箱 · 林汐")))
                            .ColorAndOpacity(FLinearColor(0.94f, 0.97f, 1.0f, 1.0f))
                            .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Bold"), 26))
                        ]
                        + SHorizontalBox::Slot()
                        .AutoWidth()
                        [
                            SNew(SButton)
                            .Text(FText::FromString(TEXT("关闭")))
                            .OnClicked_UObject(this, &UAocietyConversationWidget::HandleCloseClicked)
                        ]
                    ]
                    + SVerticalBox::Slot()
                    .AutoHeight()
                    .Padding(FMargin(0.0f, 16.0f, 0.0f, 12.0f))
                    [
                        SNew(SHorizontalBox)
                        + SHorizontalBox::Slot()
                        .AutoWidth()
                        .Padding(FMargin(0.0f, 0.0f, 10.0f, 0.0f))
                        [
                            SNew(SButton)
                            .Text(FText::FromString(TEXT("林汐")))
                            .OnClicked_UObject(this, &UAocietyConversationWidget::HandleLinxiClicked)
                        ]
                        + SHorizontalBox::Slot()
                        .AutoWidth()
                        [
                            SNew(SButton)
                            .Text(FText::FromString(TEXT("小樱")))
                            .OnClicked_UObject(this, &UAocietyConversationWidget::HandleSakuraClicked)
                        ]
                        + SHorizontalBox::Slot()
                        .FillWidth(1.0f)
                        .HAlign(HAlign_Right)
                        .VAlign(VAlign_Center)
                        [
                            SNew(STextBlock)
                            .Text(FText::FromString(TEXT("I 打开收件箱 · E 与附近居民交谈 · Enter 发送")))
                            .ColorAndOpacity(FLinearColor(0.55f, 0.64f, 0.76f, 1.0f))
                            .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 13))
                        ]
                    ]
                    + SVerticalBox::Slot()
                    .FillHeight(1.0f)
                    [
                        SNew(SBorder)
                        .BorderImage(FCoreStyle::Get().GetBrush(TEXT("WhiteBrush")))
                        .BorderBackgroundColor(FLinearColor(0.06f, 0.08f, 0.12f, 0.90f))
                        .Padding(FMargin(20.0f))
                        [
                            SAssignNew(HistoryScroll, SScrollBox)
                            + SScrollBox::Slot()
                            [
                                SAssignNew(HistoryText, STextBlock)
                                .Text(FText::FromString(TEXT("暂无历史会话")))
                                .ColorAndOpacity(FLinearColor(0.90f, 0.93f, 0.98f, 1.0f))
                                .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 17))
                                .AutoWrapText(true)
                                .WrapTextAt(820.0f)
                            ]
                        ]
                    ]
                    + SVerticalBox::Slot()
                    .AutoHeight()
                    .Padding(FMargin(0.0f, 16.0f, 0.0f, 0.0f))
                    [
                        SNew(SHorizontalBox)
                        + SHorizontalBox::Slot()
                        .FillWidth(1.0f)
                        [
                            SAssignNew(InputBox, SEditableTextBox)
                            .HintText(FText::FromString(TEXT("输入你想对居民说的话…")))
                            .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), 18))
                            .OnTextCommitted_UObject(
                                this,
                                &UAocietyConversationWidget::HandleTextCommitted)
                        ]
                        + SHorizontalBox::Slot()
                        .AutoWidth()
                        .Padding(FMargin(12.0f, 0.0f, 0.0f, 0.0f))
                        [
                            SNew(SButton)
                            .Text(FText::FromString(TEXT("发送")))
                            .OnClicked_UObject(this, &UAocietyConversationWidget::HandleSendClicked)
                        ]
                    ]
                ]
            ]
        ];
}

void UAocietyConversationWidget::OpenChat(
    const FString& NpcId,
    const FString& DisplayName,
    UAocietyClientSubsystem* Client,
    APlayerController* PlayerController)
{
    ClientSubsystem = Client;
    OwningController = PlayerController;
    if (Client && !bDelegateBound)
    {
        Client->OnConversationUpdated.AddDynamic(
            this, &UAocietyConversationWidget::HandleConversationUpdated);
        bDelegateBound = true;
    }
    SelectResident(NpcId, DisplayName);
    SetVisibility(ESlateVisibility::Visible);
    ApplyInputMode(true);
    if (InputBox.IsValid())
    {
        FSlateApplication::Get().SetKeyboardFocus(
            InputBox, EFocusCause::SetDirectly);
    }
}

void UAocietyConversationWidget::OpenInbox(
    UAocietyClientSubsystem* Client,
    APlayerController* PlayerController)
{
    OpenChat(CurrentNpcId, CurrentDisplayName, Client, PlayerController);
}

void UAocietyConversationWidget::ClosePanel()
{
    SetVisibility(ESlateVisibility::Collapsed);
    ApplyInputMode(false);
}

bool UAocietyConversationWidget::IsPanelOpen() const
{
    return GetVisibility() != ESlateVisibility::Collapsed
        && GetVisibility() != ESlateVisibility::Hidden;
}

void UAocietyConversationWidget::NativeDestruct()
{
    if (UAocietyClientSubsystem* Client = ClientSubsystem.Get())
    {
        Client->OnConversationUpdated.RemoveDynamic(
            this, &UAocietyConversationWidget::HandleConversationUpdated);
    }
    bDelegateBound = false;
    Super::NativeDestruct();
}

FReply UAocietyConversationWidget::HandleSendClicked()
{
    SubmitCurrentText();
    return FReply::Handled();
}

FReply UAocietyConversationWidget::HandleCloseClicked()
{
    ClosePanel();
    return FReply::Handled();
}

FReply UAocietyConversationWidget::HandleLinxiClicked()
{
    SelectResident(TEXT("npc_01"), TEXT("林汐"));
    return FReply::Handled();
}

FReply UAocietyConversationWidget::HandleSakuraClicked()
{
    SelectResident(TEXT("npc_02"), TEXT("小樱"));
    return FReply::Handled();
}

void UAocietyConversationWidget::HandleTextCommitted(
    const FText& Text,
    ETextCommit::Type CommitType)
{
    if (CommitType == ETextCommit::OnEnter)
    {
        SubmitCurrentText();
    }
}

void UAocietyConversationWidget::HandleConversationUpdated(
    FString NpcId,
    FAocietyConversationEntry Entry)
{
    if (NpcId == CurrentNpcId)
    {
        RefreshHistory();
    }
}

void UAocietyConversationWidget::SelectResident(
    const FString& NpcId,
    const FString& DisplayName)
{
    CurrentNpcId = NpcId;
    CurrentDisplayName = DisplayName;
    if (HeaderText.IsValid())
    {
        HeaderText->SetText(FText::FromString(
            FString::Printf(TEXT("居民收件箱 · %s"), *CurrentDisplayName)));
    }
    RefreshHistory();
}

void UAocietyConversationWidget::RefreshHistory()
{
    if (!HistoryText.IsValid())
    {
        return;
    }
    const UAocietyClientSubsystem* Client = ClientSubsystem.Get();
    const TArray<FAocietyConversationEntry> History = Client
        ? Client->GetConversationHistory(CurrentNpcId)
        : TArray<FAocietyConversationEntry>();
    FString Transcript;
    for (const FAocietyConversationEntry& Entry : History)
    {
        const FString SenderName = Entry.bFromPlayer
            ? TEXT("你")
            : (Entry.Sender == TEXT("npc_01") ? TEXT("林汐")
                : Entry.Sender == TEXT("npc_02") ? TEXT("小樱")
                : CurrentDisplayName);
        const FString Time = Entry.Timestamp.Len() >= 16
            ? Entry.Timestamp.Mid(11, 5)
            : TEXT("--:--");
        Transcript += FString::Printf(
            TEXT("[%s] %s\n%s\n%s · %s\n\n"),
            *Time,
            *SenderName,
            *Entry.Text,
            *Entry.Source,
            *Entry.Model);
    }
    if (Transcript.IsEmpty())
    {
        Transcript = FString::Printf(
            TEXT("还没有与 %s 的历史会话。\n在下方输入消息并按 Enter。"),
            *CurrentDisplayName);
    }
    HistoryText->SetText(FText::FromString(Transcript));
    if (HistoryScroll.IsValid())
    {
        HistoryScroll->ScrollToEnd();
    }
}

void UAocietyConversationWidget::SubmitCurrentText()
{
    UAocietyClientSubsystem* Client = ClientSubsystem.Get();
    if (!Client || !InputBox.IsValid())
    {
        return;
    }
    FString Text = InputBox->GetText().ToString();
    Text.TrimStartAndEndInline();
    if (Text.IsEmpty())
    {
        return;
    }
    InputBox->SetText(FText::GetEmpty());
    for (TActorIterator<AAocietyNPCCharacter> It(GetWorld()); It; ++It)
    {
        if (It->NpcId == CurrentNpcId)
        {
            It->ShowThinking();
            break;
        }
    }
    Client->RequestNPCDialogue(
        CurrentNpcId,
        Text,
        TEXT("forest_town"),
        TEXT("player_typed_chat"));
    RefreshHistory();
}

void UAocietyConversationWidget::ApplyInputMode(bool bEnableUI)
{
    APlayerController* Controller = OwningController.Get();
    if (!Controller)
    {
        return;
    }
    if (bEnableUI)
    {
        FInputModeGameAndUI InputMode;
        InputMode.SetWidgetToFocus(TakeWidget());
        InputMode.SetHideCursorDuringCapture(false);
        InputMode.SetLockMouseToViewportBehavior(
            EMouseLockMode::DoNotLock);
        Controller->SetInputMode(InputMode);
        Controller->bShowMouseCursor = true;
    }
    else
    {
        FInputModeGameOnly InputMode;
        Controller->SetInputMode(InputMode);
        Controller->bShowMouseCursor = false;
    }
}
