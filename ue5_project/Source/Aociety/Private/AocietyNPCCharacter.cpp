// Copyright Aociety. All rights reserved.

#include "AocietyNPCCharacter.h"
#include "AocietyNPCBubbleWidget.h"
#include "Animation/AnimSequence.h"

#include "Components/CapsuleComponent.h"
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
    GetCapsuleComponent()->InitCapsuleSize(38.0f, 88.0f);

    UCharacterMovementComponent* Movement = GetCharacterMovement();
    Movement->bOrientRotationToMovement = true;
    Movement->RotationRate = FRotator(0.0f, 300.0f, 0.0f);
    Movement->MaxWalkSpeed = WanderSpeed;

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
    SolidBubble->SetRelativeLocation(FVector(0.0f, 0.0f, 265.0f));
    SolidBubble->SetDrawSize(FVector2D(460.0f, 150.0f));
    SolidBubble->SetRelativeScale3D(FVector(0.30f));
    SolidBubble->SetWidgetSpace(EWidgetSpace::World);
    SolidBubble->SetPivot(FVector2D(0.5f, 1.0f));
    SolidBubble->SetBlendMode(EWidgetBlendMode::Opaque);
    SolidBubble->SetWidgetClass(UAocietyNPCBubbleWidget::StaticClass());
}

void AAocietyNPCCharacter::BeginPlay()
{
    Super::BeginPlay();
    HomeLocation = GetActorLocation();
    GetCharacterMovement()->MaxWalkSpeed = WanderSpeed;
    Nameplate->SetText(FText::FromString(
        FString::Printf(TEXT("%s [%s] · GLM 5.2"), *DisplayName, *NpcId)));
    if (UAocietyNPCBubbleWidget* Widget =
            Cast<UAocietyNPCBubbleWidget>(SolidBubble->GetUserWidgetObject()))
    {
        Widget->SetBubbleText(FString::Printf(
            TEXT("%s  [%s]\nGLM 5.2 · 正在小镇中散步"),
            *DisplayName, *NpcId));
    }
    PickWanderTarget();
    if (IdleAnimation)
    {
        GetMesh()->SetAnimationMode(EAnimationMode::AnimationSingleNode);
        GetMesh()->PlayAnimation(IdleAnimation, true);
    }
}

void AAocietyNPCCharacter::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);

    if (!bEnableWander)
    {
        return;
    }

    if (APlayerCameraManager* Camera =
            UGameplayStatics::GetPlayerCameraManager(this, 0))
    {
        FRotator Facing = UKismetMathLibrary::FindLookAtRotation(
            SolidBubble->GetComponentLocation(), Camera->GetCameraLocation());
        Facing.Pitch = 0.0f;
        Facing.Roll = 0.0f;
        SolidBubble->SetWorldRotation(Facing);
    }

    APawn* PlayerPawn = UGameplayStatics::GetPlayerPawn(this, 0);
    if (IsValid(PlayerPawn))
    {
        const FVector ToPlayer = PlayerPawn->GetActorLocation() - GetActorLocation();
        if (ToPlayer.SizeSquared2D() < FMath::Square(520.0f))
        {
            const FRotator Facing = ToPlayer.Rotation();
            SetActorRotation(FRotator(0.0f, Facing.Yaw, 0.0f));
            if (bWasMoving && IdleAnimation)
            {
                GetMesh()->SetAnimationMode(EAnimationMode::AnimationSingleNode);
                GetMesh()->PlayAnimation(IdleAnimation, true);
                bWasMoving = false;
            }
            return;
        }
    }

    TimeUntilNextTarget -= DeltaSeconds;
    FVector ToTarget = WanderTarget - GetActorLocation();
    ToTarget.Z = 0.0f;
    if (TimeUntilNextTarget <= 0.0f || ToTarget.SizeSquared() < FMath::Square(70.0f))
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
    if (bMoving != bWasMoving)
    {
        if (UAnimSequence* Desired = bMoving ? WalkAnimation : IdleAnimation)
        {
            GetMesh()->SetAnimationMode(EAnimationMode::AnimationSingleNode);
            GetMesh()->PlayAnimation(Desired, true);
        }
        bWasMoving = bMoving;
    }
}

void AAocietyNPCCharacter::ShowDialogue(const FString& Line, float Duration)
{
    const FString Wrapped = Line.Len() > 54 ? Line.Left(54) + TEXT("...") : Line;
    SpeechBubble->SetText(FText::FromString(Wrapped));
    if (UAocietyNPCBubbleWidget* Widget =
            Cast<UAocietyNPCBubbleWidget>(SolidBubble->GetUserWidgetObject()))
    {
        Widget->SetBubbleText(FString::Printf(
            TEXT("%s  [%s]\n%s\nsource=llm · model=glm-5.2"),
            *DisplayName, *NpcId, *Wrapped));
    }
    GetWorldTimerManager().ClearTimer(DialogueTimer);
    GetWorldTimerManager().SetTimer(
        DialogueTimer, this, &AAocietyNPCCharacter::ClearDialogue,
        FMath::Max(2.0f, Duration), false);
}

void AAocietyNPCCharacter::ShowThinking()
{
    SpeechBubble->SetText(FText::FromString(TEXT("正在思考 · GLM 5.2...")));
    if (UAocietyNPCBubbleWidget* Widget =
            Cast<UAocietyNPCBubbleWidget>(SolidBubble->GetUserWidgetObject()))
    {
        Widget->SetBubbleText(FString::Printf(
            TEXT("%s  [%s]\n正在思考...\n请求模型：GLM 5.2"),
            *DisplayName, *NpcId), true);
    }
}

void AAocietyNPCCharacter::PickWanderTarget()
{
    const FVector2D Offset = FMath::RandPointInCircle(WanderRadius);
    WanderTarget = HomeLocation + FVector(Offset.X, Offset.Y, 0.0f);
    TimeUntilNextTarget = FMath::FRandRange(5.0f, 10.0f);
}

void AAocietyNPCCharacter::ClearDialogue()
{
    SpeechBubble->SetText(FText::GetEmpty());
    if (UAocietyNPCBubbleWidget* Widget =
            Cast<UAocietyNPCBubbleWidget>(SolidBubble->GetUserWidgetObject()))
    {
        Widget->SetBubbleText(FString::Printf(
            TEXT("%s  [%s]\nGLM 5.2 · 正在小镇中散步"),
            *DisplayName, *NpcId));
    }
}
