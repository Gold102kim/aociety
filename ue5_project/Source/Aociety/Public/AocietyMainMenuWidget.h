// Copyright Aociety. All rights reserved.

#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "Input/Reply.h"
#include "Styling/SlateTypes.h"
#include "AocietyMainMenuWidget.generated.h"

struct FSlateDynamicImageBrush;
class STextBlock;
class SWidgetSwitcher;

UCLASS()
class AOCIETY_API UAocietyMainMenuWidget : public UUserWidget
{
    GENERATED_BODY()

protected:
    virtual TSharedRef<SWidget> RebuildWidget() override;

private:
    FReply HandleEnterWorld();
    FReply HandleOpenSettings();
    FReply HandleOpenArchive();
    FReply HandleBackToMainMenu();
    FReply HandleToggleFullscreen();
    FReply HandleQuitGame();
    FText GetDisplayModeText() const;

    TSharedPtr<FSlateDynamicImageBrush> MenuBackgroundBrush;
    TSharedPtr<FSlateDynamicImageBrush> MenuLogoBrush;
    TSharedPtr<SWidgetSwitcher> MenuSwitcher;
    TSharedPtr<STextBlock> DisplayModeText;
    FButtonStyle NormalMenuButtonStyle;
    FButtonStyle SelectedMenuButtonStyle;
};
