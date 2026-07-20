// Copyright Aociety. 保留所有权利.

#include "AocietyGameMode.h"
#include "AocietyClientSubsystem.h"
#include "AocietyPlayerCharacter.h"
#include "AocietyNPCCharacter.h"
#include "AocietyWorldBoundary.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/LightComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/SpotLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/PointLight.h"
#include "Engine/SkyLight.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/GameInstance.h"
#include "EngineUtils.h"
#include "HAL/FileManager.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "TimerManager.h"

namespace
{
AAocietyNPCCharacter* FindResidentNPC(
    const UObject* WorldContext,
    const FString& NpcId)
{
    if (!WorldContext || NpcId.IsEmpty())
    {
        return nullptr;
    }

    TArray<AActor*> MatchingActors;
    UGameplayStatics::GetAllActorsWithTag(
        WorldContext, FName(*NpcId), MatchingActors);
    for (AActor* Actor : MatchingActors)
    {
        if (AAocietyNPCCharacter* NPC = Cast<AAocietyNPCCharacter>(Actor))
        {
            return NPC;
        }
    }
    return nullptr;
}

FString GetResidentDisplayName(
    const UObject* WorldContext,
    const FString& NpcId)
{
    if (const AAocietyNPCCharacter* NPC = FindResidentNPC(WorldContext, NpcId))
    {
        return NPC->DisplayName;
    }
    if (NpcId == TEXT("npc_01"))
    {
        return TEXT("林汐");
    }
    if (NpcId == TEXT("npc_02"))
    {
        return TEXT("小樱");
    }
    return TEXT("小镇居民");
}

AStaticMeshActor* SpawnFallbackShape(
    UWorld* World,
    UStaticMesh* Mesh,
    UMaterialInterface* BaseMaterial,
    const TCHAR* Name,
    const FVector& Location,
    const FVector& Scale,
    const FLinearColor& Color,
    bool bCollision = true)
{
    if (!World || !Mesh)
    {
        return nullptr;
    }

    FActorSpawnParameters Parameters;
    Parameters.Name = MakeUniqueObjectName(
        World, AStaticMeshActor::StaticClass(), FName(Name));
    AStaticMeshActor* Actor = World->SpawnActor<AStaticMeshActor>(
        AStaticMeshActor::StaticClass(),
        Location,
        FRotator::ZeroRotator,
        Parameters);
    if (!Actor)
    {
        return nullptr;
    }

    Actor->SetActorScale3D(Scale);
    UStaticMeshComponent* Component = Actor->GetStaticMeshComponent();
    Component->SetMobility(EComponentMobility::Movable);
    Component->SetStaticMesh(Mesh);
    Component->SetCollisionEnabled(
        bCollision
            ? ECollisionEnabled::QueryAndPhysics
            : ECollisionEnabled::NoCollision);
    Component->SetCollisionProfileName(
        bCollision ? TEXT("BlockAll") : TEXT("NoCollision"));
    if (BaseMaterial)
    {
        UMaterialInstanceDynamic* Material =
            UMaterialInstanceDynamic::Create(BaseMaterial, Actor);
        if (Material)
        {
            Material->SetVectorParameterValue(TEXT("Color"), Color);
            Material->SetVectorParameterValue(TEXT("BaseColor"), Color);
            Component->SetMaterial(0, Material);
        }
    }
    return Actor;
}
}

AAocietyGameMode::AAocietyGameMode()
{
    DefaultPawnClass = AAocietyPlayerCharacter::StaticClass();
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickInterval = 0.1f;
}

void AAocietyGameMode::BeginPlay()
{
    Super::BeginPlay();

    InitializeFallbackCity();

    if (UWorld* World = GetWorld())
    {
        AAocietyWorldBoundary* Boundary = nullptr;
        for (TActorIterator<AAocietyWorldBoundary> It(World); It; ++It)
        {
            Boundary = *It;
            break;
        }
        if (!Boundary)
        {
            Boundary = World->SpawnActor<AAocietyWorldBoundary>(
                AAocietyWorldBoundary::StaticClass(),
                FVector::ZeroVector,
                FRotator::ZeroRotator);
        }
        if (Boundary)
        {
            Boundary->Configure(
                FVector2D(-5500.0f, -6500.0f),
                FVector2D(15000.0f, 8000.0f));
        }

        if (AAocietyPlayerCharacter* Player = Cast<AAocietyPlayerCharacter>(
                UGameplayStatics::GetPlayerPawn(World, 0)))
        {
            Player->SetActorLocation(
                FVector(5200.0f, -350.0f, 140.0f),
                false,
                nullptr,
                ETeleportType::TeleportPhysics);
            if (AController* Controller = Player->GetController())
            {
                Controller->SetControlRotation(FRotator(0.0f, 0.0f, 0.0f));
            }
            UE_LOG(
                LogTemp,
                Display,
                TEXT("[AocietyExpansion] player relocated to city approach"));
        }

        if (AAocietyNPCCharacter* Resident = FindResidentNPC(this, TEXT("npc_01")))
        {
            Resident->SetActorLocation(
                FVector(6200.0f, -300.0f, 115.0f),
                false,
                nullptr,
                ETeleportType::TeleportPhysics);
        }
        if (AAocietyNPCCharacter* Resident = FindResidentNPC(this, TEXT("npc_02")))
        {
            Resident->SetActorLocation(
                FVector(7000.0f, 450.0f, 115.0f),
                false,
                nullptr,
                ETeleportType::TeleportPhysics);
        }
    }

    InitializeWorldEnvironment();

    TArray<AActor*> DialogueTriggers;
    UGameplayStatics::GetAllActorsWithTag(
        this, FName("AocietyDialogueTrigger"), DialogueTriggers);

    for (AActor* Trigger : DialogueTriggers)
    {
        if (IsValid(Trigger))
        {
            Trigger->OnActorBeginOverlap.AddDynamic(
                this, &AAocietyGameMode::HandleDialogueTrigger);
            Trigger->OnActorEndOverlap.AddDynamic(
                this, &AAocietyGameMode::HandleDialogueTriggerEnd);
        }
    }

    if (UGameInstance* GameInstance = GetGameInstance())
    {
        if (UAocietyClientSubsystem* Client =
                GameInstance->GetSubsystem<UAocietyClientSubsystem>())
        {
            Client->OnNPCDialogue.AddDynamic(
                this, &AAocietyGameMode::HandleNPCDialogue);
        }
    }

    UE_LOG(LogTemp, Log, TEXT("[AocietyGameMode] Bound %d DeepSeek dialogue triggers"),
           DialogueTriggers.Num());

    GetWorldTimerManager().SetTimer(
        AmbientConversationTimer, this,
        &AAocietyGameMode::StartAmbientNPCConversation,
        32.0f, true, 14.0f);
}

void AAocietyGameMode::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    UpdateWorldEnvironment(DeltaSeconds);
}

void AAocietyGameMode::InitializeFallbackCity()
{
    const FString MarketplaceAsset = FPaths::Combine(
        FPaths::ProjectContentDir(),
        TEXT("Modular_Rural_Cabin/Meshes/Modular/Wall_8m2.uasset"));
    if (IFileManager::Get().FileExists(*MarketplaceAsset))
    {
        UE_LOG(
            LogTemp,
            Display,
            TEXT("[AocietyScene] ready source=marketplace"));
        return;
    }

    UWorld* World = GetWorld();
    UStaticMesh* Cube = LoadObject<UStaticMesh>(
        nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
    UStaticMesh* Cylinder = LoadObject<UStaticMesh>(
        nullptr, TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
    UStaticMesh* Sphere = LoadObject<UStaticMesh>(
        nullptr, TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    UMaterialInterface* Material = LoadObject<UMaterialInterface>(
        nullptr,
        TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
    if (!World || !Cube || !Cylinder || !Sphere)
    {
        UE_LOG(LogTemp, Error, TEXT("[AocietyScene] fallback assets unavailable"));
        return;
    }

    int32 SpawnedActors = 0;
    auto Spawn = [&SpawnedActors](
                     UWorld* InWorld,
                     UStaticMesh* Mesh,
                     UMaterialInterface* InMaterial,
                     const TCHAR* Name,
                     const FVector& Location,
                     const FVector& Scale,
                     const FLinearColor& Color,
                     bool bCollision = true)
    {
        if (SpawnFallbackShape(
                InWorld,
                Mesh,
                InMaterial,
                Name,
                Location,
                Scale,
                Color,
                bCollision))
        {
            ++SpawnedActors;
        }
    };

    Spawn(
        World, Cube, Material, TEXT("FallbackCityGround"),
        FVector(7600.0f, 0.0f, -50.0f), FVector(70.0f, 50.0f, 1.0f),
        FLinearColor(0.12f, 0.20f, 0.16f));
    Spawn(
        World, Cube, Material, TEXT("FallbackCityRoad"),
        FVector(7600.0f, 0.0f, 8.0f), FVector(70.0f, 5.0f, 0.12f),
        FLinearColor(0.08f, 0.10f, 0.13f), false);
    Spawn(
        World, Cube, Material, TEXT("FallbackCityPlaza"),
        FVector(6500.0f, 0.0f, 16.0f), FVector(16.0f, 15.0f, 0.12f),
        FLinearColor(0.25f, 0.28f, 0.30f), false);

    const FVector HouseLocations[] = {
        FVector(6500.0f, -1500.0f, 220.0f),
        FVector(7600.0f, -1500.0f, 220.0f),
        FVector(8800.0f, -1500.0f, 220.0f),
        FVector(6500.0f, 1500.0f, 220.0f),
        FVector(7600.0f, 1500.0f, 220.0f),
        FVector(8800.0f, 1500.0f, 220.0f)};
    const FLinearColor HouseColors[] = {
        FLinearColor(0.10f, 0.42f, 0.48f),
        FLinearColor(0.45f, 0.22f, 0.30f),
        FLinearColor(0.22f, 0.34f, 0.52f)};
    for (int32 Index = 0; Index < UE_ARRAY_COUNT(HouseLocations); ++Index)
    {
        const FString BodyName = FString::Printf(TEXT("FallbackHouseBody_%02d"), Index);
        const FString RoofName = FString::Printf(TEXT("FallbackHouseRoof_%02d"), Index);
        const FString DoorName = FString::Printf(TEXT("FallbackHouseDoor_%02d"), Index);
        Spawn(
            World, Cube, Material, *BodyName,
            HouseLocations[Index], FVector(7.0f, 5.0f, 4.4f),
            HouseColors[Index % UE_ARRAY_COUNT(HouseColors)]);
        Spawn(
            World, Cube, Material, *RoofName,
            HouseLocations[Index] + FVector(0.0f, 0.0f, 255.0f),
            FVector(7.8f, 5.8f, 0.7f),
            FLinearColor(0.06f, 0.09f, 0.13f));
        const float DoorY = HouseLocations[Index].Y > 0.0f
            ? HouseLocations[Index].Y - 255.0f
            : HouseLocations[Index].Y + 255.0f;
        Spawn(
            World, Cube, Material, *DoorName,
            FVector(HouseLocations[Index].X, DoorY, 130.0f),
            FVector(1.3f, 0.25f, 2.6f),
            FLinearColor(0.14f, 0.08f, 0.05f), false);
    }

    const FVector TreeLocations[] = {
        FVector(5700.0f, -2200.0f, 150.0f),
        FVector(7000.0f, -2400.0f, 150.0f),
        FVector(8300.0f, -2350.0f, 150.0f),
        FVector(9600.0f, -2100.0f, 150.0f),
        FVector(5700.0f, 2200.0f, 150.0f),
        FVector(7000.0f, 2400.0f, 150.0f),
        FVector(8300.0f, 2350.0f, 150.0f),
        FVector(9600.0f, 2100.0f, 150.0f)};
    for (int32 Index = 0; Index < UE_ARRAY_COUNT(TreeLocations); ++Index)
    {
        const FString TrunkName = FString::Printf(TEXT("FallbackTreeTrunk_%02d"), Index);
        const FString CrownName = FString::Printf(TEXT("FallbackTreeCrown_%02d"), Index);
        Spawn(
            World, Cylinder, Material, *TrunkName,
            TreeLocations[Index], FVector(0.55f, 0.55f, 3.0f),
            FLinearColor(0.18f, 0.09f, 0.04f));
        Spawn(
            World, Sphere, Material, *CrownName,
            TreeLocations[Index] + FVector(0.0f, 0.0f, 260.0f),
            FVector(2.5f, 2.5f, 2.8f),
            FLinearColor(0.08f, 0.32f, 0.20f), false);
    }

    const FVector LampLocations[] = {
        FVector(5900.0f, -600.0f, 180.0f),
        FVector(7000.0f, 600.0f, 180.0f),
        FVector(8200.0f, -600.0f, 180.0f),
        FVector(9400.0f, 600.0f, 180.0f)};
    for (int32 Index = 0; Index < UE_ARRAY_COUNT(LampLocations); ++Index)
    {
        const FString PoleName = FString::Printf(TEXT("FallbackLampPole_%02d"), Index);
        const FString GlowName = FString::Printf(TEXT("FallbackLampGlow_%02d"), Index);
        Spawn(
            World, Cylinder, Material, *PoleName,
            LampLocations[Index], FVector(0.16f, 0.16f, 3.6f),
            FLinearColor(0.04f, 0.06f, 0.08f));
        Spawn(
            World, Sphere, Material, *GlowName,
            LampLocations[Index] + FVector(0.0f, 0.0f, 210.0f),
            FVector(0.45f), FLinearColor(0.25f, 0.95f, 0.80f), false);
    }

    UE_LOG(
        LogTemp,
        Display,
        TEXT("[AocietyScene] ready source=fallback actors=%d"),
        SpawnedActors);
}

void AAocietyGameMode::InitializeWorldEnvironment()
{
    UWorld* World = GetWorld();
    if (!World)
    {
        return;
    }

    float RequestedStartHour = 0.0f;
    if (FParse::Value(
            FCommandLine::Get(), TEXT("AocietyStartHour="), RequestedStartHour))
    {
        WorldClockMinutes = FMath::Fmod(
            FMath::Max(0.0f, RequestedStartHour), 24.0f) * 60.0f;
    }
    FParse::Value(
        FCommandLine::Get(), TEXT("AocietyWeatherState="), WeatherState);
    WeatherState = FMath::Clamp(WeatherState, 0, 2);

    TArray<AActor*> Directionals;
    UGameplayStatics::GetAllActorsOfClass(
        World, ADirectionalLight::StaticClass(), Directionals);
    ADirectionalLight* FallbackSun = nullptr;
    for (AActor* Actor : Directionals)
    {
        if (ADirectionalLight* Candidate = Cast<ADirectionalLight>(Actor))
        {
            if (!FallbackSun)
            {
                FallbackSun = Candidate;
            }
            const UDirectionalLightComponent* Component =
                Cast<UDirectionalLightComponent>(Candidate->GetLightComponent());
            if (Component && Component->bAtmosphereSunLight)
            {
                SunLight = Candidate;
            }
        }
    }
    if (!SunLight.IsValid())
    {
        SunLight = FallbackSun;
    }
    for (AActor* Actor : Directionals)
    {
        if (ADirectionalLight* Candidate = Cast<ADirectionalLight>(Actor))
        {
            if (Candidate == SunLight.Get())
            {
                Candidate->GetLightComponent()->SetMobility(
                    EComponentMobility::Movable);
            }
            else
            {
                Candidate->GetLightComponent()->SetVisibility(false);
            }
        }
    }

    TArray<AActor*> Skies;
    UGameplayStatics::GetAllActorsOfClass(
        World, ASkyLight::StaticClass(), Skies);
    if (Skies.Num() > 0)
    {
        SkyLight = Cast<ASkyLight>(Skies[0]);
        if (SkyLight.IsValid())
        {
            SkyLight->GetLightComponent()->SetMobility(
                EComponentMobility::Movable);
        }
    }

    TArray<AActor*> Fogs;
    UGameplayStatics::GetAllActorsOfClass(
        World, AExponentialHeightFog::StaticClass(), Fogs);
    if (Fogs.Num() > 0)
    {
        HeightFog = Cast<AExponentialHeightFog>(Fogs[0]);
    }

    for (TActorIterator<AActor> It(World); It; ++It)
    {
        TArray<ULightComponent*> Components;
        It->GetComponents<ULightComponent>(Components);
        for (ULightComponent* Component : Components)
        {
            if (!Component
                || (!Component->IsA<UPointLightComponent>()
                    && !Component->IsA<USpotLightComponent>()))
            {
                continue;
            }
            NightLights.Add(Component);
            OriginalLightIntensities.Add(Component, Component->Intensity);
        }
    }
    if (NightLights.Num() == 0)
    {
        const FVector LightLocations[] = {
            FVector(-980.0f, -260.0f, 420.0f),
            FVector(720.0f, -180.0f, 420.0f),
            FVector(-760.0f, 1080.0f, 420.0f),
            FVector(1120.0f, 1120.0f, 420.0f),
            FVector(0.0f, 320.0f, 520.0f)};
        for (const FVector& Location : LightLocations)
        {
            APointLight* Actor = World->SpawnActor<APointLight>(
                APointLight::StaticClass(), Location, FRotator::ZeroRotator);
            if (!Actor)
            {
                continue;
            }
            UPointLightComponent* Component =
                Cast<UPointLightComponent>(Actor->GetLightComponent());
            if (!Component)
            {
                continue;
            }
            Component->SetMobility(EComponentMobility::Movable);
            Component->SetIntensity(8000.0f);
            Component->SetAttenuationRadius(1100.0f);
            Component->SetLightColor(FLinearColor(1.0f, 0.56f, 0.24f));
            Component->SetCastShadows(true);
            NightLights.Add(Component);
            OriginalLightIntensities.Add(Component, Component->Intensity);
        }
    }
    bWorldEnvironmentInitialized = true;
    UE_LOG(
        LogTemp,
        Display,
        TEXT("[AocietyEnvironment] initialized sun=%s skylight=%s fog=%s night_lights=%d"),
        *GetNameSafe(SunLight.Get()),
        *GetNameSafe(SkyLight.Get()),
        *GetNameSafe(HeightFog.Get()),
        NightLights.Num());
}

void AAocietyGameMode::UpdateWorldEnvironment(float DeltaSeconds)
{
    if (!bWorldEnvironmentInitialized)
    {
        return;
    }

    WorldClockMinutes = FMath::Fmod(
        WorldClockMinutes + DeltaSeconds * (1440.0f / WorldDayLengthSeconds),
        1440.0f);
    if (WorldClockMinutes < 0.0f)
    {
        WorldClockMinutes += 1440.0f;
    }
    WeatherElapsedSeconds += DeltaSeconds;
    if (WeatherElapsedSeconds > 75.0f)
    {
        WeatherElapsedSeconds = 0.0f;
        WeatherState = (WeatherState + 1) % 3;
        UE_LOG(
            LogTemp,
            Display,
            TEXT("[AocietyEnvironment] weather=%s"),
            WeatherState == 0
                ? TEXT("clear")
                : WeatherState == 1 ? TEXT("overcast") : TEXT("rain"));
    }

    const float WeatherLightScale = WeatherState == 0
        ? 1.0f
        : WeatherState == 1 ? 0.72f : 0.48f;
    const float SunAngle =
        (WorldClockMinutes / 1440.0f) * 360.0f - 90.0f;
    const float SolarElevation =
        FMath::Sin(FMath::DegreesToRadians(SunAngle));
    const bool bNight = SolarElevation < -0.08f;
    const float DayBlend =
        FMath::Clamp((SolarElevation + 0.12f) / 0.45f, 0.0f, 1.0f);

    if (SunLight.IsValid())
    {
        SunLight->SetActorRotation(FRotator(-SunAngle, -35.0f, 0.0f));
        if (UDirectionalLightComponent* Light =
                Cast<UDirectionalLightComponent>(
                    SunLight->GetLightComponent()))
        {
            Light->SetIntensity(
                FMath::Lerp(0.35f, 4.2f, DayBlend) * WeatherLightScale);
            const FLinearColor DayColor = WeatherState == 0
                ? FLinearColor(1.0f, 0.88f, 0.68f)
                : FLinearColor(0.72f, 0.76f, 0.82f);
            Light->SetLightColor(FLinearColor::LerpUsingHSV(
                FLinearColor(0.18f, 0.24f, 0.42f),
                DayColor,
                DayBlend));
        }
    }
    if (SkyLight.IsValid())
    {
        USkyLightComponent* Light = SkyLight->GetLightComponent();
        Light->SetIntensity(
            FMath::Lerp(0.62f, 1.0f, DayBlend)
            * FMath::Lerp(0.9f, 1.0f, WeatherLightScale));
        Light->SetLightColor(
            WeatherState == 0
                ? FLinearColor::White
                : FLinearColor(0.62f, 0.68f, 0.76f));
    }

    if (HeightFog.IsValid())
    {
        UExponentialHeightFogComponent* Fog = HeightFog->GetComponent();
        const float WeatherFog = WeatherState == 0
            ? 0.0008f
            : WeatherState == 1 ? 0.0022f : 0.0045f;
        Fog->FogDensity = FMath::Lerp(
            WeatherFog,
            WeatherFog * 1.35f,
            bNight ? 1.0f : 0.0f);
        Fog->FogHeightFalloff = 0.18f;
        Fog->SetFogInscatteringColor(
            bNight
                ? FLinearColor(0.025f, 0.04f, 0.10f)
                : FLinearColor(0.72f, 0.82f, 1.0f));
    }
    for (const TWeakObjectPtr<ULightComponent>& WeakLight : NightLights)
    {
        if (ULightComponent* Light = WeakLight.Get())
        {
            const float* Original = OriginalLightIntensities.Find(WeakLight);
            Light->SetVisibility(bNight);
            if (Original)
            {
                Light->SetIntensity(bNight ? *Original : 0.0f);
            }
        }
    }
}

void AAocietyGameMode::HandleDialogueTrigger(AActor* TriggerActor, AActor* OtherActor)
{
    AAocietyPlayerCharacter* Player = Cast<AAocietyPlayerCharacter>(OtherActor);
    if (!IsValid(TriggerActor) || !IsValid(Player))
    {
        return;
    }

    FString NpcId;
    for (const FName& Tag : TriggerActor->Tags)
    {
        const FString TagText = Tag.ToString();
        if (TagText.StartsWith(TEXT("npc_")))
        {
            NpcId = TagText;
            break;
        }
    }
    if (NpcId.IsEmpty())
    {
        return;
    }

    TArray<AActor*> MatchingNPCs;
    UGameplayStatics::GetAllActorsWithTag(this, FName(*NpcId), MatchingNPCs);
    for (AActor* Actor : MatchingNPCs)
    {
        if (AAocietyNPCCharacter* NPC = Cast<AAocietyNPCCharacter>(Actor))
        {
            Player->SetNearbyNPC(NPC);
            return;
        }
    }
}

void AAocietyGameMode::HandleDialogueTriggerEnd(
    AActor* TriggerActor, AActor* OtherActor)
{
    AAocietyPlayerCharacter* Player = Cast<AAocietyPlayerCharacter>(OtherActor);
    if (!IsValid(TriggerActor) || !IsValid(Player))
    {
        return;
    }

    for (const FName& Tag : TriggerActor->Tags)
    {
        const FString TagText = Tag.ToString();
        if (!TagText.StartsWith(TEXT("npc_")))
        {
            continue;
        }
        TArray<AActor*> MatchingNPCs;
        UGameplayStatics::GetAllActorsWithTag(this, Tag, MatchingNPCs);
        for (AActor* Actor : MatchingNPCs)
        {
            if (AAocietyNPCCharacter* NPC = Cast<AAocietyNPCCharacter>(Actor))
            {
                Player->ClearNearbyNPC(NPC);
            }
        }
    }
}

void AAocietyGameMode::HandleNPCDialogue(FAocietyNPCDialogue Dialogue)
{
    AAocietyNPCCharacter* Speaker = FindResidentNPC(this, Dialogue.NpcId);
    const FString SpeakerName = Speaker
        ? Speaker->DisplayName
        : GetResidentDisplayName(this, Dialogue.NpcId);
    const FString Attribution = Dialogue.Model.IsEmpty()
        ? Dialogue.Source
        : FString::Printf(TEXT("%s / %s"), *Dialogue.Source, *Dialogue.Model);

    UE_LOG(LogTemp, Log, TEXT("[Aociety][NPC] %s: %s (%s)"),
           *Dialogue.NpcId, *Dialogue.Message, *Attribution);

    if (!Speaker)
    {
        UE_LOG(LogTemp, Warning,
            TEXT("[Aociety][NPC] No world actor found for %s"),
            *Dialogue.NpcId);
        return;
    }

    const bool bAmbient = Dialogue.Mode.Equals(
        TEXT("ambient"), ESearchCase::IgnoreCase) &&
        !Dialogue.CounterpartId.IsEmpty();
    AAocietyNPCCharacter* Listener = bAmbient
        ? FindResidentNPC(this, Dialogue.CounterpartId)
        : nullptr;
    const FString ListenerName = bAmbient
        ? GetResidentDisplayName(this, Dialogue.CounterpartId)
        : FString();
    const FString VisibleLine = bAmbient
        ? FString::Printf(TEXT("对 %s：%s"),
            *ListenerName, *Dialogue.Message)
        : Dialogue.Message;

    Speaker->ShowDialogue(
        VisibleLine,
        Dialogue.Source.IsEmpty() ? TEXT("error") : Dialogue.Source,
        Dialogue.Model.IsEmpty() ? TEXT("unavailable") : Dialogue.Model,
        12.0f);

    if (Listener)
    {
        Speaker->FocusOnActor(Listener, 12.0f);
        Listener->FocusOnActor(Speaker, 12.0f);
        Listener->ShowListening(SpeakerName, 12.0f);
    }
}

void AAocietyGameMode::StartAmbientNPCConversation()
{
    UGameInstance* GameInstance = GetGameInstance();
    UAocietyClientSubsystem* Client = GameInstance
        ? GameInstance->GetSubsystem<UAocietyClientSubsystem>()
        : nullptr;
    if (!Client)
    {
        return;
    }

    const FString SpeakerId = bAmbientSpeakerIsNpc01 ? TEXT("npc_01") : TEXT("npc_02");
    const FString ListenerId = bAmbientSpeakerIsNpc01 ? TEXT("npc_02") : TEXT("npc_01");
    bAmbientSpeakerIsNpc01 = !bAmbientSpeakerIsNpc01;

    AAocietyNPCCharacter* Speaker = FindResidentNPC(this, SpeakerId);
    AAocietyNPCCharacter* Listener = FindResidentNPC(this, ListenerId);
    const FString ListenerName = GetResidentDisplayName(this, ListenerId);
    if (Speaker)
    {
        Speaker->ShowThinking();
    }
    if (Listener)
    {
        Listener->ShowListening(
            Speaker ? Speaker->DisplayName : GetResidentDisplayName(this, SpeakerId),
            12.0f);
    }
    if (Speaker && Listener)
    {
        Speaker->FocusOnActor(Listener, 12.0f);
        Listener->FocusOnActor(Speaker, 12.0f);
    }

    Client->RequestNPCDialogue(
        SpeakerId,
        FString::Printf(
            TEXT("你正在森林小镇里散步，并遇到了居民 %s。请结合当前环境和你自己的性格，对对方自然说一句简短的话，不要提到你是AI。"),
            *ListenerName),
        TEXT("forest_town"),
        TEXT("ambient_resident_chat"));
}
