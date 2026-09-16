using System.Collections.Concurrent;
using STS2PlatformLiveUi;
using Xunit;

namespace STS2PlatformLiveUiTests;

public sealed class PlatformPolicyCommandsTests
{
    private static TaskCompletionSource<bool> Signal() =>
        new(TaskCreationOptions.RunContinuationsAsynchronously);

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
        Task<string> previous = commands.RunAsync(PlatformPolicyCommand.OneStep,
            () => Task.CompletedTask, Mode, Tick, Stop);
        await entered.Task.WaitAsync(TimeSpan.FromSeconds(3));
        Task<string> human = commands.RunAsync(PlatformPolicyCommand.Human,
            () => throw new InvalidOperationException("Human must bypass preparation"), Mode, Tick, Stop);
        Assert.Equal(new[] { "one_step" }, calls.ToArray());
        release.SetResult(true);
        await Assert.ThrowsAsync<PlatformPolicyCommandSupersededException>(() => previous);
        Assert.Equal("human", await human.WaitAsync(TimeSpan.FromSeconds(3)));
        Assert.Equal(new[] { "one_step", "human" }, calls.ToArray());
    }

    [Theory]
    [InlineData(PlatformPolicyCommand.Auto)]
    [InlineData(PlatformPolicyCommand.OneStep)]
    [InlineData(PlatformPolicyCommand.Shadow)]
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
        Task<string> previous = commands.RunAsync(action, Prepare, Mode, Tick, Stop);
        await entered.Task.WaitAsync(TimeSpan.FromSeconds(3));
        string result = await commands.RunAsync(PlatformPolicyCommand.Human,
            () => throw new InvalidOperationException(), Mode, Tick, Stop).WaitAsync(TimeSpan.FromSeconds(3));
        Assert.Equal("human", result);
        release.SetResult(true);
        await Assert.ThrowsAsync<PlatformPolicyCommandSupersededException>(() => previous);
        Assert.Equal(new[] { "human" }, calls.ToArray());
    }

    [Fact]
    public async Task UnknownSubmittedMutationIsNotRetriedAndQueuedStopRunsLast()
    {
        var commands = new PlatformPolicyCommands();
        var entered = Signal();
        var release = Signal();
        var calls = new ConcurrentQueue<string>();
        var unknown = new IOException("synthetic lost response; outcome unknown");
        async Task<string> Mode(string mode)
        {
            calls.Enqueue(mode);
            entered.SetResult(true);
            await release.Task;
            throw unknown;
        }
        Task<string> Tick() { calls.Enqueue("tick"); return Task.FromResult("tick"); }
        Task<string> Stop() { calls.Enqueue("stop"); return Task.FromResult("stop"); }
        Task<string> previous = commands.RunAsync(PlatformPolicyCommand.Auto,
            () => Task.CompletedTask, Mode, Tick, Stop);
        await entered.Task.WaitAsync(TimeSpan.FromSeconds(3));
        Task<string> recovery = commands.RunAsync(PlatformPolicyCommand.Stop,
            () => throw new InvalidOperationException(), Mode, Tick, Stop);
        Assert.Equal(new[] { "auto" }, calls.ToArray());
        release.SetResult(true);
        Assert.Same(unknown, await Assert.ThrowsAsync<IOException>(() => previous));
        Assert.Equal("stop", await recovery.WaitAsync(TimeSpan.FromSeconds(3)));
        Assert.Equal(new[] { "auto", "stop" }, calls.ToArray());
    }

    [Fact]
    public async Task FailedPreparationDoesNotSendAnyMutation()
    {
        var commands = new PlatformPolicyCommands();
        var pending = new InvalidOperationException("recording Close pending");
        int effects = 0;
        Task<string> Mutation() { effects++; return Task.FromResult("unexpected"); }
        Assert.Same(pending, await Assert.ThrowsAsync<InvalidOperationException>(() => commands.RunAsync(
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
        Assert.Equal("receipt", await commands.RunAsync(PlatformPolicyCommand.OneStep,
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
        Task<string> previous = commands.RunAsync(PlatformPolicyCommand.Auto,
            () => release.Task, _ => Mutation(), Mutation, Mutation);
        commands.InvalidatePending();
        release.SetResult(true);
        await Assert.ThrowsAsync<PlatformPolicyCommandSupersededException>(() => previous);
        Assert.Equal(0, effects);
    }
}
