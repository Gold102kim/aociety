// Copyright Aociety. All rights reserved.

#include "AocietyMainMenuGameMode.h"

#include "AocietyMainMenuWidget.h"
#include "Blueprint/UserWidget.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "TimerManager.h"
#include "UnrealClient.h"

AAocietyMainMenuGameMode::AAocietyMainMenuGameMode()
{
    DefaultPawnClass = nullptr;
    HUDClass = nullptr;
    bStartPlayersAsSpectators = true;
}

void AAocietyMainMenuGameMode::BeginPlay()
{
    Super::BeginPlay();

    APlayerController* PlayerController =
        UGameplayStatics::GetPlayerController(this, 0);
    if (!PlayerController)
    {
        UE_LOG(LogTemp, Error, TEXT("[AocietyMainMenu] player controller unavailable"));
        return;
    }

    UAocietyMainMenuWidget* MenuWidget =
        CreateWidget<UAocietyMainMenuWidget>(
            PlayerController,
            UAocietyMainMenuWidget::StaticClass());
    if (!MenuWidget)
    {
        UE_LOG(LogTemp, Error, TEXT("[AocietyMainMenu] widget creation failed"));
        return;
    }

    MenuWidget->AddToViewport(1000);
    PlayerController->bShowMouseCursor = true;
    PlayerController->SetInputMode(FInputModeUIOnly());
    UE_LOG(LogTemp, Display, TEXT("[AocietyMainMenu] ready"));

    if (FParse::Param(FCommandLine::Get(), TEXT("AocietyMainMenuAudit")))
    {
        GetWorldTimerManager().SetTimer(
            AuditTimer,
            this,
            &AAocietyMainMenuGameMode::CaptureMenuAudit,
            1.5f,
            false);
    }

    if (FParse::Param(FCommandLine::Get(), TEXT("AocietyAutoEnterWorld")))
    {
        GetWorldTimerManager().SetTimer(
            AutoEnterTimer,
            this,
            &AAocietyMainMenuGameMode::EnterWorld,
            2.5f,
            false);
    }
}

void AAocietyMainMenuGameMode::EnterWorld()
{
    if (bTransitionStarted)
    {
        return;
    }
    bTransitionStarted = true;

    if (APlayerController* PlayerController =
            UGameplayStatics::GetPlayerController(this, 0))
    {
        PlayerController->bShowMouseCursor = false;
        PlayerController->SetInputMode(FInputModeGameOnly());
    }

    UE_LOG(LogTemp, Display, TEXT("[AocietyMainMenu] entering world"));
    UGameplayStatics::OpenLevel(
        this,
        FName(TEXT("/Game/Aociety/Maps/Aociety_ForestSnowTown")),
        true,
        TEXT("game=/Script/Aociety.AocietyGameMode"));
}

void AAocietyMainMenuGameMode::CaptureMenuAudit()
{
    const FString ArtifactDirectory = FPaths::ConvertRelativePathToFull(
        FPaths::Combine(FPaths::ProjectDir(), TEXT("../artifacts")));
    IFileManager::Get().MakeDirectory(*ArtifactDirectory, true);
    const FString ScreenshotPath = FPaths::Combine(
        ArtifactDirectory,
        TEXT("main_menu.png"));
    FScreenshotRequest::RequestScreenshot(ScreenshotPath, true, false);
    UE_LOG(
        LogTemp,
        Display,
        TEXT("[AocietyMainMenuAudit] screenshot=%s"),
        *ScreenshotPath);
}
