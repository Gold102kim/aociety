// Copyright Aociety. All rights reserved.

#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "Input/Reply.h"
#include "AocietyPauseMenuWidget.generated.h"

class APlayerController;

UCLASS()
class AOCIETY_API UAocietyPauseMenuWidget : public UUserWidget
{
    GENERATED_BODY()

public:
    void Open(APlayerController* PlayerController);
    void Close();
    bool IsMenuOpen() const;

protected:
    virtual TSharedRef<SWidget> RebuildWidget() override;

private:
    FReply HandleResumeClicked();
    FReply HandleMainMenuClicked();
    FReply HandleQuitClicked();
    void ApplyInputMode(bool bEnableUI);

    TWeakObjectPtr<APlayerController> OwningController;
};
