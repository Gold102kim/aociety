// Copyright Aociety. All rights reserved.

#include "AocietyPlayerCharacter.h"
#include "AocietyClientSubsystem.h"
#include "AocietyNPCCharacter.h"

#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/Controller.h"
#include "GameFramework/SpringArmComponent.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "UObject/ConstructorHelpers.h"
#include "Animation/AnimSequence.h"

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
    CameraBoom->SetRelativeLocation(FVector(0.0f, 0.0f, 115.0f));
    CameraBoom->TargetArmLength = 520.0f;
    CameraBoom->SocketOffset = FVector(0.0f, 70.0f, 25.0f);
    CameraBoom->bUsePawnControlRotation = true;
    CameraBoom->bDoCollisionTest = false;
    CameraBoom->bEnableCameraLag = true;
    CameraBoom->CameraLagSpeed = 12.0f;

    FollowCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FollowCamera"));
    FollowCamera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
    FollowCamera->bUsePawnControlRotation = false;

    static ConstructorHelpers::FObjectFinder<USkeletalMesh> EcyMesh(
        TEXT("/Game/Aociety/Characters/Ecy/SK_Ecy.SK_Ecy"));
    if (EcyMesh.Succeeded())
    {
        GetMesh()->SetSkeletalMeshAsset(EcyMesh.Object);
        GetMesh()->SetRelativeLocation(FVector(0.0f, 0.0f, -88.0f));
        GetMesh()->SetRelativeRotation(FRotator(0.0f, -90.0f, 0.0f));
        GetMesh()->SetRelativeScale3D(FVector(1.55f));
    }

    static ConstructorHelpers::FObjectFinder<UAnimSequence> IdleAsset(
        TEXT("/Game/Aociety/Characters/Ecy/Animations/A_Ecy_Idle.A_Ecy_Idle"));
    static ConstructorHelpers::FObjectFinder<UAnimSequence> WalkAsset(
        TEXT("/Game/Aociety/Characters/Ecy/Animations/A_Ecy_Walk.A_Ecy_Walk"));
    IdleAnimation = IdleAsset.Object;
    WalkAnimation = WalkAsset.Object;
    if (IdleAnimation)
    {
        GetMesh()->SetAnimationMode(EAnimationMode::AnimationSingleNode);
        GetMesh()->PlayAnimation(IdleAnimation, true);
    }
}

void AAocietyPlayerCharacter::BeginPlay()
{
    Super::BeginPlay();
    if (IdleAnimation)
    {
        GetMesh()->SetAnimationMode(EAnimationMode::AnimationSingleNode);
        GetMesh()->PlayAnimation(IdleAnimation, true);
    }
}

void AAocietyPlayerCharacter::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    const bool bMoving = GetVelocity().SizeSquared2D() > FMath::Square(8.0f);
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
}

void AAocietyPlayerCharacter::SetNearbyNPC(AAocietyNPCCharacter* NPC)
{
    NearbyNPC = NPC;
    if (GEngine && IsValid(NPC))
    {
        GEngine->AddOnScreenDebugMessage(
            -1, 6.0f, FColor(255, 220, 120),
            FString::Printf(TEXT("按 E 与 %s [%s] 交谈"),
                *NPC->DisplayName, *NPC->NpcId));
    }
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
    AAocietyNPCCharacter* NPC = NearbyNPC.Get();
    if (!IsValid(NPC))
    {
        if (GEngine)
        {
            GEngine->AddOnScreenDebugMessage(
                -1, 2.5f, FColor(180, 210, 255),
                TEXT("请先靠近一名居民"));
        }
        return;
    }

    UGameInstance* GameInstance = GetGameInstance();
    UAocietyClientSubsystem* Client = GameInstance
        ? GameInstance->GetSubsystem<UAocietyClientSubsystem>()
        : nullptr;
    if (!Client)
    {
        return;
    }

    NPC->ShowThinking();
    Client->RequestNPCDialogue(
        NPC->NpcId,
        TEXT("玩家刚刚走到你面前并按下交互键。请观察当下环境、回想最近交流，再决定这一刻自然说什么。不要重复固定欢迎语。"),
        TEXT("forest_town"),
        TEXT("player_interaction"));
}

void AAocietyPlayerCharacter::MoveForward(float Value)
{
    if (Controller && !FMath::IsNearlyZero(Value))
    {
        const FRotator YawRotation(0.0f, Controller->GetControlRotation().Yaw, 0.0f);
        AddMovementInput(FRotationMatrix(YawRotation).GetUnitAxis(EAxis::X), Value);
    }
}

void AAocietyPlayerCharacter::MoveRight(float Value)
{
    if (Controller && !FMath::IsNearlyZero(Value))
    {
        const FRotator YawRotation(0.0f, Controller->GetControlRotation().Yaw, 0.0f);
        AddMovementInput(FRotationMatrix(YawRotation).GetUnitAxis(EAxis::Y), Value);
    }
}
