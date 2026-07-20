// Copyright Aociety. 保留所有权利.

#include "AocietyGameInstance.h"
#include "AocietyClientSubsystem.h"
#include "Dom/JsonObject.h"
#include "HAL/PlatformMisc.h"
#include "Misc/CommandLine.h"
#include "Misc/DateTime.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
bool ReadRequiredString(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, FString& OutValue)
{
    return Object.IsValid() && Object->TryGetStringField(Field, OutValue) && !OutValue.IsEmpty();
}
}

bool UAocietyGameInstance::LoadLauncherSession()
{
    FString SessionFile;
    FString ContractVersion;
    FString CommandLineLaunchId;
    const TCHAR* CommandLine = FCommandLine::Get();

    if (!FParse::Value(CommandLine, TEXT("LauncherSessionFile="), SessionFile) ||
        !FParse::Value(CommandLine, TEXT("LauncherContractVersion="), ContractVersion) ||
        !FParse::Value(CommandLine, TEXT("LauncherLaunchId="), CommandLineLaunchId))
    {
        LauncherSessionError = TEXT("NoLauncherArguments");
        return false;
    }

    if (ContractVersion != TEXT("1.0"))
    {
        LauncherSessionError = TEXT("UnsupportedContractVersion");
        return false;
    }

    FString JsonText;
    if (!FFileHelper::LoadFileToString(JsonText, *SessionFile))
    {
        LauncherSessionError = TEXT("SessionFileUnreadable");
        return false;
    }

    TSharedPtr<FJsonObject> Root;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonText);
    if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
    {
        LauncherSessionError = TEXT("SessionJsonInvalid");
        return false;
    }

    FString FileContractVersion;
    FString FileLaunchId;
    FString ExpiresAtText;
    if (!ReadRequiredString(Root, TEXT("contractVersion"), FileContractVersion) ||
        !ReadRequiredString(Root, TEXT("launchId"), FileLaunchId) ||
        !ReadRequiredString(Root, TEXT("expiresAt"), ExpiresAtText))
    {
        LauncherSessionError = TEXT("SessionMissingRequiredFields");
        return false;
    }

    if (FileContractVersion != ContractVersion || FileLaunchId != CommandLineLaunchId)
    {
        LauncherSessionError = TEXT("SessionArgumentMismatch");
        return false;
    }

    FDateTime ExpiresAt;
    if (!FDateTime::ParseIso8601(*ExpiresAtText, ExpiresAt) || ExpiresAt <= FDateTime::UtcNow())
    {
        LauncherSessionError = TEXT("SessionExpired");
        return false;
    }

    const TSharedPtr<FJsonObject>* Account = nullptr;
    const TSharedPtr<FJsonObject>* Agent = nullptr;
    if (!Root->TryGetObjectField(TEXT("account"), Account) || !Account ||
        !Root->TryGetObjectField(TEXT("agent"), Agent) || !Agent ||
        !ReadRequiredString(*Account, TEXT("accountId"), LauncherAccountId) ||
        !ReadRequiredString(*Account, TEXT("displayName"), LauncherDisplayName) ||
        !ReadRequiredString(*Agent, TEXT("agentId"), LauncherAgentId) ||
        !ReadRequiredString(*Agent, TEXT("baseModelId"), LauncherBaseModelId))
    {
        LauncherSessionError = TEXT("SessionIdentityInvalid");
        return false;
    }

    LauncherLaunchId = FileLaunchId;
    LauncherSessionError.Empty();
    bLauncherSessionValid = true;
    UE_LOG(LogTemp, Log, TEXT("[AocietyGame] Launcher session accepted: launch=%s account=%s agent=%s"),
        *LauncherLaunchId, *LauncherAccountId, *LauncherAgentId);
    return true;
}

void UAocietyGameInstance::Init()
{
    Super::Init();

    UE_LOG(LogTemp, Log, TEXT("[AocietyGame] Init"));

    if (!LoadLauncherSession())
    {
        UE_LOG(LogTemp, Warning, TEXT("[AocietyGame] Launcher session unavailable: %s"), *LauncherSessionError);
#if UE_BUILD_SHIPPING
        FPlatformMisc::RequestExit(false);
        return;
#endif
    }

    if (UAocietyClientSubsystem* Client = GetSubsystem<UAocietyClientSubsystem>())
    {
        Client->BackendURL = BackendURL;
        Client->CareBackendURL = CareBackendURL;
        if (bAutoStartCapture)
        {
            Client->Connect();
        }
    }
}

void UAocietyGameInstance::Shutdown()
{
    if (UAocietyClientSubsystem* Client = GetSubsystem<UAocietyClientSubsystem>())
    {
        Client->Disconnect();
    }
    Super::Shutdown();
}
