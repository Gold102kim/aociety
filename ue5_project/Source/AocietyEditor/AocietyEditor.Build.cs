using UnrealBuildTool;

public class AocietyEditor : ModuleRules
{
    public AocietyEditor(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PrivateDependencyModuleNames.AddRange(new[]
        {
            "Core",
            "CoreUObject",
            "Engine",
            "UnrealEd",
            "Slate",
            "SlateCore",
            "AssetRegistry",
            "Aociety",
            "PoseSearch",
            "PoseSearchEditor",
            "Chooser",
            "IKRig",
            "IKRigEditor",
            "StructUtils",
            "AnimationDataController"
        });
    }
}
