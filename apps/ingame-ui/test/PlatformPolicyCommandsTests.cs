using System.Collections.Concurrent;
using STS2PlatformLiveUi;
using Xunit;

namespace STS2PlatformLiveUiTests;

public sealed class PlatformPolicyCommandsTests
{
    private static TaskCompletionSource<bool> Signal() =>
        new(TaskCreationOptions.RunContinuationsAsynchronously);

    [Fact]
    public void GameBindingRejectsOtherRuntimeOtherGameAndAbsentEpoch()
    {
        var binding = new PlatformPolicyBinding("sts2.policy-runtime/environment-1", "run-a", "game-a", 0);
        binding.Validate("run-a", "game-a");
        Assert.Throws<InvalidOperationException>(() => binding.Validate("run-b", "game-a"));
        Assert.Throws<InvalidOperationException>(() => binding.Validate("run-a", "game-b"));
        Assert.Throws<InvalidOperationException>(() => (binding with { RecoveryEpoch = null }).Validate("run-a", "game-a"));
        Assert.Throws<InvalidOperationException>(() => (binding with { RecoveryEpoch = -1 }).Validate("run-a", "game-a"));
    }

    [Fact]
    public async Task OneStepModePendingThenHumanNeverSendsLateTick()
    {
        var commands = new PlatformPolicyCommands();
        var entered = Signal();
        var release = Signal();
        var calls = new ConcurrentQueue<string>();
        async Task<string> Mode(string mode)
        {
            calls.Enqueue(mode);
            if (mode == "one_step")
            {
                entered.SetResult(true);
                await release.Task;
            }
            return mode;
        }
        Task<string> Tick() { calls.Enqueue("tick"); return Task.FromResult("tick"); }
        Task<string> Stop() { calls.Enqueue("stop"); return Task.FromResult("stop"); }
        Task<string> previous = commands.RunAsync("run-a", PlatformPolicyCommand.OneStep,
            () => Task.CompletedTask, Mode, Tick, Stop);
        await entered.Task.WaitAsync(TimeSpan.FromSeconds(3));
        Task<string> human = commands.RunAsync("run-a", PlatformPolicyCommand.Human,
            () => throw new InvalidOperationException("Human must bypass preparation"), Mode, Tick, Stop);
        Assert.Equal("human", await human.WaitAsync(TimeSpan.FromSeconds(3)));
        Assert.Equal(new[] { "one_step", "human" }, calls.ToArray());
        release.SetResult(true);
        await Assert.ThrowsAsync<PlatformPolicyCommandSupersededException>(() => previous);
        Assert.Equal("human", await human.WaitAsync(TimeSpan.FromSeconds(3)));
        Assert.Equal(new[] { "one_step", "human" }, calls.ToArray());
    }

    [Theory]
    [InlineData(PlatformPolicyCommand.Auto)]
    [InlineData(PlatformPolicyCommand.OneStep)]
    [InlineData(PlatformPolicyCommand.Shadow)]
    [InlineData(PlatformPolicyCommand.Tick)]
    public async Task HumanOvertakesPendingPreparationAndOldCommandNeverSendsMode(PlatformPolicyCommand action)
    {
        var commands = new PlatformPolicyCommands();
        var entered = Signal();
        var release = Signal();
        var calls = new ConcurrentQueue<string>();
        async Task Prepare() { entered.SetResult(true); await release.Task; }
        Task<string> Mode(string mode) { calls.Enqueue(mode); return Task.FromResult(mode); }
        Task<string> Tick() { calls.Enqueue("tick"); return Task.FromResult("tick"); }
        Task<string> Stop() { calls.Enqueue("stop"); return Task.FromResult("stop"); }
        Task<string> previous = commands.RunAsync("run-a", action, Prepare, Mode, Tick, Stop);
        await entered.Task.WaitAsync(TimeSpan.FromSeconds(3));
        string result = await commands.RunAsync("run-a", PlatformPolicyCommand.Human,
            () => throw new InvalidOperationException(), Mode, Tick, Stop).WaitAsync(TimeSpan.FromSeconds(3));
        Assert.Equal("human", result);
        release.SetResult(true);
        await Assert.ThrowsAsync<PlatformPolicyCommandSupersededException>(() => previous);
        Assert.Equal(new[] { "human" }, calls.ToArray());
    }

    [Fact]
    public async Task RecoveryBypassesPendingModelResponseAndItsLateUnknownDoesNotRelock()
    {
        var commands = new PlatformPolicyCommands();
        var entered = Signal();
        var release = Signal();
        var calls = new ConcurrentQueue<string>();
        var unknown = new PlatformPolicyCommandUnknownException(new IOException("synthetic lost response; outcome unknown"));
        async Task<string> Mode(string mode)
        {
            calls.Enqueue(mode);
            entered.SetResult(true);
            await release.Task;
            throw unknown;
        }
        Task<string> Tick() { calls.Enqueue("tick"); return Task.FromResult("tick"); }
        Task<string> Stop() { calls.Enqueue("stop"); return Task.FromResult("stop"); }
        Task<string> previous = commands.RunAsync("run-a", PlatformPolicyCommand.Auto,
            () => Task.CompletedTask, Mode, Tick, Stop);
        await entered.Task.WaitAsync(TimeSpan.FromSeconds(3));
        Task<string> recovery = commands.RunAsync("run-a", PlatformPolicyCommand.Stop,
            () => throw new InvalidOperationException(), Mode, Tick, Stop);
        Assert.Equal("stop", await recovery.WaitAsync(TimeSpan.FromSeconds(3)));
        Assert.Equal(new[] { "auto", "stop" }, calls.ToArray());
        release.SetResult(true);
        Assert.Same(unknown, await Assert.ThrowsAsync<PlatformPolicyCommandUnknownException>(() => previous));
        Assert.Equal(new[] { "auto", "stop" }, calls.ToArray());
        Assert.False(commands.HasUnknownCommand("run-a"));
    }

    [Fact]
    public async Task FailedPreparationDoesNotSendAnyMutation()
    {
        var commands = new PlatformPolicyCommands();
        var pending = new InvalidOperationException("recording Close pending");
        int effects = 0;
        Task<string> Mutation() { effects++; return Task.FromResult("unexpected"); }
        Assert.Same(pending, await Assert.ThrowsAsync<InvalidOperationException>(() => commands.RunAsync("run-a",
            PlatformPolicyCommand.Auto, () => throw pending, _ => Mutation(), Mutation, Mutation)));
        Assert.Equal(0, effects);
    }

    [Fact]
    public async Task OneStepWithoutRecoveryUsesExactlyOneModeAndOneTick()
    {
        var commands = new PlatformPolicyCommands();
        var calls = new List<string>();
        Task Prepare() { calls.Add("prepare"); return Task.CompletedTask; }
        Task<string> Mode(string mode) { calls.Add(mode); return Task.FromResult(mode); }
        Task<string> Tick() { calls.Add("tick"); return Task.FromResult("receipt"); }
        Assert.Equal("receipt", await commands.RunAsync("run-a", PlatformPolicyCommand.OneStep,
            Prepare, Mode, Tick, () => throw new InvalidOperationException()));
        Assert.Equal(new[] { "prepare", "one_step", "tick" }, calls);
    }

    [Fact]
    public async Task TeardownInvalidatesLatePreparationWithoutClaimingStop()
    {
        var commands = new PlatformPolicyCommands();
        var release = Signal();
        int effects = 0;
        Task<string> Mutation() { effects++; return Task.FromResult("unexpected"); }
        Task<string> previous = commands.RunAsync("run-a", PlatformPolicyCommand.Auto,
            () => release.Task, _ => Mutation(), Mutation, Mutation);
        commands.InvalidatePending();
        release.SetResult(true);
        await Assert.ThrowsAsync<PlatformPolicyCommandSupersededException>(() => previous);
        Assert.Equal(0, effects);
    }
    [Theory]
    [InlineData(PlatformPolicyCommand.Auto)]
    [InlineData(PlatformPolicyCommand.OneStep)]
    public async Task UnknownModeOrTickRemainsBlockedAcrossSuccessfulStatusUntilRecovery(PlatformPolicyCommand first)
    {
        var commands = new PlatformPolicyCommands();
        int attempts = 0;
        Task<string> Unknown() { attempts++; throw new PlatformPolicyCommandUnknownException(new IOException("lost response")); }
        Task<string> Known() { attempts++; return Task.FromResult("confirmed"); }
        await Assert.ThrowsAsync<PlatformPolicyCommandUnknownException>(() => commands.RunAsync("run-a", first,
            () => Task.CompletedTask, _ => first == PlatformPolicyCommand.OneStep ? Known() : Unknown(),
            Unknown, Known));
        Assert.True(commands.HasUnknownCommand("run-a"));
        Assert.False(commands.HasUnknownCommand("other-run"));
        int priorAttempts = attempts;
        // A fresh successful status is observation only; the same coordinator and run remain fenced.
        await Task.CompletedTask;
        foreach (var action in new[] { PlatformPolicyCommand.Auto, PlatformPolicyCommand.OneStep, PlatformPolicyCommand.Tick, PlatformPolicyCommand.Shadow })
            await Assert.ThrowsAsync<PlatformPolicyRecoveryRequiredException>(() => commands.RunAsync("run-a", action,
                () => throw new Exception("must not prepare"), _ => Known(), Known, Known));
        Assert.Equal(priorAttempts, attempts);
        Assert.Equal("confirmed", await commands.RunAsync("run-a", PlatformPolicyCommand.Human,
            () => throw new Exception("recovery bypasses preparation"), _ => Known(), Known, Known));
        Assert.False(commands.HasUnknownCommand("run-a"));
        await commands.RunAsync("run-a", PlatformPolicyCommand.OneStep, () => Task.CompletedTask, _ => Known(), Known, Known);
        Assert.Equal(priorAttempts + 3, attempts);
    }

    [Fact]
    public async Task FailedRecoveryKeepsLatchAndKnownRejectionDoesNotCreateOne()
    {
        var commands = new PlatformPolicyCommands();
        Task<string> Unknown() => throw new PlatformPolicyCommandUnknownException(new TaskCanceledException());
        Task<string> Rejected() => throw new PlatformPolicyCommandRejectedException("runtime_recovery_epoch_mismatch");
        Task<string> Known() => Task.FromResult("known");
        await Assert.ThrowsAsync<PlatformPolicyCommandRejectedException>(() => commands.RunAsync("run-a", PlatformPolicyCommand.Auto,
            () => Task.CompletedTask, _ => Rejected(), Rejected, Rejected));
        Assert.False(commands.HasUnknownCommand("run-a"));
        await Assert.ThrowsAsync<PlatformPolicyCommandUnknownException>(() => commands.RunAsync("run-a", PlatformPolicyCommand.Auto,
            () => Task.CompletedTask, _ => Unknown(), Unknown, Unknown));
        await Assert.ThrowsAsync<PlatformPolicyCommandUnknownException>(() => commands.RunAsync("run-a", PlatformPolicyCommand.Human,
            () => Task.CompletedTask, _ => Unknown(), Unknown, Unknown));
        Assert.True(commands.HasUnknownCommand("run-a"));
        await commands.RunAsync("run-b", PlatformPolicyCommand.Auto, () => Task.CompletedTask, _ => Known(), Known, Known);
        Assert.True(commands.HasUnknownCommand("run-a"));
        await commands.RunAsync("run-a", PlatformPolicyCommand.Stop, () => Task.CompletedTask, _ => Known(), Known, Known);
        Assert.False(commands.HasUnknownCommand("run-a"));
    }

}
