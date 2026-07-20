// Copyright Aociety. All rights reserved.

#include "AocietyPlayerCharacter.h"
#include "AocietyClientSubsystem.h"
#include "AocietyConversationWidget.h"
#include "AocietyPauseMenuWidget.h"
#include "AocietyEcyRetargetAnimInstance.h"
#include "AocietyMotionMatchingAnimInstance.h"
#include "AocietyNPCCharacter.h"

#include "Camera/CameraComponent.h"
#include "Blueprint/UserWidget.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/Controller.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"
#include "HAL/FileManager.h"
#include "Engine/GameInstance.h"
#include "EngineUtils.h"
#include "Misc/App.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "UnrealClient.h"
#include "UObject/ConstructorHelpers.h"
#include "PoseSearch/PoseSearchDatabase.h"
#include "Retargeter/IKRetargeter.h"

AAocietyPlayerCharacter::AAocietyPlayerCharacter()
{
    PrimaryActorTick.bCanEverTick = true;
    GetCapsuleComponent()->InitCapsuleSize(42.0f, 88.0f);

    bUseControllerRotationPitch = false;
    bUseControllerRotationYaw = false;
    bUseControllerRotationRoll = false;

    UCharacterMovementComponent* Movement = GetCharacterMovement();
    Movement->bOrientRotationToMovement = true;
    Movement->RotationRate = FRotator(0.0f, 540.0f, 0.0f);
    Movement->JumpZVelocity = 520.0f;
    Movement->AirControl = 0.35f;
    Movement->MaxWalkSpeed = 420.0f;

    CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
    CameraBoom->SetupAttachment(RootComponent);
    CameraBoom->SetRelativeLocation(FVector(0.0f, 0.0f, 105.0f));
    CameraBoom->TargetArmLength = 360.0f;
    CameraBoom->SocketOffset = FVector(0.0f, 0.0f, 20.0f);
    CameraBoom->bUsePawnControlRotation = true;
    CameraBoom->bDoCollisionTest = true;
    CameraBoom->ProbeSize = 18.0f;
    CameraBoom->ProbeChannel = ECC_Camera;
    CameraBoom->bEnableCameraLag = false;

    FollowCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FollowCamera"));
    FollowCamera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
    FollowCamera->bUsePawnControlRotation = false;

    MotionDriverMesh = CreateDefaultSubobject<USkeletalMeshComponent>(
        TEXT("MotionMatchingDriver"));
    MotionDriverMesh->SetupAttachment(GetCapsuleComponent());
    MotionDriverMesh->SetRelativeLocation(FVector(0.0f, 0.0f, -88.0f));
    MotionDriverMesh->SetRelativeRotation(FRotator(0.0f, -90.0f, 0.0f));
    MotionDriverMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    MotionDriverMesh->SetGenerateOverlapEvents(false);
    MotionDriverMesh->SetReceivesDecals(false);
    MotionDriverMesh->SetHiddenInGame(true);
    MotionDriverMesh->SetVisibility(false, true);
    MotionDriverMesh->SetCastShadow(false);
    MotionDriverMesh->VisibilityBasedAnimTickOption =
        EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;

    GetMesh()->SetReceivesDecals(false);

    static ConstructorHelpers::FObjectFinder<USkeletalMesh> EcyMesh(
        TEXT("/Game/Aociety/Characters/Ecy/SK_Ecy.SK_Ecy"));
    if (EcyMesh.Succeeded())
    {
        GetMesh()->SetSkeletalMeshAsset(EcyMesh.Object);
        GetMesh()->SetRelativeLocation(FVector(0.0f, 0.0f, -88.0f));
        GetMesh()->SetRelativeRotation(FRotator(0.0f, -90.0f, 0.0f));
        GetMesh()->SetRelativeScale3D(FVector(1.55f));
        GetMesh()->SetAnimationMode(EAnimationMode::AnimationBlueprint);
        GetMesh()->SetAnimInstanceClass(
            UAocietyEcyRetargetAnimInstance::StaticClass());
        GetMesh()->VisibilityBasedAnimTickOption =
            EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
        GetMesh()->bComponentUseFixedSkelBounds = true;
        GetMesh()->SetBoundsScale(1.5f);
        GetMesh()->SetTeleportDistanceThreshold(140.0f);
        GetMesh()->SetTeleportRotationThreshold(75.0f);
        GetMesh()->AddTickPrerequisiteComponent(MotionDriverMesh);
    }

}

void AAocietyPlayerCharacter::BeginPlay()
{
    Super::BeginPlay();

    GetMesh()->SetReceivesDecals(false);
    MotionDriverMesh->SetReceivesDecals(false);

    const bool bRuntimeAuditRequested =
        FParse::Param(FCommandLine::Get(), TEXT("AocietyRuntimeAudit"));
    const UWorld* World = GetWorld();
    bRuntimeAuditEnabled = bRuntimeAuditRequested
        && FApp::IsUnattended()
        && World
        && World->WorldType == EWorldType::Game;
    if (bRuntimeAuditRequested && !bRuntimeAuditEnabled)
    {
        UE_LOG(
            LogTemp,
            Display,
            TEXT("[AocietyRuntimeAudit] ignored outside standalone game world_type=%d"),
            World ? static_cast<int32>(World->WorldType) : -1);
    }

    const bool bMotionMatchingEnabled = !FApp::IsGame()
        || FParse::Param(FCommandLine::Get(), TEXT("AocietyEnableMotionMatching"));
    USkeletalMesh* MannyDriverAsset = !bMotionMatchingEnabled
        ? nullptr
        : LoadObject<USkeletalMesh>(
            nullptr,
            TEXT("/Game/Aociety/MotionMatching/SKM_Manny_Aociety.SKM_Manny_Aociety"));
    MotionDatabase = !bMotionMatchingEnabled
        ? nullptr
        : LoadObject<UPoseSearchDatabase>(
            nullptr,
            TEXT("/Game/Aociety/MotionMatching/PSDB_EcyLocomotion.PSDB_EcyLocomotion"));
    EcyRetargeter = !bMotionMatchingEnabled
        ? nullptr
        : LoadObject<UIKRetargeter>(
            nullptr,
            TEXT("/Game/Aociety/MotionMatching/RTG_MannyToEcy.RTG_MannyToEcy"));
    MotionDriverMesh->SetSkeletalMeshAsset(MannyDriverAsset);
    const int32 RuntimePoseCount = bMotionMatchingEnabled && MotionDatabase
        ? MotionDatabase->GetSearchIndex().GetNumPoses()
        : 0;
    const bool bMotionMatchingReady = MannyDriverAsset
        && MotionDatabase
        && EcyRetargeter
        && RuntimePoseCount > 0;

    UAocietyMotionMatchingAnimInstance* MotionInstance = nullptr;
    UAocietyEcyRetargetAnimInstance* EcyInstance = nullptr;
    bool bRetargetReady = false;
    if (bMotionMatchingReady)
    {
        MotionDriverMesh->SetAnimationMode(EAnimationMode::AnimationBlueprint);
        MotionDriverMesh->SetAnimInstanceClass(
            UAocietyMotionMatchingAnimInstance::StaticClass());
        MotionDriverMesh->InitAnim(true);
        GetMesh()->InitAnim(true);

        MotionInstance = Cast<UAocietyMotionMatchingAnimInstance>(
            MotionDriverMesh->GetAnimInstance());
        if (MotionInstance)
        {
            MotionInstance->ConfigureDatabase(MotionDatabase);
        }

        EcyInstance = Cast<UAocietyEcyRetargetAnimInstance>(
            GetMesh()->GetAnimInstance());
        bRetargetReady = EcyInstance
            && EcyInstance->ConfigureRetarget(EcyRetargeter, MotionDriverMesh);
    }
    else
    {
        MotionDriverMesh->SetAnimationMode(EAnimationMode::AnimationSingleNode);
        MotionDriverMesh->SetComponentTickEnabled(false);
        GetMesh()->SetAnimationMode(EAnimationMode::AnimationSingleNode);
        GetMesh()->InitAnim(true);
        UE_LOG(
            LogTemp,
            Warning,
            TEXT("[AocietyMotionMatching] runtime fallback enabled: motion assets require repair"));
    }

    ConversationWidget = CreateWidget<UAocietyConversationWidget>(
        GetWorld(), UAocietyConversationWidget::StaticClass());
    if (ConversationWidget)
    {
        ConversationWidget->AddToViewport(100);
        ConversationWidget->SetVisibility(ESlateVisibility::Collapsed);
    }

    PauseMenuWidget = CreateWidget<UAocietyPauseMenuWidget>(
        GetWorld(), UAocietyPauseMenuWidget::StaticClass());
    if (PauseMenuWidget)
    {
        PauseMenuWidget->AddToViewport(200);
        PauseMenuWidget->SetVisibility(ESlateVisibility::Collapsed);
    }

    PreviousActorLocation = GetActorLocation();
    bHasPreviousActorLocation = true;

    UE_LOG(
        LogTemp,
        Display,
        TEXT("[AocietyMotionMatching] initialized driver=%s database=%s indexed_poses=%d retargeter=%s retarget_ready=%s"),
        *GetNameSafe(MotionDriverMesh->GetSkeletalMeshAsset()),
        *GetNameSafe(MotionDatabase),
        MotionInstance ? MotionInstance->GetIndexedPoseCount() : 0,
        *GetNameSafe(EcyRetargeter),
        bRetargetReady ? TEXT("true") : TEXT("false"));
}

void AAocietyPlayerCharacter::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);

    const FVector CurrentActorLocation = GetActorLocation();
    if (bHasPreviousActorLocation
        && FVector::DistSquared(CurrentActorLocation, PreviousActorLocation)
            > FMath::Square(140.0f))
    {
        if (UAnimInstance* EcyAnimInstance = GetMesh()->GetAnimInstance())
        {
            EcyAnimInstance->ResetDynamics(ETeleportType::ResetPhysics);
        }
    }
    PreviousActorLocation = CurrentActorLocation;
    bHasPreviousActorLocation = true;

    if (!bInitialCameraPitchApplied && Controller)
    {
        FRotator ViewRotation = Controller->GetControlRotation();
        ViewRotation.Pitch = -10.0f;
        Controller->SetControlRotation(ViewRotation);
        FollowCamera->SetActive(true);
        if (APlayerController* PlayerController =
                Cast<APlayerController>(Controller))
        {
            PlayerController->SetViewTarget(this);
            UE_LOG(
                LogTemp,
                Display,
                TEXT("[AocietyViewport] pawn=%s camera=%s view_target=%s"),
                *GetActorLocation().ToCompactString(),
                *FollowCamera->GetComponentLocation().ToCompactString(),
                *GetNameSafe(PlayerController->GetViewTarget()));
        }
        bInitialCameraPitchApplied = true;
    }

    if (bRuntimeAuditEnabled)
    {
        RunRuntimeAudit(DeltaSeconds);
    }

    MotionEvidenceAccumulator += DeltaSeconds;
    if (MotionEvidenceAccumulator >= 1.0f)
    {
        MotionEvidenceAccumulator = 0.0f;
        UAocietyMotionMatchingAnimInstance* MotionInstance =
            Cast<UAocietyMotionMatchingAnimInstance>(
                MotionDriverMesh->GetAnimInstance());
        UAocietyEcyRetargetAnimInstance* EcyInstance =
            Cast<UAocietyEcyRetargetAnimInstance>(GetMesh()->GetAnimInstance());
        const FVector LeftFootLocation = GetMesh()->GetSocketTransform(
            TEXT("foot_L_143"),
            RTS_Component).GetLocation();
        const float LeftFootDelta = bHasPreviousLeftFootLocation
            ? FVector::Distance(PreviousLeftFootLocation, LeftFootLocation)
            : 0.0f;
        PreviousLeftFootLocation = LeftFootLocation;
        bHasPreviousLeftFootLocation = true;

        if (MotionInstance && EcyInstance)
        {
            UE_LOG(
                LogTemp,
                Display,
                TEXT("[AocietyMotionMatching] speed=%.1f foot_delta=%.2f motion=(%s) ecy=(%s)"),
                GetVelocity().Size2D(),
                LeftFootDelta,
                *MotionInstance->GetMotionMatchingState(),
                *EcyInstance->GetRetargetState());
        }
    }
}

void AAocietyPlayerCharacter::RunRuntimeAudit(float DeltaSeconds)
{
    RuntimeAuditElapsed += DeltaSeconds;

    if (!bRuntimeAuditIdleCaptured && RuntimeAuditElapsed >= 2.0f)
    {
        bRuntimeAuditIdleCaptured = true;
        CaptureRuntimeAuditScreenshot(TEXT("01_ecy_idle_mm.png"));
    }

    if (RuntimeAuditElapsed >= 2.5f && RuntimeAuditElapsed < 6.0f)
    {
        AddMovementInput(GetActorForwardVector(), 1.0f, true);
    }

    if (!bRuntimeAuditWalkCaptured && RuntimeAuditElapsed >= 4.5f)
    {
        bRuntimeAuditWalkCaptured = true;
        CaptureRuntimeAuditScreenshot(TEXT("02_ecy_walk_mm.png"));
    }

    if (!bRuntimeAuditJumpStarted && RuntimeAuditElapsed >= 6.5f)
    {
        bRuntimeAuditJumpStarted = true;
        Jump();
    }

    if (!bRuntimeAuditJumpCaptured && RuntimeAuditElapsed >= 6.9f)
    {
        bRuntimeAuditJumpCaptured = true;
        CaptureRuntimeAuditScreenshot(TEXT("05_ecy_jump_land.png"));
    }

    if (!bRuntimeAuditFinalCaptured && RuntimeAuditElapsed >= 9.0f)
    {
        bRuntimeAuditFinalCaptured = true;
        const FBoxSphereBounds& Bounds = GetMesh()->Bounds;
        UE_LOG(
            LogTemp,
            Display,
            TEXT("[AocietyRuntimeAudit] player=%s mesh_bounds_origin=%s mesh_bounds_extent=%s mesh_bounds_radius=%.2f hips=%s left_foot=%s velocity=%s"),
            *GetActorLocation().ToCompactString(),
            *Bounds.Origin.ToCompactString(),
            *Bounds.BoxExtent.ToCompactString(),
            Bounds.SphereRadius,
            *GetMesh()->GetSocketLocation(TEXT("hips_217")).ToCompactString(),
            *GetMesh()->GetSocketLocation(TEXT("foot_L_143")).ToCompactString(),
            *GetVelocity().ToCompactString());
        CaptureRuntimeAuditScreenshot(TEXT("06_animdynamics.png"));
    }

    if (!bRuntimeAuditNPCViewSet && RuntimeAuditElapsed >= 10.0f)
    {
        bRuntimeAuditNPCViewSet = true;
        GetCharacterMovement()->StopMovementImmediately();
        SetActorLocation(FVector(5600.0f, 0.0f, 140.0f));
        SetActorRotation(FRotator(0.0f, 0.0f, 0.0f));
        if (AController* PlayerController = GetController())
        {
            PlayerController->SetControlRotation(FRotator(-12.0f, 0.0f, 0.0f));
        }
        UE_LOG(
            LogTemp,
            Display,
            TEXT("[AocietyRuntimeAudit] npc_view player=%s yaw=0"),
            *GetActorLocation().ToCompactString());
        for (TActorIterator<AAocietyNPCCharacter> It(GetWorld()); It; ++It)
        {
            AAocietyNPCCharacter* NPC = *It;
            USkeletalMeshComponent* NPCMesh =
                NPC ? NPC->GetResidentVisual() : nullptr;
            if (!NPC || !NPCMesh)
            {
                continue;
            }

            NPC->bEnableWander = false;
            NPC->GetCharacterMovement()->StopMovementImmediately();
            NPC->SetActorLocation(
                NPC->NpcId == TEXT("npc_01")
                    ? FVector(6200.0f, -300.0f, 115.0f)
                    : FVector(6200.0f, 300.0f, 115.0f));

            const FBoxSphereBounds& NPCBounds = NPCMesh->Bounds;
            UE_LOG(
                LogTemp,
                Display,
                TEXT("[AocietyRuntimeAudit] npc=%s location=%s actor_scale=%s mesh_scale=%s visible=%s hidden=%s playing=%s bounds_origin=%s bounds_extent=%s bounds_radius=%.2f"),
                *NPC->NpcId,
                *NPC->GetActorLocation().ToCompactString(),
                *NPC->GetActorScale3D().ToCompactString(),
                *NPCMesh->GetRelativeScale3D().ToCompactString(),
                NPCMesh->IsVisible() ? TEXT("true") : TEXT("false"),
                NPC->IsHidden() ? TEXT("true") : TEXT("false"),
                NPCMesh->IsPlaying() ? TEXT("true") : TEXT("false"),
                *NPCBounds.Origin.ToCompactString(),
                *NPCBounds.BoxExtent.ToCompactString(),
                NPCBounds.SphereRadius);
        }
    }

    if (!bRuntimeAuditNPCThinkingCaptured && RuntimeAuditElapsed >= 14.1f)
    {
        bRuntimeAuditNPCThinkingCaptured = true;
        CaptureRuntimeAuditScreenshot(TEXT("08_npc_ambient_thinking.png"));
    }

    if (!bRuntimeAuditNPCReplyCaptured && RuntimeAuditElapsed >= 17.0f)
    {
        bRuntimeAuditNPCReplyCaptured = true;
        CaptureRuntimeAuditScreenshot(TEXT("09_npc_ambient_reply.png"));
    }

    if (!bRuntimeAuditPlayerInteractionStarted && RuntimeAuditElapsed >= 18.0f)
    {
        bRuntimeAuditPlayerInteractionStarted = true;
        for (TActorIterator<AAocietyNPCCharacter> It(GetWorld()); It; ++It)
        {
            AAocietyNPCCharacter* NPC = *It;
            if (!NPC || NPC->NpcId != TEXT("npc_02"))
            {
                continue;
            }

            GetCharacterMovement()->StopMovementImmediately();
            SetActorLocation(NPC->GetActorLocation() + FVector(180.0f, 260.0f, 0.0f));
            NearbyNPC = NPC;
            FVector LookDirection = NPC->GetActorLocation() - GetActorLocation();
            LookDirection.Z = 0.0f;
            const FRotator LookRotation = LookDirection.Rotation();
            if (AController* PlayerController = GetController())
            {
                FRotator InteractionView = LookRotation;
                InteractionView.Pitch = -10.0f;
                PlayerController->SetControlRotation(InteractionView);
            }
            Interact();
            UE_LOG(
                LogTemp,
                Display,
                TEXT("[AocietyRuntimeAudit] player_interaction npc=%s player=%s"),
                *NPC->NpcId,
                *GetActorLocation().ToCompactString());
            break;
        }
    }

    if (!bRuntimeAuditPlayerPendingCaptured && RuntimeAuditElapsed >= 18.2f)
    {
        bRuntimeAuditPlayerPendingCaptured = true;
        CaptureRuntimeAuditScreenshot(TEXT("10_player_interaction_pending.png"));
    }

    if (!bRuntimeAuditPlayerReplyCaptured && RuntimeAuditElapsed >= 21.5f)
    {
        bRuntimeAuditPlayerReplyCaptured = true;
        CaptureRuntimeAuditScreenshot(TEXT("11_player_interaction_deepseek.png"));
    }

    if (RuntimeAuditElapsed >= 23.0f)
    {
        FPlatformMisc::RequestExit(false);
    }
}

void AAocietyPlayerCharacter::CaptureRuntimeAuditScreenshot(
    const TCHAR* FileName) const
{
    const FString ArtifactDirectory = FPaths::ConvertRelativePathToFull(
        FPaths::Combine(FPaths::ProjectDir(), TEXT("../artifacts")));
    IFileManager::Get().MakeDirectory(*ArtifactDirectory, true);
    const FString ScreenshotPath = FPaths::Combine(ArtifactDirectory, FileName);
    FScreenshotRequest::RequestScreenshot(ScreenshotPath, false, false);
    UE_LOG(
        LogTemp,
        Display,
        TEXT("[AocietyRuntimeAudit] screenshot=%s"),
        *ScreenshotPath);
}

void AAocietyPlayerCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
    Super::SetupPlayerInputComponent(PlayerInputComponent);

    PlayerInputComponent->BindAxis(TEXT("MoveForward"), this,
        &AAocietyPlayerCharacter::MoveForward);
    PlayerInputComponent->BindAxis(TEXT("MoveRight"), this,
        &AAocietyPlayerCharacter::MoveRight);
    PlayerInputComponent->BindAxis(TEXT("Turn"), this,
        &APawn::AddControllerYawInput);
    PlayerInputComponent->BindAxis(TEXT("LookUp"), this,
        &APawn::AddControllerPitchInput);
    PlayerInputComponent->BindAction(TEXT("Jump"), IE_Pressed, this,
        &ACharacter::Jump);
    PlayerInputComponent->BindAction(TEXT("Jump"), IE_Released, this,
        &ACharacter::StopJumping);
    PlayerInputComponent->BindAction(TEXT("Interact"), IE_Pressed, this,
        &AAocietyPlayerCharacter::Interact);
    PlayerInputComponent->BindAction(TEXT("Inbox"), IE_Pressed, this,
        &AAocietyPlayerCharacter::ToggleInbox);
    FInputActionBinding& EscapeBinding = PlayerInputComponent->BindAction(
        TEXT("CloseConversation"), IE_Pressed, this,
        &AAocietyPlayerCharacter::HandleEscape);
    EscapeBinding.bExecuteWhenPaused = true;
}

void AAocietyPlayerCharacter::SetNearbyNPC(AAocietyNPCCharacter* NPC)
{
    NearbyNPC = NPC;
}

void AAocietyPlayerCharacter::ClearNearbyNPC(AAocietyNPCCharacter* NPC)
{
    if (NearbyNPC.Get() == NPC)
    {
        NearbyNPC.Reset();
    }
}

void AAocietyPlayerCharacter::Interact()
{
    if (ConversationWidget && ConversationWidget->IsPanelOpen())
    {
        ConversationWidget->ClosePanel();
        return;
    }
    AAocietyNPCCharacter* NPC = NearbyNPC.Get();
    if (!IsValid(NPC))
    {
        constexpr float MaxInteractionDistance = 650.0f;
        const FVector PlayerLocation = GetActorLocation();
        float BestDistanceSquared = FMath::Square(MaxInteractionDistance);
        for (TActorIterator<AAocietyNPCCharacter> It(GetWorld()); It; ++It)
        {
            AAocietyNPCCharacter* Candidate = *It;
            if (!IsValid(Candidate))
            {
                continue;
            }
            const float DistanceSquared = FVector::DistSquared(
                PlayerLocation, Candidate->GetActorLocation());
            if (DistanceSquared <= BestDistanceSquared)
            {
                BestDistanceSquared = DistanceSquared;
                NPC = Candidate;
            }
        }
        NearbyNPC = NPC;
    }
    if (!IsValid(NPC))
    {
        return;
    }

    UGameInstance* GameInstance = GetGameInstance();
    UAocietyClientSubsystem* Client = GameInstance
        ? GameInstance->GetSubsystem<UAocietyClientSubsystem>()
        : nullptr;
    if (!Client || !ConversationWidget)
    {
        return;
    }

    ConversationWidget->OpenChat(
        NPC->NpcId,
        NPC->DisplayName,
        Client,
        Cast<APlayerController>(Controller));
}

void AAocietyPlayerCharacter::ToggleInbox()
{
    if (!ConversationWidget)
    {
        return;
    }
    if (ConversationWidget->IsPanelOpen())
    {
        ConversationWidget->ClosePanel();
        return;
    }
    UGameInstance* GameInstance = GetGameInstance();
    UAocietyClientSubsystem* Client = GameInstance
        ? GameInstance->GetSubsystem<UAocietyClientSubsystem>()
        : nullptr;
    if (Client)
    {
        ConversationWidget->OpenInbox(
            Client, Cast<APlayerController>(Controller));
    }
}

void AAocietyPlayerCharacter::HandleEscape()
{
    if (ConversationWidget && ConversationWidget->IsPanelOpen())
    {
        ConversationWidget->ClosePanel();
        return;
    }
    if (!PauseMenuWidget)
    {
        return;
    }
    if (PauseMenuWidget->IsMenuOpen())
    {
        PauseMenuWidget->Close();
    }
    else
    {
        PauseMenuWidget->Open(Cast<APlayerController>(Controller));
    }
}

void AAocietyPlayerCharacter::MoveForward(float Value)
{
    if ((ConversationWidget && ConversationWidget->IsPanelOpen())
        || (PauseMenuWidget && PauseMenuWidget->IsMenuOpen()))
    {
        return;
    }
    if (Controller && !FMath::IsNearlyZero(Value))
    {
        const FRotator YawRotation(0.0f, Controller->GetControlRotation().Yaw, 0.0f);
        AddMovementInput(FRotationMatrix(YawRotation).GetUnitAxis(EAxis::X), Value);
    }
}

void AAocietyPlayerCharacter::MoveRight(float Value)
{
    if ((ConversationWidget && ConversationWidget->IsPanelOpen())
        || (PauseMenuWidget && PauseMenuWidget->IsMenuOpen()))
    {
        return;
    }
    if (Controller && !FMath::IsNearlyZero(Value))
    {
        const FRotator YawRotation(0.0f, Controller->GetControlRotation().Yaw, 0.0f);
        AddMovementInput(FRotationMatrix(YawRotation).GetUnitAxis(EAxis::Y), Value);
    }
}
