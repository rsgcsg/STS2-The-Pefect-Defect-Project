# 1a 初始计算图检查 — 2026-09-18

源码 `60b04ffff3c87a2e283b251d1ae6ed4f429622f6`；锁
`1dd5f0dc645c7330b4a6e7712da5edad7f04caa6640b69c0cf1d0dfac42f84f7`。
私有任务 `com.spireagent.stage1a.profile.20260918-170715`；结果 schema
`stpd/stage1a-graph-profile-v1`，状态 completed，总耗时 180.869 秒。

本机 MPS/FP32，Torch 2.13.0、Transformers 5.15.1，Qwen3-0.6B-Base
revision `da87bfb608c14b7cf20ba1ce41287e8de496c0cd`，权重 digest
`c0d42533fa221952ba6502ae7425a424e7784a2190122bb10250807b896b85ec`。
四图各检查 128/512/1024 个随机合法词表 ID、两个 24/25-token 动作，seed1701。
使用合成选择索引检查 backward，optimizer 更新次数为零；没有人类数据或游戏执行。

| 配置 | 1024-token forward 秒 | backward 秒 | 反向后 MPS driver 字节 |
|---|---:|---:|---:|
| B-S | 0.181 | 0.114 | 1152401408 |
| D-Simple-S | 0.055 | 0.057 | 1128218624 |
| B-PF | 62.118 | 95.966 | 16582017024 |
| D-Simple-PF | 0.770 | 0.001 | 2833039360 |

全部 12 项分数和训练参数梯度有限；冻结骨干未获得参数梯度。
没有统一 warm-up 或重复采样，执行顺序和内存压力影响时间；这些不是正式延迟分布。
driver 字节是采样值，不是独占物理内存或精确峰值，不能与 CPU RSS 简单相加。

结论是计算图可运行，同时 B-PF 的整段 autograd 路径在较长输入时存在严重成本问题。
后续改用固定因果前缀 KV、末尾 query 保梯度的执行方式，必须分别验证分数／梯度等价
及实际性能，不能把本报告的结果改写为优化版已通过。真实 lite 数据曾达到约六千个
Qwen tokens，不能用本次 1024-token 两候选检查推断正式训练预算。

首次进程已完成并保留结果；旧 `launchctl submit` 启动方式随后重复唤起，均被
“输出已存在”拒绝，没有覆盖结果或重新训练。任务已移除。后续使用显式
`RunAtLoad=true, KeepAlive=false` 的一次性 job，并分别核对进程退出与报告终态。
