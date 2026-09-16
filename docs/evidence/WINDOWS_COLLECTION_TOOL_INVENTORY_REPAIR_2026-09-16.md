# Windows CollectionTool inventory repair — 2026-09-16

## Scope and finding

Evidence source revision `48903212adff7700a333701d2e4e4a03938a9f30` repairs the
CollectionTool verification boundary. The publisher declares exact files in
ordinal POSIX relative-path order, while Windows `Path` ordering can place
mixed-case names differently. The previous verifier therefore rejected the
same paths, sizes and SHA-256 values when only ordering differed.

## Repair and checks

CollectionTool now sorts only its materialized actual rows by their POSIX path
string before the existing exact manifest comparison. Transfer inventory
semantics and strict count/path/byte/size/hash/order checks remain unchanged.
Portable mixed-case and unsorted-manifest regressions pass; the generated local
Windows reference release `bfdb3aac969f5101ea713be4aa89f805334d0393c198a7ce955f0b326195b855`
also verifies. The completion symlink test skips only when Windows symlink
creation reports unavailable privilege (WinError 1314); unknown-outbox checks
remain independently exercised.

This is source/test and local-tool evidence only. It does not establish a new
Human or upload PASS. Existing fixed kits and installed configurations retain their original identities;
this source repair does not rewrite their manifests or transfer prior acceptance.

## Integration refresh

PR #9 merges `develop@defc501c5acb052b9ec439222243439390a755b5` normally,
retaining the rc10 summary and authentication-recovery behavior. The combined
Evidence is version `0.1.0-rc.11`, source
`2490dae5366df27cff668feb5860224ae4900182`; BOM and Python consumer pins refer
to that immutable source. The original repair source above remains historical.
The 107-test Evidence suite passes on macOS, including symlink rejection and
independent unknown-outbox checks. The Windows-order portable regression fails
against the previous verifier and passes against the corrected implementation.
The runtime-install fixture skips unavailable symlink creation only on Windows;
other operating-system errors remain failures. Hosted latest-head Linux/Windows
results belong to PR #9; they are not native installation or Human qualification.
