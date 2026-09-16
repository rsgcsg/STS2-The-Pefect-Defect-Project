using STS2HumanAnnotator.Core;

namespace STS2HumanAnnotator.Mod;

/// <summary>Optional in-process mutation precondition; not an evidence format.</summary>
public sealed record RecordingSessionExpectation(string? SessionId);

/// <summary>
/// Single typed application boundary for recording query, command and event views.
/// It changes recorder lifecycle only; it never owns or invokes STS2 actions.
/// </summary>
public sealed class RecordingApplicationService
{
    public static RecordingApplicationService Instance { get; } = new();

    private RecordingApplicationService()
    {
    }

    public RecordingApplicationStatus QueryStatus() => RecorderRuntime.GetRecordingApplicationStatus();

    public RecordingEventBatch QueryEvents(long afterSequence) =>
        RecorderRuntime.ReadRecordingEvents(afterSequence);

    public RecordingCommandResult Execute(RecordingCommand command) =>
        RecorderRuntime.ExecuteRecordingCommand(command);

    public RecordingCommandResult ExecuteForSession(RecordingCommand command, string? expectedSessionId) =>
        RecorderRuntime.ExecuteRecordingCommand(command, new RecordingSessionExpectation(expectedSessionId));
}
