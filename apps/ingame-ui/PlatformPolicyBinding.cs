using System.Text.Json.Serialization;

namespace STS2PlatformLiveUi;

/// <summary>Fresh read-only Runtime observation, bound to this game's instance.</summary>
public sealed record PlatformPolicyBinding(
    [property: JsonPropertyName("schema")] string Schema,
    [property: JsonPropertyName("run_id")] string RunId,
    [property: JsonPropertyName("runtime_instance_id")] string RuntimeInstanceId,
    [property: JsonPropertyName("recovery_epoch")] long? RecoveryEpoch)
{
    public void Validate(string expectedRunId, string expectedGameInstanceId)
    {
        if (Schema != "sts2.policy-runtime/environment-1" || RecoveryEpoch is null or < 0 or > 9007199254740991
            || string.IsNullOrWhiteSpace(expectedRunId) || string.IsNullOrWhiteSpace(expectedGameInstanceId)
            || RunId != expectedRunId || RuntimeInstanceId != expectedGameInstanceId)
            throw new InvalidOperationException("模型运行器未确认连接当前游戏，请在工作台重新准备模型。");
    }
}
