using STS2HumanAnnotator.Core;
using STS2PlatformLiveUi;
using Xunit;

namespace STS2PlatformLiveUiTests;

public sealed class PlatformCollectionHandoffTests
{
    private static RecordingApplicationStatus Status(RecordingLifecycleState state, string closeout = "idle", string? session = "recording-a") =>
        new(RecordingApplicationContract.StatusSchema, DateTimeOffset.UtcNow, 1,
            new(state, session, DateTimeOffset.UtcNow, "test"), null, new(0, 0, 0, 0),
            null, null, null, null!, null!, new(closeout, null, null, null),
            "ready", "test", null, null, Array.Empty<string>(), 0);

    [Theory]
    [InlineData(RecordingLifecycleState.Recording)]
    [InlineData(RecordingLifecycleState.Paused)]
    public void HandoffWaitsForActualDurableClose(RecordingLifecycleState initial)
    {
        var current = Status(initial);
        int commands = 0;
        var result = PlatformCollectionHandoff.Prepare("recording-a", "one-command", () => current, (command, expected) =>
        {
            commands++;
            Assert.Equal(RecordingCommandKind.Close, command.Kind);
            Assert.Equal("one-command", command.CommandId);
            current = Status(RecordingLifecycleState.Closing, "closing");
            return new(true, true, "closing", "waiting for owner", current.Lifecycle);
        });
        Assert.False(PlatformCollectionHandoff.Ready(result));
        PlatformCollectionHandoff.Prepare("recording-a", "another-command", () => current, (_, _) => throw new Exception("must not repeat close"));
        Assert.Equal(1, commands);
        current = Status(RecordingLifecycleState.Closed, "closed");
        Assert.True(PlatformCollectionHandoff.Ready(PlatformCollectionHandoff.Prepare("recording-a", "later", () => current, (_, _) => throw new Exception())));
    }

    [Fact]
    public void SessionChangeCannotCloseAReplacementRecording()
    {
        Assert.Throws<InvalidOperationException>(() => PlatformCollectionHandoff.Prepare(
            "old", "command", () => Status(RecordingLifecycleState.Recording), (_, _) => throw new Exception("must not mutate")));
    }

    [Fact]
    public void RejectionAndIncompleteCloseDoNotGrantModelReadiness()
    {
        var current = Status(RecordingLifecycleState.Recording);
        Assert.Throws<InvalidOperationException>(() => PlatformCollectionHandoff.Prepare("recording-a", "command", () => current,
            (_, _) => new(false, false, "disk_failed", "failed", current.Lifecycle)));
        Assert.False(PlatformCollectionHandoff.Ready(Status(RecordingLifecycleState.Closed, "closing")));
        Assert.True(PlatformCollectionHandoff.Ready(Status(RecordingLifecycleState.Ready, session: null)));
    }
}
