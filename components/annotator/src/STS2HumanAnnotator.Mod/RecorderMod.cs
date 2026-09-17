using System.Reflection;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Modding;
using STS2HumanAnnotator.Core;

namespace STS2HumanAnnotator.Mod;

#if !STS2_PLATFORM_UNIFIED
[ModInitializer("Initialize")]
#endif
public static class RecorderMod
{
    public const string Version = CurrentRecordingContract.ProductVersion;

    public static void Initialize()
    {
        try
        {
            string modDirectory = Path.GetDirectoryName(
                Assembly.GetExecutingAssembly().Location)
                ?? throw new InvalidOperationException("Annotator assembly directory is unavailable.");
            AnnotatorConfiguration configuration = AnnotatorConfiguration.Load(modDirectory);
            RecorderRuntime.Initialize(configuration);
            new Harmony("rsgcsg.sts2-human-annotator").PatchAll(typeof(RecorderMod).Assembly);
            var tree = (SceneTree)Engine.GetMainLoop();
            tree.Connect(
                SceneTree.SignalName.ProcessFrame,
                Callable.From(RecorderRuntime.OnProcessFrame));
            tree.Root.Connect(Node.SignalName.TreeExiting,
                Callable.From(RecorderRuntime.ObserveGameExiting));
            GD.Print(
                $"[STS2 Human Annotator] v{Version} observer ready; no recording session is open.");
        }
        catch (Exception exception)
        {
            GD.PrintErr($"[STS2 Human Annotator] initialization failed: {exception}");
        }
    }
}
