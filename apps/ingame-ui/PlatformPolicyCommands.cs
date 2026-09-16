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
    Stop
}

/// <summary>An older UI intent completed after another command superseded it.</summary>
public sealed class PlatformPolicyCommandSupersededException : OperationCanceledException
{
    public PlatformPolicyCommandSupersededException()
        : base("A newer Policy Runtime command superseded this intent.") { }
}

/// <summary>
/// Orders typed Runtime mutations, not gameplay. A recovery intent immediately
/// invalidates earlier preparation and follow-up Tick work; its mutation follows
/// any request already submitted. No failed or unknown request is retried here.
/// </summary>
public sealed class PlatformPolicyCommands
{
    private readonly SemaphoreSlim _mutations = new(1, 1);
    private long _generation;

    /// <summary>
    /// The latest deliberate command wins. Prepare closes Human recording through
    /// its existing owner and must fail if pending/unknown. Human and Stop bypass
    /// preparation. Delegates retain exact Runtime identity and transport fences.
    /// Ignore PlatformPolicyCommandSupersededException in UI result presentation.
    /// </summary>
    public async Task<T> RunAsync<T>(
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
        cancellationToken.ThrowIfCancellationRequested();
        long intent = Interlocked.Increment(ref _generation);

        if (command is PlatformPolicyCommand.Shadow or PlatformPolicyCommand.OneStep or PlatformPolicyCommand.Auto)
        {
            EnsureCurrent(intent, cancellationToken);
            await prepareModel().ConfigureAwait(false);
            EnsureCurrent(intent, cancellationToken);
        }
        if (command == PlatformPolicyCommand.Stop)
            return await SendAsync(intent, stop, cancellationToken).ConfigureAwait(false);

        string mode = command switch {
            PlatformPolicyCommand.Human => "human",
            PlatformPolicyCommand.Shadow => "shadow",
            PlatformPolicyCommand.OneStep => "one_step",
            PlatformPolicyCommand.Auto => "auto",
            _ => throw new ArgumentOutOfRangeException(nameof(command))
        };
        T result = await SendAsync(intent, () => setMode(mode), cancellationToken).ConfigureAwait(false);
        return command == PlatformPolicyCommand.OneStep
            ? await SendAsync(intent, tick, cancellationToken).ConfigureAwait(false)
            : result;
    }

    /// <summary>
    /// Invalidate queued/preparing work during UI teardown. This does not claim to
    /// stop an already submitted effect; use an explicit Stop for that operation.
    /// </summary>
    public void InvalidatePending() => Interlocked.Increment(ref _generation);

    private async Task<T> SendAsync<T>(long intent, Func<Task<T>> mutation, CancellationToken cancellationToken)
    {
        await _mutations.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            EnsureCurrent(intent, cancellationToken);
            T result = await mutation().ConfigureAwait(false);
            EnsureCurrent(intent, cancellationToken);
            return result;
        }
        finally
        {
            _mutations.Release();
        }
    }

    private void EnsureCurrent(long intent, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (intent != Interlocked.Read(ref _generation))
            throw new PlatformPolicyCommandSupersededException();
    }
}
