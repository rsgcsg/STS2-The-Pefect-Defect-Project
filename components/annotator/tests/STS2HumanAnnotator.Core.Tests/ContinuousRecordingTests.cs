using STS2HumanAnnotator.Core;
using Xunit;

namespace STS2HumanAnnotator.Core.Tests;

public sealed class ContinuousRecordingTests
{
    [Theory]
    [InlineData(true, false, "victory")]
    [InlineData(false, false, "defeat")]
    [InlineData(false, true, "abandoned")]
    public void TerminalSealKeepsArmedAndNextRunStartsWithoutTransferredWitnesses(
        bool victory, bool abandoned, string outcome)
    {
        ContinuousRecording recording = new();
        recording.Arm();
        recording.BeginSession();
        recording.ObserveLaunch("run_started_native");
        Assert.True(recording.ObserveTerminal(victory, abandoned));
        Assert.False(recording.ObserveTerminal(victory, abandoned));
        recording.RequestSeal();
        Assert.Equal("sealing", recording.Snapshot().SealState);
        recording.MarkSealed();
        recording.MarkSealed();
        var first = recording.Snapshot();
        Assert.True(first.Armed);
        Assert.True(first.BoundaryComplete);
        Assert.Equal(outcome, first.Outcome);
        Assert.Equal(1, first.FinishedRuns);
        recording.BeginSession();
        Assert.False(recording.Snapshot().NativeStartObserved);
        Assert.False(recording.Snapshot().TerminalObserved);
        Assert.Equal(1, recording.Snapshot().SealedSegments);
    }

    [Fact]
    public void SavedRunAndPauseNeverBecomeCompleteFreshRuns()
    {
        ContinuousRecording recording = new();
        recording.Arm(); recording.BeginSession();
        recording.ObserveLaunch("run_resumed_native");
        recording.ObserveTerminal(false, false);
        Assert.False(recording.Snapshot().BoundaryComplete);
        recording.BeginSession(); recording.ObserveLaunch("run_started_native");
        recording.Pause();
        Assert.False(recording.Armed);
        recording.Arm(); recording.ObserveTerminal(true, false);
        Assert.False(recording.Snapshot().BoundaryComplete);
    }

    [Fact]
    public void ExitCanSealPartialContentWithoutInventingATerminal()
    {
        ContinuousRecording recording = new();
        recording.Arm(); recording.BeginSession();
        recording.ObserveLaunch("run_started_native");
        recording.Disarm(); recording.RequestSeal(); recording.MarkSealed();
        var status = recording.Snapshot();
        Assert.False(status.Armed);
        Assert.False(status.TerminalObserved);
        Assert.False(status.BoundaryComplete);
        Assert.Equal("unknown", status.Outcome);
        Assert.Equal(0, status.FinishedRuns);
        Assert.Equal(1, status.SealedSegments);
    }
}
