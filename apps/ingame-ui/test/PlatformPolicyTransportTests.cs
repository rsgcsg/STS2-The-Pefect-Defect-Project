using System.Net;
using System.Net.Http;
using System.Text.Json;
using STS2PlatformLiveUi;
using Xunit;

namespace STS2PlatformLiveUiTests;

public sealed class PlatformPolicyTransportTests
{
    private sealed class Handler(Func<HttpRequestMessage, Task<HttpResponseMessage>> handle) : HttpMessageHandler
    {
        public int Attempts { get; private set; }
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        { Attempts++; return handle(request); }
    }

    [Theory]
    [InlineData(409, "runtime_game_mismatch")]
    [InlineData(409, "runtime_recovery_epoch_mismatch")]
    [InlineData(409, "runtime_run_mismatch")]
    [InlineData(428, "runtime_recovery_precondition_required")]
    [InlineData(503, "runtime_environment_unavailable")]
    public async Task ExactOwnerRejectionsAreKnownAndNeverRetried(int status, string code)
    {
        using var handler = new Handler(_ => Task.FromResult(new HttpResponseMessage((HttpStatusCode)status) {
            Content = new StringContent(JsonSerializer.Serialize(new { schema = "sts2.policy-runtime/http-2", error = code })) }));
        using var client = new HttpClient(handler);
        using var request = new HttpRequestMessage(HttpMethod.Post, "http://127.0.0.1/v2/mode");
        var error = await Assert.ThrowsAsync<PlatformPolicyCommandRejectedException>(() =>
            PlatformPolicyTransport.SendAsync(client, request, _ => Task.FromResult("must not decode")));
        Assert.Equal(code, error.Message);
        Assert.Equal(1, handler.Attempts);
    }

    [Theory]
    [InlineData(409, "{\"schema\":\"sts2.policy-runtime/http-2\",\"error\":\"runtime_game_mismatch\",\"extra\":true}")]
    [InlineData(409, "{\"schema\":\"sts2.policy-runtime/http-2\",\"error\":\"invented_error\"}")]
    [InlineData(500, "{\"schema\":\"sts2.policy-runtime/http-2\",\"error\":\"runtime_game_mismatch\"}")]
    [InlineData(409, "<html>proxy denied</html>")]
    [InlineData(307, "redirect")]
    public async Task UnprovenErrorResponsesRemainUnknown(int status, string body)
    {
        using var handler = new Handler(_ => Task.FromResult(new HttpResponseMessage((HttpStatusCode)status) { Content = new StringContent(body) }));
        using var client = new HttpClient(handler);
        using var request = new HttpRequestMessage(HttpMethod.Post, "http://127.0.0.1/v2/mode");
        await Assert.ThrowsAsync<PlatformPolicyCommandUnknownException>(() =>
            PlatformPolicyTransport.SendAsync(client, request, _ => Task.FromResult("must not decode")));
        Assert.Equal(1, handler.Attempts);
    }

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public async Task LostOrMalformedSuccessIsUnknownAndNotRetried(bool malformed)
    {
        using var handler = new Handler(_ => malformed
            ? Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK) { Content = new StringContent("{}") })
            : throw new TaskCanceledException("response was lost after effect"));
        using var client = new HttpClient(handler);
        using var request = new HttpRequestMessage(HttpMethod.Post, "http://127.0.0.1/v2/tick");
        await Assert.ThrowsAsync<PlatformPolicyCommandUnknownException>(() =>
            PlatformPolicyTransport.SendAsync<string>(client, request, _ => throw new JsonException("missing status")));
        Assert.Equal(1, handler.Attempts);
    }
}
