using System.Net.Http;
using System.Text.Json;

namespace STS2PlatformLiveUi;

public sealed class PlatformPolicyCommandUnknownException : IOException
{
    public PlatformPolicyCommandUnknownException(Exception cause)
        : base("模型操作结果未确认。请先暂停并接管或结束测试，不要重复发送。", cause) { }
}

public sealed class PlatformPolicyCommandRejectedException : InvalidOperationException
{
    public PlatformPolicyCommandRejectedException(string code) : base(code) { }
}

public sealed class PlatformPolicyRecoveryRequiredException : InvalidOperationException
{
    public PlatformPolicyRecoveryRequiredException()
        : base("上次模型操作结果未确认；请先暂停并接管或结束测试。") { }
}

/// <summary>One POST attempt. Only an exact owner precondition rejection proves non-dispatch.</summary>
public static class PlatformPolicyTransport
{
    public static async Task<T> SendAsync<T>(HttpClient client, HttpRequestMessage request,
        Func<HttpResponseMessage, Task<T>> decodeAndValidate, CancellationToken cancellationToken = default)
    {
        try
        {
            using HttpResponseMessage response = await client.SendAsync(request, cancellationToken).ConfigureAwait(false);
            if (!response.IsSuccessStatusCode)
            {
                string? code = await RejectionAsync(response, cancellationToken).ConfigureAwait(false);
                if (code != null) throw new PlatformPolicyCommandRejectedException(code);
                response.EnsureSuccessStatusCode();
            }
            return await decodeAndValidate(response).ConfigureAwait(false);
        }
        catch (PlatformPolicyCommandRejectedException) { throw; }
        catch (Exception error) { throw new PlatformPolicyCommandUnknownException(error); }
    }

    private static async Task<string?> RejectionAsync(HttpResponseMessage response, CancellationToken cancellationToken)
    {
        // No raw remote message is shown and no HTML error is treated as an owner receipt.
        using Stream stream = await response.Content.ReadAsStreamAsync(cancellationToken).ConfigureAwait(false);
        byte[] bytes = new byte[4097];
        int length = 0;
        while (length < bytes.Length)
        {
            int count = await stream.ReadAsync(bytes.AsMemory(length), cancellationToken).ConfigureAwait(false);
            if (count == 0) break;
            length += count;
        }
        if (length > 4096) return null;
        using JsonDocument document = JsonDocument.Parse(bytes.AsMemory(0, length));
        JsonElement root = document.RootElement;
        if (root.ValueKind != JsonValueKind.Object
            || !root.EnumerateObject().Select(field => field.Name).Order().SequenceEqual(new[] { "error", "schema" })
            || root.GetProperty("schema").GetString() != "sts2.policy-runtime/http-2") return null;
        string? error = root.GetProperty("error").GetString();
        return ((int)response.StatusCode, error) switch
        {
            (409, "runtime_run_mismatch" or "runtime_game_mismatch" or "runtime_recovery_epoch_mismatch") => error,
            (428, "runtime_run_precondition_required" or "runtime_game_precondition_required" or "runtime_recovery_precondition_required") => error,
            (503, "runtime_environment_unavailable") => error,
            (403, "mutation_host_not_allowed" or "mutation_origin_not_allowed") => error,
            (415, "mutation_requires_application_json") => error,
            _ => null
        };
    }
}
