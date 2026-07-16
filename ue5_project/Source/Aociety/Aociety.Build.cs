using UnrealBuildTool;

public class Aociety : ModuleRules
{
    public Aociety(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new[]
        {
            "Core",
            "CoreUObject",
            "Engine",
            "InputCore",
            "HTTP",
            "Json",
            "JsonUtilities",
            "WebSockets",
            "Sockets",
            "Networking",
            "RHI",
            "RenderCore",
            "ImageWrapper",
            "AudioCaptureCore",
            "AudioMixer",
            "SignalProcessing",
            "UMG",
            "Slate",
            "SlateCore",
            "OpenCV",
            "OpenCVHelper"
        });

    }
}
