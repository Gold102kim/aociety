// Copyright Aociety. All rights reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "AocietyPlayerCharacter.generated.h"

class UCameraComponent;
class USpringArmComponent;
class AAocietyNPCCharacter;

UCLASS()
class AOCIETY_API AAocietyPlayerCharacter : public ACharacter
{
    GENERATED_BODY()

public:
    AAocietyPlayerCharacter();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;

    void SetNearbyNPC(AAocietyNPCCharacter* NPC);
    void ClearNearbyNPC(AAocietyNPCCharacter* NPC);

protected:
    virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;

private:
    void MoveForward(float Value);
    void MoveRight(float Value);
    void Interact();

    UPROPERTY(VisibleAnywhere, Category="Aociety|Camera")
    TObjectPtr<USpringArmComponent> CameraBoom;

    UPROPERTY(VisibleAnywhere, Category="Aociety|Camera")
    TObjectPtr<UCameraComponent> FollowCamera;

    UPROPERTY()
    TObjectPtr<class UAnimSequence> IdleAnimation;

    UPROPERTY()
    TObjectPtr<class UAnimSequence> WalkAnimation;

    TWeakObjectPtr<AAocietyNPCCharacter> NearbyNPC;
    bool bWasMoving = false;
};
