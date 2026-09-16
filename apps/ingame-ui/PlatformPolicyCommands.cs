using System;
using System.Threading;
using System.Threading.Tasks;

namespace STS2PlatformLiveUi;

public enum PlatformPolicyCommand
{
    Human,
    Shadow,
    OneStep,
    Auto,
    Stop,
    Tick
}

/// <summary>An older UI intent completed after another command superseded it.</summary>
public sealed class PlatformPolicyCommandSupersededException : OperationCanceledException
{
    public PlatformPolicyCommandSupersededException()
        : base("A newer Policy Runtime command superseded this intent.") { }
}

/// <summary>
/// Orders typed Runtime mutations, not gameplay. A recovery intent immediately
/// invalidates earlier preparation and follow-up Tick work. Recovery bypasses
/// the local wait so Runtime's owner can fence queued/in-flight model intent.
/// No failed or unknown request is retried here.
/// </summary>
public sealed class PlatformPolicyCommands
{
    private readonly SemaphoreSlim _mutations = new(1, 1);
    private long _generation;
    private readonly object _unknownGate = new();
    private readonly Dictionary<string, long> _unknownRuns = new(StringComparer.Ordinal);
    private readonly Dictionary<string, long> _recoveredRuns = new(StringComparer.Ordinal);

    public bool HasUnknownCommand(string? runId)
    {
        lock (_unknownGate) return runId != null && _unknownRuns.ContainsKey(runId);
    }

    private void EnsureAllowed(string runId, bool recovery)
    {
        if (!recovery && HasUnknownCommand(runId)) throw new PlatformPolicyRecoveryRequiredException();
    }

    /// <summary>
    /// The latest deliberate command wins. Prepare closes Human recording through
    /// its existing owner and must fail if pending/unknown. Human and Stop bypass
    /// preparation. Delegates retain exact Runtime identity and transport fences.
    /// Ignore PlatformPolicyCommandSupersededException in UI result presentation.
    /// </summary>
    public async Task<T> RunAsync<T>(
        string expectedRunId,
        PlatformPolicyCommand command,
        Func<Task> prepareModel,
        Func<string, Task<T>> setMode,
        Func<Task<T>> tick,
        Func<Task<T>> stop,
        CancellationToken cancellationToken = default)
    {
        if (!Enum.IsDefined(command))
            throw new ArgumentOutOfRangeException(nameof(command));
        ArgumentNullException.ThrowIfNull(prepareModel);
        ArgumentNullException.ThrowIfNull(setMode);
        ArgumentNullException.ThrowIfNull(tick);
        ArgumentNullException.ThrowIfNull(stop);
        ArgumentException.ThrowIfNullOrWhiteSpace(expectedRunId);
        cancellationToken.ThrowIfCancellationRequested();
        bool recovery = command is PlatformPolicyCommand.Human or PlatformPolicyCommand.Stop;
        EnsureAllowed(expectedRunId, recovery);
        long intent = Interlocked.Increment(ref _generation);

        if (command is PlatformPolicyCommand.Shadow or PlatformPolicyCommand.OneStep or PlatformPolicyCommand.Auto or PlatformPolicyCommand.Tick)
        {
            EnsureCurrent(intent, cancellationToken);
            await prepareModel().ConfigureAwait(false);
            EnsureCurrent(intent, cancellationToken);
        }
        if (command == PlatformPolicyCommand.Tick)
            return await SendAsync(intent, expectedRunId, recovery, tick, cancellationToken).ConfigureAwait(false);
        if (command == PlatformPolicyCommand.Stop)
            return await SendAsync(intent, expectedRunId, recovery, stop, cancellationToken).ConfigureAwait(false);

        string mode = command switch {
            PlatformPolicyCommand.Human => "human",
            PlatformPolicyCommand.Shadow => "shadow",
            PlatformPolicyCommand.OneStep => "one_step",
            PlatformPolicyCommand.Auto => "auto",
            _ => throw new ArgumentOutOfRangeException(nameof(command))
        };
        T result = await SendAsync(intent, expectedRunId, recovery, () => setMode(mode), cancellationToken).ConfigureAwait(false);
        return command == PlatformPolicyCommand.OneStep
            ? await SendAsync(intent, expectedRunId, recovery, tick, cancellationToken).ConfigureAwait(false)
            : result;
    }

    /// <summary>
    /// Invalidate queued/preparing work during UI teardown. This does not claim to
    /// stop an already submitted effect; use an explicit Stop for that operation.
    /// </summary>
    public void InvalidatePending() => Interlocked.Increment(ref _generation);

    private async Task<T> SendAsync<T>(long intent, string runId, bool recovery, Func<Task<T>> mutation, CancellationToken cancellationToken)
    {
        // Runtime serializes effects and advances recovery_epoch on Human/Stop
        // entry. Waiting behind a model HTTP response here would delay that fence.
        if (!recovery) await _mutations.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            EnsureCurrent(intent, cancellationToken);
            EnsureAllowed(runId, recovery);
            T result;
            try { result = await mutation().ConfigureAwait(false); }
            catch (PlatformPolicyCommandUnknownException)
            {
                lock (_unknownGate)
                {
                    // A late failure of old intent cannot undo confirmed recovery.
                    if (!_recoveredRuns.TryGetValue(runId, out long recovered) || intent > recovered)
                        _unknownRuns[runId] = Math.Max(intent, _unknownRuns.GetValueOrDefault(runId));
                }
                throw;
            }
            if (recovery)
            {
                lock (_unknownGate)
                {
                    _recoveredRuns[runId] = Math.Max(intent, _recoveredRuns.GetValueOrDefault(runId));
                    if (_unknownRuns.TryGetValue(runId, out long unknown) && unknown <= intent)
                        _unknownRuns.Remove(runId);
                }
            }
            EnsureCurrent(intent, cancellationToken);
            return result;
        }
        finally
        {
            if (!recovery) _mutations.Release();
        }
    }

    private void EnsureCurrent(long intent, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (intent != Interlocked.Read(ref _generation))
            throw new PlatformPolicyCommandSupersededException();
    }
}
