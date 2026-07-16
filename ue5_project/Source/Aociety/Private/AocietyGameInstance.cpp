// Copyright Aociety. 保留所有权利.

#include "AocietyGameInstance.h"
#include "AocietyClientSubsystem.h"

void UAocietyGameInstance::Init()
{
    Super::Init();

    UE_LOG(LogTemp, Log, TEXT("[AocietyGame] Init"));

    if (UAocietyClientSubsystem* Client = GetSubsystem<UAocietyClientSubsystem>())
    {
        Client->BackendURL = BackendURL;
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
