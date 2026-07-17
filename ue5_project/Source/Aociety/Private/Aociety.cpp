// Copyright Aociety. 保留所有权利.

#include "Aociety.h"

#define LOCTEXT_NAMESPACE "FAocietyModule"

void FAocietyModule::StartupModule()
{
    UE_LOG(LogTemp, Log, TEXT("Aociety module starting"));
}

void FAocietyModule::ShutdownModule()
{
    UE_LOG(LogTemp, Log, TEXT("Aociety module shutting down"));
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_PRIMARY_GAME_MODULE(FAocietyModule, Aociety, "Aociety")
