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
#include "Engine/DirectionalLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/PointLight.h"
#include "Engine/SkyLight.h"
#include "Engine/GameInstance.h"
#include "EngineUtils.h"
#include "NiagaraComponent.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraSystem.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
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

    if (UWorld* World = GetWorld())
    {
        if (!World->GetAuthGameMode())
        {
            return;
        }
        AAocietyWorldBoundary* Boundary = nullptr;
        for (TActorIterator<AAocietyWorldBoundary> It(World); It; ++It)
        {
            Boundary = *It;
            break;
        }
        if (!Boundary)
        {
            Boundary = World->SpawnActor<AAocietyWorldBoundary>(
                AAocietyWorldBoundary::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator);
        }
        if (Boundary)
        {
            // Authored cabin diorama and plaza occupy this rectangle; the generous
            // margin prevents edge falls without clipping the town paths.
            Boundary->Configure(FVector2D(-4200.0f, -3600.0f), FVector2D(4200.0f, 4200.0f));
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
    FParse::Value(FCommandLine::Get(), TEXT("AocietyWeatherState="), WeatherState);
    WeatherState = FMath::Clamp(WeatherState, 0, 2);

    TArray<AActor*> Directionals;
    UGameplayStatics::GetAllActorsOfClass(World, ADirectionalLight::StaticClass(), Directionals);
    ADirectionalLight* FallbackSun = nullptr;
    for (AActor* Actor : Directionals)
    {
        if (ADirectionalLight* Candidate = Cast<ADirectionalLight>(Actor))
        {
            if (!FallbackSun)
            {
                FallbackSun = Candidate;
            }
            if (const UDirectionalLightComponent* Component = Cast<UDirectionalLightComponent>(
                    Candidate->GetLightComponent()); Component && Component->bAtmosphereSunLight)
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
                Candidate->GetLightComponent()->SetMobility(EComponentMobility::Movable);
            }
            else
            {
                Candidate->GetLightComponent()->SetVisibility(false);
            }
        }
    }

    TArray<AActor*> Skies;
    UGameplayStatics::GetAllActorsOfClass(World, ASkyLight::StaticClass(), Skies);
    if (Skies.Num() > 0)
    {
        SkyLight = Cast<ASkyLight>(Skies[0]);
        if (SkyLight.IsValid())
        {
            SkyLight->GetLightComponent()->SetMobility(EComponentMobility::Movable);
        }
    }

    TArray<AActor*> Fogs;
    UGameplayStatics::GetAllActorsOfClass(World, AExponentialHeightFog::StaticClass(), Fogs);
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
            if (!Component || !Component->IsA<UPointLightComponent>() && !Component->IsA<USpotLightComponent>())
            {
                continue;
            }
            NightLights.Add(Component);
            OriginalLightIntensities.Add(Component, Component->Intensity);
        }
    }
    if (NightLights.Num() == 0)
    {
        // The authored cabin pack uses emissive meshes rather than light actors.
        // Add a restrained set of warm, movable window/porch lights so the
        // dusk-to-night transition is visible in the playable demo.
        const FVector LightLocations[] = {
            FVector(-980.0f, -260.0f, 420.0f),
            FVector(720.0f, -180.0f, 420.0f),
            FVector(-760.0f, 1080.0f, 420.0f),
            FVector(1120.0f, 1120.0f, 420.0f),
            FVector(0.0f, 320.0f, 520.0f)};
        for (const FVector& Location : LightLocations)
        {
            if (APointLight* Actor = World->SpawnActor<APointLight>(
                    APointLight::StaticClass(), Location, FRotator::ZeroRotator))
            {
                UPointLightComponent* Component = Cast<UPointLightComponent>(
                    Actor->GetLightComponent());
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
    }

    if (UNiagaraSystem* RainSystem = LoadObject<UNiagaraSystem>(
            nullptr, TEXT("/DynamicSkySystem/Niagara/Rain/NS_Rain.NS_Rain")))
    {
        WeatherParticles = UNiagaraFunctionLibrary::SpawnSystemAtLocation(
            World, RainSystem, FVector::ZeroVector, FRotator::ZeroRotator,
            FVector::OneVector, false, false, ENCPoolMethod::None, true);
        if (WeatherParticles)
        {
            WeatherParticles->SetVisibility(false, true);
            WeatherParticles->SetComponentTickEnabled(false);
            WeatherParticles->SetAutoActivate(false);
        }
    }

    bWorldEnvironmentInitialized = true;
    UE_LOG(LogTemp, Display, TEXT("[AocietyEnvironment] initialized sun=%s skylight=%s fog=%s night_lights=%d"),
        *GetNameSafe(SunLight.Get()), *GetNameSafe(SkyLight.Get()), *GetNameSafe(HeightFog.Get()), NightLights.Num());
}

void AAocietyGameMode::UpdateWorldEnvironment(float DeltaSeconds)
{
    if (!bWorldEnvironmentInitialized)
    {
        return;
    }

    WorldClockMinutes = FMath::Fmod(
        WorldClockMinutes + DeltaSeconds * (1440.0f / WorldDayLengthSeconds), 1440.0f);
    if (WorldClockMinutes < 0.0f)
    {
        WorldClockMinutes += 1440.0f;
    }
    WeatherElapsedSeconds += DeltaSeconds;
    if (WeatherElapsedSeconds > 75.0f)
    {
        WeatherElapsedSeconds = 0.0f;
        WeatherState = (WeatherState + 1) % 3; // clear -> overcast -> rain
        UE_LOG(LogTemp, Display, TEXT("[AocietyEnvironment] weather=%s"),
            WeatherState == 0 ? TEXT("clear") : WeatherState == 1 ? TEXT("overcast") : TEXT("rain"));
    }

    const float WeatherLightScale = WeatherState == 0
        ? 1.0f : WeatherState == 1 ? 0.72f : 0.48f;
    const float SunAngle = (WorldClockMinutes / 1440.0f) * 360.0f - 90.0f;
    const float SolarElevation = FMath::Sin(FMath::DegreesToRadians(SunAngle));
    const bool bNight = SolarElevation < -0.08f;
    const float DayBlend = FMath::Clamp((SolarElevation + 0.12f) / 0.45f, 0.0f, 1.0f);

    if (SunLight.IsValid())
    {
        // UE directional lights point along local -X; a negative pitch puts the
        // morning/noon sun toward the authored ground instead of above the sky.
        SunLight->SetActorRotation(FRotator(-SunAngle, -35.0f, 0.0f));
        if (UDirectionalLightComponent* Light = Cast<UDirectionalLightComponent>(
                SunLight->GetLightComponent()))
        {
            Light->SetIntensity(
                FMath::Lerp(0.35f, 4.2f, DayBlend) * WeatherLightScale);
            const FLinearColor DayColor = WeatherState == 0
                ? FLinearColor(1.0f, 0.88f, 0.68f)
                : FLinearColor(0.72f, 0.76f, 0.82f);
            Light->SetLightColor(FLinearColor::LerpUsingHSV(
                FLinearColor(0.18f, 0.24f, 0.42f), DayColor, DayBlend));
        }
    }
    if (SkyLight.IsValid())
    {
        USkyLightComponent* Light = SkyLight->GetLightComponent();
        Light->SetIntensity(
            FMath::Lerp(0.62f, 1.0f, DayBlend) * FMath::Lerp(0.9f, 1.0f, WeatherLightScale));
        Light->SetLightColor(WeatherState == 0
            ? FLinearColor::White
            : FLinearColor(0.62f, 0.68f, 0.76f));
        if (FMath::IsNearlyEqual(FMath::Fmod(WorldClockMinutes, 30.0f), 0.0f, 0.2f))
        {
            Light->RecaptureSky();
        }
    }

    if (HeightFog.IsValid())
    {
        UExponentialHeightFogComponent* Fog = HeightFog->GetComponent();
        const float WeatherFog = WeatherState == 0 ? 0.0008f : WeatherState == 1 ? 0.0022f : 0.0045f;
        Fog->FogDensity = FMath::Lerp(WeatherFog, WeatherFog * 1.35f, bNight ? 1.0f : 0.0f);
        Fog->FogHeightFalloff = 0.18f;
        Fog->SetFogInscatteringColor(bNight
            ? FLinearColor(0.025f, 0.04f, 0.10f)
            : FLinearColor(0.72f, 0.82f, 1.0f));
    }
    const bool bRain = WeatherState == 2;
    if (WeatherParticles)
    {
        if (APawn* Player = UGameplayStatics::GetPlayerPawn(this, 0))
        {
            WeatherParticles->SetWorldLocation(
                Player->GetActorLocation() + FVector(0.0f, 0.0f, 1200.0f));
        }
        if (bRain && !WeatherParticles->IsActive())
        {
            WeatherParticles->Activate(true);
        }
        else if (!bRain && WeatherParticles->IsActive())
        {
            WeatherParticles->DeactivateImmediate();
        }
        WeatherParticles->SetVisibility(bRain, true);
        WeatherParticles->SetComponentTickEnabled(bRain);
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
