# Stage 1a four-configuration engineering pilot

All four configurations completed ten updates on the same public-compact model view
`2553accb6bf393809f0f813f94f73a1ccd266cdb6824a38e1591b1a1ebd478fd`.
49 eligible train decisions feed the fixed plan; dev has 16 decisions from one
independent run. No test/Gold labels or game actions are used. This is a pipeline
and comparison check, not architecture selection or evidence of pretrained advantage.

| Configuration | Top-1 | n > 1 Top-1 | NLL | Worker attempt including dev |
|---|---:|---:|---:|---:|
| `stage1a.dsimple.s.v1` | 8/16 | 6/14 | 1.720264 | 9.769 s |
| `stage1a.dsimple.pf.v1` | 4/16 | 2/14 | 1.721246 | 76.375 s |
| `stage1a.b.pf.v2` | 6/16 | 4/14 | 1.714594 | 166.611 s |
| `stage1a.b.s.v2` | 3/16 | 1/14 | 2.362603 | 8.853 s |

The B-S wrapper took 32.818 seconds (CLI 31.584 seconds including input validation).
Its worker attempt was 8.853 seconds. Different scopes must not be conflated;
research preparation, prior failed/paused attempts and validation are additional cost.
The comparison verified exact result closures and common dev identities.

## New B-S artifacts

- source: `5a4bdaddb9c5b9bc42966dbd72de58054c308384`
- run: `b795dba9af1633b72cbf7aad4b60d9fb2112c2d826acd3aa5c54b969ef4a3fb8`
- checkpoint: `12813d4179a0af2a079202100d4111e9484228c692946cdd19b46bc75915181d`
- result: `f3176e481b3a0f6ae688a47a708bd17e256c6b0eb51eafaccb867d1bff75d064`
- model: `01b60f59b01db98021c26fc77f45094c5fa3358b4923231a6836699317abb307`
- evaluation: `9512b1848b16c6cce05019db617bf910243eb9de6aac7d06a1203b774685786c`

Private evidence directory: `stage1a-packed-b-s-20260918-213508` under the research
root. The model export is `stage1a-exports/b-s-packed-v2`.

Checkpoint/published weights were byte-identical. The independent scorer loaded in
0.0646 seconds and scored the 18-candidate snapshot in 0.3362 seconds, without loading
Qwen. Its original-order scores exactly matched the restored engine. Candidate
reversal passed `atol=2e-5, rtol=2e-5`, with maximum difference 5.3644e-7. This is one
snapshot timing without repeated latency statistics, not full-game latency.

- Comparison receipt SHA-256: `13ac5a2f7f9ad59332fe182ea2d847418482f456ce8992a9c8e720358971cbb1`.
- Export receipt SHA-256: `02055edbcbdb3a41622a3e8f9fff2d450075abd6ff476821a9e1dce227fa832f`.

## Game-entry integration work

An additive trusted `token-v1` adapter now connects public snapshot exports to the
existing decision-only NDJSON protocol. Workbench supports an operator-created local
catalog alongside shipped S1; its commands and Runtime package remain fixed by code.
No model has yet been registered for actual native use. Existing S1 support is unchanged.

Focused token-port and Workbench tests passed (101 tests, followed by 16 token-port
checks including an additional no-ML-import regression). A private new-process test
produced ready and a complete 18-score decision from the real B-S export. Public
TypeScript consumer verification is pending: the active worktree had no installed
tsc/dependencies. The dependency/build, consumer and full Python gates will run as
one durable, separately monitored job. No native game qualification follows from these
source, export or protocol checks. Local registration with current game identity,
Workbench/Mod loading and Human/Stop/model-switch controls remain outstanding.
