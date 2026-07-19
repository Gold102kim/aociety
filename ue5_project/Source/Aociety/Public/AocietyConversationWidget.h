// Copyright Aociety. All rights reserved.

#pragma once

#include "CoreMinimal.h"
#include "AocietyClientSubsystem.h"
#include "Blueprint/UserWidget.h"
#include "Types/SlateEnums.h"
#include "AocietyConversationWidget.generated.h"

class APlayerController;
class SEditableTextBox;
class SScrollBox;
class STextBlock;
class UAocietyClientSubsystem;

UCLASS()
class AOCIETY_API UAocietyConversationWidget : public UUserWidget
{
    GENERATED_BODY()

public:
    void OpenChat(
        const FString& NpcId,
        const FString& DisplayName,
        UAocietyClientSubsystem* Client,
        APlayerController* PlayerController);
    void OpenInbox(
        UAocietyClientSubsystem* Client,
        APlayerController* PlayerController);
    void ClosePanel();
    bool IsPanelOpen() const;

protected:
    virtual TSharedRef<SWidget> RebuildWidget() override;
    virtual void NativeDestruct() override;

private:
    FReply HandleSendClicked();
    FReply HandleCloseClicked();
    FReply HandleLinxiClicked();
    FReply HandleSakuraClicked();
    void HandleTextCommitted(const FText& Text, ETextCommit::Type CommitType);

    UFUNCTION()
    void HandleConversationUpdated(
        FString NpcId,
        FAocietyConversationEntry Entry);

    void SelectResident(const FString& NpcId, const FString& DisplayName);
    void RefreshHistory();
    void SubmitCurrentText();
    void ApplyInputMode(bool bEnableUI);

    TWeakObjectPtr<UAocietyClientSubsystem> ClientSubsystem;
    TWeakObjectPtr<APlayerController> OwningController;
    FString CurrentNpcId = TEXT("npc_01");
    FString CurrentDisplayName = TEXT("林汐");
    bool bDelegateBound = false;

    TSharedPtr<STextBlock> HeaderText;
    TSharedPtr<STextBlock> HistoryText;
    TSharedPtr<SEditableTextBox> InputBox;
    TSharedPtr<SScrollBox> HistoryScroll;
};
