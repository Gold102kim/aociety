// Copyright Aociety. All rights reserved.

#include "AocietyWorldBoundary.h"

#include "Components/BoxComponent.h"

namespace
{
void ConfigureWall(UBoxComponent* Wall)
{
    if (!Wall)
    {
        return;
    }
    Wall->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
    Wall->SetCollisionProfileName(TEXT("BlockAll"));
    Wall->SetCollisionResponseToAllChannels(ECR_Block);
    Wall->SetGenerateOverlapEvents(false);
    Wall->SetCanEverAffectNavigation(false);
    Wall->SetVisibility(false, true);
    Wall->SetHiddenInGame(true);
    Wall->bIsEditorOnly = false;
}
}

AAocietyWorldBoundary::AAocietyWorldBoundary()
{
    PrimaryActorTick.bCanEverTick = false;
    SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("BoundaryRoot"));
    RootComponent = SceneRoot;

    WestWall = CreateDefaultSubobject<UBoxComponent>(TEXT("WestWall"));
    EastWall = CreateDefaultSubobject<UBoxComponent>(TEXT("EastWall"));
    SouthWall = CreateDefaultSubobject<UBoxComponent>(TEXT("SouthWall"));
    NorthWall = CreateDefaultSubobject<UBoxComponent>(TEXT("NorthWall"));
    WestWall->SetupAttachment(SceneRoot);
    EastWall->SetupAttachment(SceneRoot);
    SouthWall->SetupAttachment(SceneRoot);
    NorthWall->SetupAttachment(SceneRoot);
    ConfigureWall(WestWall);
    ConfigureWall(EastWall);
    ConfigureWall(SouthWall);
    ConfigureWall(NorthWall);
}

void AAocietyWorldBoundary::Configure(
    const FVector2D& MinXY, const FVector2D& MaxXY,
    float BottomZ, float TopZ, float WallThickness)
{
    const float Width = FMath::Max(100.0f, MaxXY.X - MinXY.X);
    const float Depth = FMath::Max(100.0f, MaxXY.Y - MinXY.Y);
    const float Height = FMath::Max(100.0f, TopZ - BottomZ);
    const float CenterZ = (TopZ + BottomZ) * 0.5f;
    const float HalfThickness = FMath::Max(1.0f, WallThickness * 0.5f);

    WestWall->SetRelativeLocation(FVector(MinXY.X - HalfThickness, (MinXY.Y + MaxXY.Y) * 0.5f, CenterZ));
    WestWall->SetBoxExtent(FVector(HalfThickness, Depth * 0.5f + WallThickness, Height * 0.5f));
    EastWall->SetRelativeLocation(FVector(MaxXY.X + HalfThickness, (MinXY.Y + MaxXY.Y) * 0.5f, CenterZ));
    EastWall->SetBoxExtent(FVector(HalfThickness, Depth * 0.5f + WallThickness, Height * 0.5f));
    SouthWall->SetRelativeLocation(FVector((MinXY.X + MaxXY.X) * 0.5f, MinXY.Y - HalfThickness, CenterZ));
    SouthWall->SetBoxExtent(FVector(Width * 0.5f + WallThickness, HalfThickness, Height * 0.5f));
    NorthWall->SetRelativeLocation(FVector((MinXY.X + MaxXY.X) * 0.5f, MaxXY.Y + HalfThickness, CenterZ));
    NorthWall->SetBoxExtent(FVector(Width * 0.5f + WallThickness, HalfThickness, Height * 0.5f));
}
