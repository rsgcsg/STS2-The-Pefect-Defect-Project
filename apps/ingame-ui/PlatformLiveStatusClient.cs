using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;
using STS2Connector.PlayerEnvironment.Protocol;
using STS2HumanAnnotator.Core;
using STS2HumanAnnotator.Mod;

namespace STS2PlatformLiveUi;

public sealed class PlatformLiveStatusClient : IDisposable
{
    private const string PolicyRuntimeHttpSchema = "sts2.policy-runtime/http-2";
    private const string PolicyRuntimeTickSchema = "sts2.policy-runtime/http-2/tick-1";

    private readonly HttpClient _connectorHttp;
    private readonly HttpClient _policyRuntimeHttp;
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        PropertyNameCaseInsensitive = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
    };

    public PlatformLiveStatusClient()
    {
        _connectorHttp = new HttpClient
        {
            BaseAddress = new Uri($"http://127.0.0.1:{ResolveConnectorPort()}/"),
            Timeout = TimeSpan.FromMilliseconds(900)
        };
        _policyRuntimeHttp = new HttpClient
        {
            BaseAddress = ResolvePolicyRuntimeAddress(),
            Timeout = TimeSpan.FromMilliseconds(900)
        };
    }

    public async Task<PlatformLiveStatus> ReadAsync(CancellationToken cancellationToken = default)
    {
        PlayerEnvironmentCapabilitiesResponse? capabilities = null;
        PlayerEnvironmentSnapshot? snapshot = null;
        PlayerEnvironmentControlSnapshot? controller = null;
        var errors = new List<string>();
        string connectorTransportStatus = "unavailable";
        string? connectorTransportDetail = null;

        try
        {
            PlayerEnvironmentCapabilitiesResponse fetchedCapabilities = await GetAsync<PlayerEnvironmentCapabilitiesResponse>(
                _connectorHttp,
                "api/player-environment/capabilities",
                cancellationToken);
            PlayerEnvironmentSnapshot fetchedSnapshot = await GetAsync<PlayerEnvironmentSnapshot>(
                _connectorHttp,
                "api/player-environment/snapshot",
                cancellationToken);
            PlayerEnvironmentControlSnapshot fetchedController = await GetAsync<PlayerEnvironmentControlSnapshot>(
                _connectorHttp,
                "api/player-environment/controller",
                cancellationToken);
            PlatformLiveStatusProjection.EnsureConnectorCoherence(
                fetchedCapabilities,
                fetchedSnapshot,
                fetchedController);
            capabilities = fetchedCapabilities;
            snapshot = fetchedSnapshot;
            controller = fetchedController;
            connectorTransportStatus = "connected";
        }
        catch (Exception exception) when (IsLoopbackFailure(exception))
        {
            capabilities = null;
            snapshot = null;
            controller = null;
            connectorTransportDetail = exception is TaskCanceledException
                ? "Connector loopback request timed out."
                : exception.Message;
            errors.Add($"Connector: {connectorTransportDetail}");
        }

        PolicyRuntimeStatus? policyRuntime = null;
        string policyRuntimeTransportStatus = "unavailable";
        string? policyRuntimeTransportDetail = null;
        try
        {
            PolicyRuntimeHttpStatusResponse response = await GetAsync<PolicyRuntimeHttpStatusResponse>(
                _policyRuntimeHttp,
                "status",
                cancellationToken);
            EnsurePolicyRuntimeStatus(response.Schema, response.Status);
            policyRuntime = response.Status;
            policyRuntimeTransportStatus = "connected";
        }
        catch (Exception exception) when (IsLoopbackFailure(exception))
        {
            policyRuntimeTransportDetail = exception is TaskCanceledException
                ? "Policy Runtime loopback request timed out."
                : exception.Message;
            errors.Add($"Policy Runtime: {policyRuntimeTransportDetail}");
        }

        RecordingApplicationStatus recording = RecordingApplicationService.Instance.QueryStatus();
        return PlatformLiveStatusProjection.Build(
            policyRuntime,
            capabilities,
            snapshot,
            controller,
            recording,
            connectorTransportStatus,
            connectorTransportDetail,
            policyRuntimeTransportStatus,
            policyRuntimeTransportDetail,
            errors);
    }

    public async Task<PlatformPolicyBinding> ObserveBindingAsync(
        string expectedRunId, string expectedGameInstanceId, CancellationToken cancellationToken = default)
    {
        PlatformPolicyBinding observed = await GetAsync<PlatformPolicyBinding>(
            _policyRuntimeHttp, "v2/environment", cancellationToken);
        observed.Validate(expectedRunId, expectedGameInstanceId);
        return observed;
    }

    public async Task<PolicyRuntimeStatus> SetModeAsync(
        string mode,
        string expectedRunId,
        PlatformPolicyBinding? binding = null,
        CancellationToken cancellationToken = default)
    {
        ValidateMode(mode);
        if (mode != "human" && binding is null) throw new InvalidOperationException("A fresh game binding is required.");
        PolicyRuntimeHttpStatusResponse response = await PostAsync<PolicyRuntimeHttpStatusResponse>(
            "mode",
            new { mode },
            expectedRunId,
            cancellationToken, binding);
        EnsurePolicyRuntimeStatus(response.Schema, response.Status);
        return response.Status;
    }

    public async Task<PolicyRuntimeStatus> StopAsync(string expectedRunId, CancellationToken cancellationToken = default)
    {
        var response = await PostAsync<PolicyRuntimeHttpStatusResponse>("stop", new { }, expectedRunId, cancellationToken);
        EnsurePolicyRuntimeStatus(response.Schema, response.Status);
        return response.Status;
    }

    public async Task<PolicyRuntimeStatus> TickAsync(string expectedRunId, PlatformPolicyBinding binding, CancellationToken cancellationToken = default)
    {
        PolicyRuntimeTickResponse response = await PostAsync<PolicyRuntimeTickResponse>(
            "tick",
            new { max_ticks = 1 },
            expectedRunId,
            cancellationToken, binding);
        if (response.Schema != PolicyRuntimeTickSchema)
            throw new JsonException($"Policy Runtime tick schema is unsupported: {response.Schema}");
        EnsurePolicyRuntimeStatus(response.Schema, response.Status, allowTickSchema: true);
        return response.Status;
    }

    public void Dispose()
    {
        _connectorHttp.Dispose();
        _policyRuntimeHttp.Dispose();
    }

    private async Task<T> GetAsync<T>(
        HttpClient client,
        string relativePath,
        CancellationToken cancellationToken)
    {
        using HttpResponseMessage response = await client.GetAsync(relativePath, cancellationToken);
        return await ReadResponseAsync<T>(response, relativePath, cancellationToken);
    }

    private async Task<T> PostAsync<T>(
        string relativePath,
        object body,
        string expectedRunId,
        CancellationToken cancellationToken,
        PlatformPolicyBinding? binding = null)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(expectedRunId);
        using var request = new HttpRequestMessage(HttpMethod.Post, "v2/" + relativePath)
        {
            Content = JsonContent.Create(body, options: JsonOptions)
        };
        request.Headers.Add("X-STS2-Policy-Run-ID", expectedRunId);
        if (binding is not null)
        {
            binding.Validate(expectedRunId, binding.RuntimeInstanceId);
            request.Headers.Add("X-STS2-Game-Instance-ID", binding.RuntimeInstanceId);
            request.Headers.Add("X-STS2-Recovery-Epoch", binding.RecoveryEpoch!.Value.ToString(System.Globalization.CultureInfo.InvariantCulture));
        }
        using HttpResponseMessage response = await _policyRuntimeHttp.SendAsync(request, cancellationToken);
        return await ReadResponseAsync<T>(response, relativePath, cancellationToken);
    }

    private static async Task<T> ReadResponseAsync<T>(
        HttpResponseMessage response,
        string relativePath,
        CancellationToken cancellationToken)
    {
        if (response.StatusCode == HttpStatusCode.NotFound)
            throw new HttpRequestException($"Loopback endpoint not found: {relativePath}");
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<T>(JsonOptions, cancellationToken)
            ?? throw new JsonException($"Loopback endpoint returned an empty {typeof(T).Name}.");
    }

    private static void EnsurePolicyRuntimeStatus(
        string envelopeSchema,
        PolicyRuntimeStatus status,
        bool allowTickSchema = false)
    {
        if (envelopeSchema != PolicyRuntimeHttpSchema
            && !(allowTickSchema && envelopeSchema == PolicyRuntimeTickSchema))
        {
            throw new JsonException($"Policy Runtime HTTP schema is unsupported: {envelopeSchema}");
        }
        if (status.Schema != PolicyRuntimeStatus.CurrentSchema)
            throw new JsonException($"Policy Runtime status schema is unsupported: {status.Schema}");
        if (status.Runtime == null || string.IsNullOrWhiteSpace(status.Runtime.Version))
            throw new JsonException("Policy Runtime software identity is absent.");
        if (status.Policy == null || string.IsNullOrWhiteSpace(status.Policy.ManifestId))
            throw new JsonException("Policy Runtime policy identity is absent.");
        if (string.IsNullOrWhiteSpace(status.RunId))
            throw new JsonException("Policy Runtime run identity is absent.");
        if (status.Lifecycle is not ("running" or "stopped")
            || status.Mode is not ("human" or "shadow" or "one_step" or "auto")
            || status.Controller is not ("held" or "released"))
        {
            throw new JsonException("Policy Runtime lifecycle status is invalid.");
        }
    }

    private static void ValidateMode(string mode)
    {
        if (mode is not ("human" or "shadow" or "one_step" or "auto"))
            throw new ArgumentOutOfRangeException(nameof(mode), mode, "Unsupported Policy Runtime mode.");
    }

    private static bool IsLoopbackFailure(Exception exception) =>
        exception is HttpRequestException or TaskCanceledException or JsonException or InvalidOperationException;

    private static int ResolveConnectorPort()
    {
        string? configured = Environment.GetEnvironmentVariable("STS2_CONNECTOR_PORT");
        return int.TryParse(configured, out int port) && port is > 0 and <= 65535
            ? port
            : 15526;
    }

    private static Uri ResolvePolicyRuntimeAddress()
    {
        string? configuredUrl = Environment.GetEnvironmentVariable("STS2_POLICY_RUNTIME_URL");
        if (!string.IsNullOrWhiteSpace(configuredUrl)
            && Uri.TryCreate(configuredUrl, UriKind.Absolute, out Uri? configured)
            && configured.Scheme is "http" or "https"
            && string.IsNullOrEmpty(configured.UserInfo)
            && configured.Host is "127.0.0.1" or "localhost" or "::1")
        {
            return new Uri(configured, configured.AbsolutePath.TrimEnd('/') + "/");
        }

        string? configuredPort = Environment.GetEnvironmentVariable("STS2_POLICY_RUNTIME_PORT");
        int port = int.TryParse(configuredPort, out int parsedPort) && parsedPort is > 0 and <= 65535
            ? parsedPort
            : 15527;
        return new Uri($"http://127.0.0.1:{port}/");
    }
}
