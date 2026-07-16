using UnrealBuildTool;

public class AocietyEditorTarget : TargetRules
{
    public AocietyEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("Aociety");
    }
}
