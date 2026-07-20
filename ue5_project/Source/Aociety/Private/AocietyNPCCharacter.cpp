// Copyright Aociety. All rights reserved.

#include "AocietyNPCCharacter.h"
#include "AocietyNPCBubbleWidget.h"
#include "Animation/AnimSequence.h"

#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Components/WidgetComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Animation/SkeletalMeshActor.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetMathLibrary.h"
#include "Materials/MaterialInterface.h"
#include "TimerManager.h"

namespace
{
void DisableLegacyWorldText(UTextRenderComponent* TextComponent)
{
    if (!TextComponent)
    {
        return;
    }

    TextComponent->SetText(FText::GetEmpty());
    TextComponent->SetVisibility(false, true);
    TextComponent->SetHiddenInGame(true, true);
    TextComponent->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    TextComponent->SetCastShadow(false);
}

void ApplyResidentVariantMaterials(
    USkeletalMeshComponent* VisualMesh,
    const FString& NpcId)
{
    if (!VisualMesh)
    {
        return;
    }

    const TCHAR* ClothPath = nullptr;
    const TCHAR* HairPath = nullptr;
    if (NpcId == TEXT("npc_01"))
    {
        ClothPath = TEXT("/Game/Aociety/Characters/GeneratedMaterials/M_EcyNPC_Linxi_Cloth.M_EcyNPC_Linxi_Cloth");
        HairPath = TEXT("/Game/Aociety/Characters/GeneratedMaterials/M_EcyNPC_Linxi_Hair.M_EcyNPC_Linxi_Hair");
    }
    else if (NpcId == TEXT("npc_02"))
    {
        ClothPath = TEXT("/Game/Aociety/Characters/GeneratedMaterials/M_EcyNPC_Sakura_Cloth.M_EcyNPC_Sakura_Cloth");
        HairPath = TEXT("/Game/Aociety/Characters/GeneratedMaterials/M_EcyNPC_Sakura_Hair.M_EcyNPC_Sakura_Hair");
    }

    if (ClothPath)
    {
        if (UMaterialInterface* Cloth = LoadObject<UMaterialInterface>(nullptr, ClothPath))
        {
            VisualMesh->SetMaterial(0, Cloth);
        }
    }
    if (HairPath)
    {
        if (UMaterialInterface* Hair = LoadObject<UMaterialInterface>(nullptr, HairPath))
        {
            VisualMesh->SetMaterial(3, Hair);
        }
    }
}
}

USkeletalMeshComponent* AAocietyNPCCharacter::GetResidentVisual() const
{
    if (IsValid(RuntimeVisualActor))
    {
        return RuntimeVisualActor->GetSkeletalMeshComponent();
    }
    return GetMesh();
}

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

    ResidentVisual = CreateDefaultSubobject<USkeletalMeshComponent>(
        TEXT("ResidentVisual"));
    ResidentVisual->SetupAttachment(GetCapsuleComponent());
    ResidentVisual->SetRelativeLocation(FVector(0.0f, 0.0f, -46.0f));
    ResidentVisual->SetRelativeRotation(FRotator(0.0f, -90.0f, 0.0f));
    ResidentVisual->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    ResidentVisual->SetGenerateOverlapEvents(false);
    ResidentVisual->SetReceivesDecals(false);
    ResidentVisual->SetVisibility(false, true);
    ResidentVisual->SetHiddenInGame(true, true);

    GetMesh()->SetReceivesDecals(false);

    Nameplate = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Nameplate"));
    Nameplate->SetupAttachment(RootComponent);
    Nameplate->SetRelativeLocation(FVector(0.0f, 0.0f, 205.0f));
    Nameplate->SetHorizontalAlignment(EHTA_Center);
    Nameplate->SetWorldSize(24.0f);
    Nameplate->SetTextRenderColor(FColor(110, 235, 255));
    Nameplate->SetText(FText::FromString(TEXT("AI 居民 · DeepSeek V4 Flash")));
    DisableLegacyWorldText(Nameplate);

    SpeechBubble = CreateDefaultSubobject<UTextRenderComponent>(TEXT("SpeechBubble"));
    SpeechBubble->SetupAttachment(RootComponent);
    SpeechBubble->SetRelativeLocation(FVector(0.0f, 0.0f, 250.0f));
    SpeechBubble->SetHorizontalAlignment(EHTA_Center);
    SpeechBubble->SetWorldSize(27.0f);
    SpeechBubble->SetTextRenderColor(FColor(255, 230, 150));
    DisableLegacyWorldText(SpeechBubble);

    SolidBubble = CreateDefaultSubobject<UWidgetComponent>(TEXT("SolidBubble"));
    SolidBubble->SetupAttachment(RootComponent);
    SolidBubble->SetRelativeLocation(FVector(0.0f, 0.0f, 150.0f));
    SolidBubble->SetDrawSize(FVector2D(512.0f, 210.0f));
    SolidBubble->SetRelativeScale3D(FVector(0.18f));
    SolidBubble->SetWidgetSpace(EWidgetSpace::World);
    SolidBubble->SetPivot(FVector2D(0.5f, 1.0f));
    SolidBubble->SetBlendMode(EWidgetBlendMode::Transparent);
    SolidBubble->SetBackgroundColor(FLinearColor::Transparent);
    SolidBubble->SetTintColorAndOpacity(FLinearColor::White);
    SolidBubble->SetTwoSided(false);
    SolidBubble->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    SolidBubble->SetCastShadow(false);
    SolidBubble->SetTranslucentSortPriority(20);
    SolidBubble->SetWidgetClass(UAocietyNPCBubbleWidget::StaticClass());
    SolidBubble->SetVisibility(false);
}

void AAocietyNPCCharacter::BeginPlay()
{
    Super::BeginPlay();

    if (NpcId == TEXT("npc_01"))
    {
        SetActorLocation(
            FVector(6200.0f, -300.0f, 115.0f),
            false,
            nullptr,
            ETeleportType::TeleportPhysics);
    }
    else if (NpcId == TEXT("npc_02"))
    {
        SetActorLocation(
            FVector(7000.0f, 450.0f, 115.0f),
            false,
            nullptr,
            ETeleportType::TeleportPhysics);
    }

    ResidentVisual->SetReceivesDecals(false);
    GetMesh()->SetReceivesDecals(false);

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
    ResidentVisual->SetVisibility(false, true);
    ResidentVisual->SetHiddenInGame(true, true);
    GetMesh()->SetVisibility(false, true);
    GetMesh()->SetHiddenInGame(true, true);

    FActorSpawnParameters VisualSpawnParameters;
    VisualSpawnParameters.Owner = this;
    VisualSpawnParameters.SpawnCollisionHandlingOverride =
        ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    VisualSpawnParameters.ObjectFlags |= RF_Transient;
    RuntimeVisualActor = GetWorld()->SpawnActor<ASkeletalMeshActor>(
        ASkeletalMeshActor::StaticClass(),
        GetActorTransform(),
        VisualSpawnParameters);
    if (IsValid(RuntimeVisualActor))
    {
        RuntimeVisualActor->AttachToActor(
            this, FAttachmentTransformRules::SnapToTargetNotIncludingScale);
        RuntimeVisualActor->SetActorRelativeLocation(FVector(0.0f, 0.0f, -46.0f));
        RuntimeVisualActor->SetActorRelativeRotation(FRotator(0.0f, -90.0f, 0.0f));
        RuntimeVisualActor->SetActorRelativeScale3D(FVector::OneVector);

        USkeletalMeshComponent* VisualMesh =
            RuntimeVisualActor->GetSkeletalMeshComponent();
        VisualMesh->SetSkeletalMeshAsset(GetMesh()->GetSkeletalMeshAsset());
        for (int32 MaterialIndex = 0;
             MaterialIndex < GetMesh()->GetNumMaterials();
             ++MaterialIndex)
        {
            VisualMesh->SetMaterial(
                MaterialIndex, GetMesh()->GetMaterial(MaterialIndex));
        }
        ApplyResidentVariantMaterials(VisualMesh, NpcId);
        UE_LOG(LogTemp, Log,
            TEXT("[AocietyNPC] %s visual cloth=%s hair=%s"),
            *NpcId,
            *GetPathNameSafe(VisualMesh->GetMaterial(0)),
            *GetPathNameSafe(VisualMesh->GetMaterial(3)));
        VisualMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        VisualMesh->SetGenerateOverlapEvents(false);
        VisualMesh->SetReceivesDecals(false);
        VisualMesh->SetVisibility(true, true);
        VisualMesh->SetHiddenInGame(false, true);
        VisualMesh->SetRenderInMainPass(true);
        VisualMesh->SetRenderInDepthPass(true);
        VisualMesh->bEnableUpdateRateOptimizations = false;
        VisualMesh->VisibilityBasedAnimTickOption =
            EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
        VisualMesh->bComponentUseFixedSkelBounds = true;
        VisualMesh->SetBoundsScale(1.5f);
        VisualMesh->MarkRenderStateDirty();
    }
    else
    {
        UE_LOG(LogTemp, Error,
            TEXT("[AocietyNPC] Could not create runtime visual for %s"),
            *NpcId);
    }

    HomeLocation = GetActorLocation();
    // Placed instances may retain serialized visibility from the retired
    // TextRender UI. Keep those components permanently disabled so only the
    // styled UMG bubble can render in game.
    DisableLegacyWorldText(Nameplate);
    DisableLegacyWorldText(SpeechBubble);

    UCharacterMovementComponent* Movement = GetCharacterMovement();
    Movement->bRunPhysicsWithNoController = true;
    Movement->bOrientRotationToMovement = true;
    Movement->bUseControllerDesiredRotation = false;
    Movement->MaxWalkSpeed = WanderSpeed;
    SolidBubble->SetRelativeLocation(FVector(0.0f, 0.0f, 150.0f));
    SolidBubble->SetDrawSize(FVector2D(512.0f, 210.0f));
    SolidBubble->SetRelativeScale3D(FVector(0.18f));
    SolidBubble->SetWidgetSpace(EWidgetSpace::World);
    SolidBubble->SetPivot(FVector2D(0.5f, 1.0f));
    SolidBubble->SetBlendMode(EWidgetBlendMode::Transparent);
    SolidBubble->SetBackgroundColor(FLinearColor::Transparent);
    SolidBubble->SetTintColorAndOpacity(FLinearColor::White);
    SolidBubble->SetTwoSided(false);
    SolidBubble->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    SolidBubble->SetCastShadow(false);
    SolidBubble->SetTranslucentSortPriority(20);
    SolidBubble->SetWidgetClass(UAocietyNPCBubbleWidget::StaticClass());
    SolidBubble->SetVisibility(false);
    SolidBubble->InitWidget();
    Nameplate->SetText(FText::FromString(
        FString::Printf(TEXT("%s [%s] · DeepSeek V4 Flash"), *DisplayName, *NpcId)));
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
        *ResidentVisual->GetRelativeScale3D().ToCompactString(),
        *GetNameSafe(IdleAnimation),
        *GetNameSafe(WalkAnimation));
}

void AAocietyNPCCharacter::EndPlay(
    const EEndPlayReason::Type EndPlayReason)
{
    if (IsValid(RuntimeVisualActor))
    {
        RuntimeVisualActor->Destroy();
        RuntimeVisualActor = nullptr;
    }
    Super::EndPlay(EndPlayReason);
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
        if (ToPlayer.SizeSquared2D() < FMath::Square(150.0f))
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
    SolidBubble->SetVisibility(true);
    if (UAocietyNPCBubbleWidget* Widget =
            Cast<UAocietyNPCBubbleWidget>(SolidBubble->GetUserWidgetObject()))
    {
        Widget->SetThinking(DisplayName, TEXT("deepseek-v4-flash"));
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
    SolidBubble->SetVisibility(true);
    if (UAocietyNPCBubbleWidget* Widget =
            Cast<UAocietyNPCBubbleWidget>(SolidBubble->GetUserWidgetObject()))
    {
        Widget->SetListening(DisplayName, SpeakerName, TEXT("deepseek-v4-flash"));
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

    USkeletalMeshComponent* VisualMesh = GetResidentVisual();
    if (!VisualMesh)
    {
        return;
    }
    if (VisualMesh->GetSkeletalMeshAsset() != GetMesh()->GetSkeletalMeshAsset())
    {
        return;
    }
    VisualMesh->SetRelativeScale3D(FVector::OneVector);
    VisualMesh->SetAnimationMode(EAnimationMode::AnimationSingleNode);
    VisualMesh->PlayAnimation(Desired, true);
    ActiveAnimation = Desired;

    UE_LOG(LogTemp, Log,
        TEXT("[AocietyNPC] %s animation=%s speed=%.1f"),
        *NpcId, bMoving ? TEXT("walk") : TEXT("idle"),
        GetVelocity().Size2D());
}

void AAocietyNPCCharacter::ClearDialogue()
{
    if (UAocietyNPCBubbleWidget* Widget =
            Cast<UAocietyNPCBubbleWidget>(SolidBubble->GetUserWidgetObject()))
    {
        Widget->SetIdle(DisplayName);
    }
    SolidBubble->SetVisibility(false);
}
