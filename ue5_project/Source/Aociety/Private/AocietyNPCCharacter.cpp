// Copyright Aociety. All rights reserved.

#include "AocietyNPCCharacter.h"
#include "AocietyNPCBubbleWidget.h"
#include "Animation/AnimSequence.h"

#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Components/WidgetComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetMathLibrary.h"
#include "TimerManager.h"

AAocietyNPCCharacter::AAocietyNPCCharacter()
{
    PrimaryActorTick.bCanEverTick = true;
    AutoPossessAI = EAutoPossessAI::PlacedInWorldOrSpawned;
    GetCapsuleComponent()->InitCapsuleSize(38.0f, 88.0f);

    UCharacterMovementComponent* Movement = GetCharacterMovement();
    Movement->bRunPhysicsWithNoController = true;
    Movement->bOrientRotationToMovement = true;
    Movement->bUseControllerDesiredRotation = false;
    Movement->RotationRate = FRotator(0.0f, 300.0f, 0.0f);
    Movement->MaxWalkSpeed = WanderSpeed;
    Movement->BrakingDecelerationWalking = 720.0f;

    Nameplate = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Nameplate"));
    Nameplate->SetupAttachment(RootComponent);
    Nameplate->SetRelativeLocation(FVector(0.0f, 0.0f, 205.0f));
    Nameplate->SetHorizontalAlignment(EHTA_Center);
    Nameplate->SetWorldSize(24.0f);
    Nameplate->SetTextRenderColor(FColor(110, 235, 255));
    Nameplate->SetText(FText::FromString(TEXT("AI 居民 · GLM 5.2")));
    Nameplate->SetVisibility(false);

    SpeechBubble = CreateDefaultSubobject<UTextRenderComponent>(TEXT("SpeechBubble"));
    SpeechBubble->SetupAttachment(RootComponent);
    SpeechBubble->SetRelativeLocation(FVector(0.0f, 0.0f, 250.0f));
    SpeechBubble->SetHorizontalAlignment(EHTA_Center);
    SpeechBubble->SetWorldSize(27.0f);
    SpeechBubble->SetTextRenderColor(FColor(255, 230, 150));
    SpeechBubble->SetText(FText::GetEmpty());
    SpeechBubble->SetVisibility(false);

    SolidBubble = CreateDefaultSubobject<UWidgetComponent>(TEXT("SolidBubble"));
    SolidBubble->SetupAttachment(RootComponent);
    SolidBubble->SetRelativeLocation(FVector(0.0f, 0.0f, 242.0f));
    SolidBubble->SetDrawSize(FVector2D(512.0f, 256.0f));
    SolidBubble->SetRelativeScale3D(FVector(0.20f));
    SolidBubble->SetWidgetSpace(EWidgetSpace::World);
    // Align the reference artwork's left-side tail with the speaker's head.
    SolidBubble->SetPivot(FVector2D(0.34f, 1.0f));
    SolidBubble->SetBlendMode(EWidgetBlendMode::Transparent);
    SolidBubble->SetBackgroundColor(FLinearColor::Transparent);
    SolidBubble->SetTintColorAndOpacity(FLinearColor::White);
    SolidBubble->SetTwoSided(true);
    SolidBubble->SetTranslucentSortPriority(20);
    SolidBubble->SetWidgetClass(UAocietyNPCBubbleWidget::StaticClass());
    SolidBubble->SetVisibility(false);
}

void AAocietyNPCCharacter::BeginPlay()
{
    Super::BeginPlay();

    if (!GetActorScale3D().Equals(FVector::OneVector, KINDA_SMALL_NUMBER))
    {
        UE_LOG(LogTemp, Warning,
            TEXT("[AocietyNPC] Resetting unexpected actor scale for %s: %s"),
            *NpcId, *GetActorScale3D().ToCompactString());
        SetActorScale3D(FVector::OneVector);
    }
    if (!GetMesh()->GetRelativeScale3D().Equals(
            FVector::OneVector, KINDA_SMALL_NUMBER))
    {
        UE_LOG(LogTemp, Warning,
            TEXT("[AocietyNPC] Resetting unexpected mesh scale for %s: %s"),
            *NpcId, *GetMesh()->GetRelativeScale3D().ToCompactString());
        GetMesh()->SetRelativeScale3D(FVector::OneVector);
    }

    HomeLocation = GetActorLocation();
    UCharacterMovementComponent* Movement = GetCharacterMovement();
    Movement->bRunPhysicsWithNoController = true;
    Movement->bOrientRotationToMovement = true;
    Movement->bUseControllerDesiredRotation = false;
    Movement->MaxWalkSpeed = WanderSpeed;
    GetMesh()->bEnableUpdateRateOptimizations = false;
    GetMesh()->VisibilityBasedAnimTickOption =
        EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    SolidBubble->SetRelativeLocation(FVector(0.0f, 0.0f, 242.0f));
    SolidBubble->SetDrawSize(FVector2D(512.0f, 256.0f));
    SolidBubble->SetRelativeScale3D(FVector(0.20f));
    SolidBubble->SetPivot(FVector2D(0.34f, 1.0f));
    SolidBubble->SetBlendMode(EWidgetBlendMode::Transparent);
    SolidBubble->SetBackgroundColor(FLinearColor::Transparent);
    SolidBubble->SetTintColorAndOpacity(FLinearColor::White);
    SolidBubble->SetTwoSided(true);
    SolidBubble->SetTranslucentSortPriority(20);
    SolidBubble->SetWidgetClass(UAocietyNPCBubbleWidget::StaticClass());
    SolidBubble->SetVisibility(false);
    SolidBubble->InitWidget();
    Nameplate->SetText(FText::FromString(
        FString::Printf(TEXT("%s [%s] · GLM 5.2"), *DisplayName, *NpcId)));
    if (UAocietyNPCBubbleWidget* Widget =
            Cast<UAocietyNPCBubbleWidget>(SolidBubble->GetUserWidgetObject()))
    {
        Widget->SetIdle(DisplayName);
    }
    BeginWanderPause();
    PlayLocomotionAnimation(false);

    UE_LOG(LogTemp, Log,
        TEXT("[AocietyNPC] ready id=%s actor_scale=%s mesh_scale=%s idle=%s walk=%s"),
        *NpcId,
        *GetActorScale3D().ToCompactString(),
        *GetMesh()->GetRelativeScale3D().ToCompactString(),
        *GetNameSafe(IdleAnimation),
        *GetNameSafe(WalkAnimation));
}

void AAocietyNPCCharacter::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);

    if (APlayerCameraManager* Camera =
            UGameplayStatics::GetPlayerCameraManager(this, 0))
    {
        FRotator Facing = UKismetMathLibrary::FindLookAtRotation(
            SolidBubble->GetComponentLocation(), Camera->GetCameraLocation());
        Facing.Pitch = 0.0f;
        Facing.Roll = 0.0f;
        SolidBubble->SetWorldRotation(Facing);
    }

    if (FocusActor.IsValid() && GetWorld()->GetTimeSeconds() < FocusEndTime)
    {
        FVector ToFocus = FocusActor->GetActorLocation() - GetActorLocation();
        ToFocus.Z = 0.0f;
        if (!ToFocus.IsNearlyZero())
        {
            SetActorRotation(FRotator(0.0f, ToFocus.Rotation().Yaw, 0.0f));
        }
        GetCharacterMovement()->StopMovementImmediately();
        PlayLocomotionAnimation(false);
        return;
    }
    FocusActor.Reset();

    if (!bEnableWander)
    {
        GetCharacterMovement()->StopMovementImmediately();
        PlayLocomotionAnimation(false);
        return;
    }

    APawn* PlayerPawn = UGameplayStatics::GetPlayerPawn(this, 0);
    if (IsValid(PlayerPawn))
    {
        const FVector ToPlayer = PlayerPawn->GetActorLocation() - GetActorLocation();
        if (ToPlayer.SizeSquared2D() < FMath::Square(520.0f))
        {
            const FRotator Facing = ToPlayer.Rotation();
            SetActorRotation(FRotator(0.0f, Facing.Yaw, 0.0f));
            GetCharacterMovement()->StopMovementImmediately();
            PlayLocomotionAnimation(false);
            return;
        }
    }

    TimeUntilNextTarget -= DeltaSeconds;
    if (bWaitingAtTarget)
    {
        if (TimeUntilNextTarget <= 0.0f)
        {
            PickWanderTarget();
        }
        else
        {
            GetCharacterMovement()->StopMovementImmediately();
            PlayLocomotionAnimation(false);
            return;
        }
    }

    FVector ToTarget = WanderTarget - GetActorLocation();
    ToTarget.Z = 0.0f;
    if (ToTarget.SizeSquared() < FMath::Square(60.0f))
    {
        BeginWanderPause();
        return;
    }
    if (TimeUntilNextTarget <= 0.0f)
    {
        PickWanderTarget();
        ToTarget = WanderTarget - GetActorLocation();
        ToTarget.Z = 0.0f;
    }

    if (!ToTarget.IsNearlyZero())
    {
        AddMovementInput(ToTarget.GetSafeNormal(), 1.0f);
    }

    const bool bMoving = GetVelocity().SizeSquared2D() > FMath::Square(5.0f);
    PlayLocomotionAnimation(bMoving);
}

void AAocietyNPCCharacter::ShowDialogue(
    const FString& Line,
    const FString& Source,
    const FString& Model,
    float Duration)
{
    const FString Wrapped = Line.Len() > 64 ? Line.Left(64) + TEXT("...") : Line;
    SpeechBubble->SetText(FText::FromString(Wrapped));
    SolidBubble->SetVisibility(true);
    if (UAocietyNPCBubbleWidget* Widget =
            Cast<UAocietyNPCBubbleWidget>(SolidBubble->GetUserWidgetObject()))
    {
        Widget->SetDialogue(DisplayName, Wrapped, Source, Model);
    }
    GetWorldTimerManager().ClearTimer(DialogueTimer);
    GetWorldTimerManager().SetTimer(
        DialogueTimer, this, &AAocietyNPCCharacter::ClearDialogue,
        FMath::Max(2.0f, Duration), false);
}

void AAocietyNPCCharacter::ShowThinking()
{
    SpeechBubble->SetText(FText::FromString(TEXT("正在思考 · GLM 5.2...")));
    SolidBubble->SetVisibility(true);
    if (UAocietyNPCBubbleWidget* Widget =
            Cast<UAocietyNPCBubbleWidget>(SolidBubble->GetUserWidgetObject()))
    {
        Widget->SetThinking(DisplayName, TEXT("glm-5.2"));
    }
    GetWorldTimerManager().ClearTimer(DialogueTimer);
    GetWorldTimerManager().SetTimer(
        DialogueTimer, this, &AAocietyNPCCharacter::ClearDialogue,
        30.0f, false);
}

void AAocietyNPCCharacter::ShowListening(
    const FString& SpeakerName,
    float Duration)
{
    SpeechBubble->SetText(FText::FromString(
        FString::Printf(TEXT("正在听 %s 说话..."), *SpeakerName)));
    SolidBubble->SetVisibility(true);
    if (UAocietyNPCBubbleWidget* Widget =
            Cast<UAocietyNPCBubbleWidget>(SolidBubble->GetUserWidgetObject()))
    {
        Widget->SetListening(DisplayName, SpeakerName, TEXT("glm-5.2"));
    }
    GetWorldTimerManager().ClearTimer(DialogueTimer);
    GetWorldTimerManager().SetTimer(
        DialogueTimer, this, &AAocietyNPCCharacter::ClearDialogue,
        FMath::Max(2.0f, Duration), false);
}

void AAocietyNPCCharacter::FocusOnActor(AActor* OtherActor, float Duration)
{
    if (!IsValid(OtherActor) || OtherActor == this)
    {
        FocusActor.Reset();
        FocusEndTime = 0.0;
        return;
    }

    FocusActor = OtherActor;
    FocusEndTime = GetWorld()->GetTimeSeconds() + FMath::Max(1.0f, Duration);
}

void AAocietyNPCCharacter::PickWanderTarget()
{
    FVector2D Offset = FMath::RandPointInCircle(WanderRadius);
    const float MinimumTravel = FMath::Min(90.0f, WanderRadius * 0.45f);
    for (int32 Attempt = 0;
         Attempt < 4 && Offset.SizeSquared() < FMath::Square(MinimumTravel);
         ++Attempt)
    {
        Offset = FMath::RandPointInCircle(WanderRadius);
    }
    WanderTarget = HomeLocation + FVector(Offset.X, Offset.Y, 0.0f);
    TimeUntilNextTarget = FMath::Max(
        8.0f,
        (WanderRadius / FMath::Max(1.0f, WanderSpeed)) * 3.0f + 4.0f);
    bWaitingAtTarget = false;
}

void AAocietyNPCCharacter::BeginWanderPause()
{
    bWaitingAtTarget = true;
    TimeUntilNextTarget = FMath::FRandRange(2.5f, 5.0f);
    GetCharacterMovement()->StopMovementImmediately();
    PlayLocomotionAnimation(false);
}

void AAocietyNPCCharacter::PlayLocomotionAnimation(bool bMoving)
{
    UAnimSequence* Desired = bMoving ? WalkAnimation : IdleAnimation;
    bWasMoving = bMoving;
    if (!Desired || ActiveAnimation == Desired)
    {
        return;
    }

    GetMesh()->SetRelativeScale3D(FVector::OneVector);
    GetMesh()->SetAnimationMode(EAnimationMode::AnimationSingleNode);
    GetMesh()->PlayAnimation(Desired, true);
    ActiveAnimation = Desired;

    UE_LOG(LogTemp, Log,
        TEXT("[AocietyNPC] %s animation=%s speed=%.1f"),
        *NpcId, bMoving ? TEXT("walk") : TEXT("idle"),
        GetVelocity().Size2D());
}

void AAocietyNPCCharacter::ClearDialogue()
{
    SpeechBubble->SetText(FText::GetEmpty());
    if (UAocietyNPCBubbleWidget* Widget =
            Cast<UAocietyNPCBubbleWidget>(SolidBubble->GetUserWidgetObject()))
    {
        Widget->SetIdle(DisplayName);
    }
    SolidBubble->SetVisibility(false);
}
