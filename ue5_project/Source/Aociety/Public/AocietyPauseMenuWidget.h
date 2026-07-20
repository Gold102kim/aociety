// Copyright Aociety. All rights reserved.

#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "AocietyPauseMenuWidget.generated.h"

class APlayerController;
class STextBlock;

/** Small runtime pause menu kept in C++ so the demo has no external widget asset dependency. */
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
    FReply HandleQuitClicked();
    void ApplyInputMode(bool bEnableUI);

    TWeakObjectPtr<APlayerController> OwningController;
};
