// Copyright Aociety. All rights reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AocietyWorldBoundary.generated.h"

class UBoxComponent;

/** Invisible collision perimeter that keeps the playable demo on the authored terrain. */
UCLASS(NotPlaceable)
class AOCIETY_API AAocietyWorldBoundary : public AActor
{
    GENERATED_BODY()

public:
    AAocietyWorldBoundary();

    void Configure(const FVector2D& MinXY, const FVector2D& MaxXY,
        float BottomZ = -500.0f, float TopZ = 2000.0f,
        float WallThickness = 40.0f);

private:
    UPROPERTY(VisibleAnywhere)
    TObjectPtr<USceneComponent> SceneRoot;

    UPROPERTY(VisibleAnywhere)
    TObjectPtr<UBoxComponent> WestWall;

    UPROPERTY(VisibleAnywhere)
    TObjectPtr<UBoxComponent> EastWall;

    UPROPERTY(VisibleAnywhere)
    TObjectPtr<UBoxComponent> SouthWall;

    UPROPERTY(VisibleAnywhere)
    TObjectPtr<UBoxComponent> NorthWall;
};
