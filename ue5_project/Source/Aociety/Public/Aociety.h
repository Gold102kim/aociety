// Copyright Aociety. 保留所有权利.

#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

class FAocietyModule : public IModuleInterface
{
public:
    virtual void StartupModule() override;
    virtual void ShutdownModule() override;
};
