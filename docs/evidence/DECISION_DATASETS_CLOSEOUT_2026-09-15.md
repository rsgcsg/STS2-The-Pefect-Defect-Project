# Fixed decision datasets: bounded closeout, 2026-09-15

## Exact qualification

Tested STPD source: `2aa69bdfe62eb2734ed95480fedbb5c09a556f8d`.
PR #12 integrated normally into develop at `0025b786c09565f55004075c1fe23bf5eeb01f24`.
These receipts qualify their actual source, not a later merge commit. Published release notes
and `refs/notes/b-workflow-release` bind subsequent source/CI/image promotion.

- Local clean-source closeout: PASS, 761 tests, 3 skips, 21 subtests; Ruff/Mypy,
  both CPU E2Es, Node UI regressions, package build and diff checks.
- Hosted run [34935862157](https://github.com/rsgcsg/STS2-The-Perfect-Defect/actions/runs/34935862157):
  Linux, Windows and required `locked-python` PASS.
- Qualified Hub OCI: `sha256:238338e7992c2f11d430ff90319e544b696d0251b088287d1a898fd92116f251`.
- Hub HTTPS source identity and container health PASS; local Workbench cold-started from a
  separate clean detached checkout of the same source. Workbench digest:
  `f60d64586298718f4f29d1084955346c28b65b6d4413ea746d3e369c3dee874f`.
- Lock: `7f760f8be6f7f9f7ac150f5d02f81f9b0190775753cc3215f14630153eec3dca`.
- Platform Evidence pin unchanged: `e26b7c76a3c007c63f7ae9eee285e6dc3d78cd73`.

## Real data and member checks

Two existing authorized sources yielded 814 proved canonical decisions: 269 + 545.
One unresolved occurrence and one normal cancellation were excluded with reasons. Both
sources remain incomplete fragments; no uninterrupted complete run was invented. Fewer
than three independent split components remain unassigned, not training-ready.

Immutable dataset `ebba631f1aef4aa64a02ab1ac1cd245b0781034595587581118cefbb6af22974`
retains its actual earlier producer `d19814759a71d285d2d21e96d5a7e7061962a7a3`.
The R2 owning loader reprojected all records from exact source bytes and verified payloads.
Logical dataset: `3304593228791e0929fc465108784231cbab9912c8755cfe2b1efa8c08862090`.

Normal-member download on the final tested source verified 3/3 files, 1,858,016 bytes:
export `176dd6ba11eca772419fe20397c9a5c954e930838e43f7c5ed43d2a2a06917df`.
The Human operator confirmed the final local fixed-inventory page displays all three files.
The inherited four-second login timeout was insufficient for source-authorized exports;
bounded data deadlines and unknown-submission reporting were repaired and regression-tested.
No automatic submission retry or sharing-policy relaxation was added.

## Recovery and distribution

The obsolete SSH source-IP rule was removed. Public-key-only authentication, strict original
host identity, UFW, TLS and loopback-only Hub service remain. See the
[network recovery report](HUB_NETWORK_RECOVERY_2026-09-15.md) and
[operations runbook](../../deploy/hub/OPERATIONS.md). This does not promise access through
institutional networks that independently block SSH.

Final tested image backup receipt:
`0989222201163394ae6e6a3243d8f3343835dc874ab4d31ec1502445491f27cc`.
Off-host readback and isolated paused restore PASS; restored DB SHA256:
`2bd94b3da8b3951ef7011ddb915c89e4b8bb2bd000f8607591bf1ba93fca6acb`.
Backup timer active; capacity reserve preflight PASS. Production state was not restored.

Candidate developer ZIP SHA256:
`77ee4524c8aa349a9a1883d8e71be20291e18eb5b4810218c8c7fd2837bcdfbb`
(3,132,131 bytes, 20 files). Fixed Collection Tool:
`80d37fd70f7eb51353870bdbc6032c85084e1e5f7384a56c41341b7058d68481`.
Owner BOM/provenance and native DLL/manifest checked. No native package change, gameplay,
new recording, raw evidence rewrite or GPU work occurred. A final release ZIP must be rebuilt
at its actual release source; this candidate is not silently relabeled.

## Limits and maintenance

Defaults admit good decisions from incomplete/lost runs and compatible version mixtures.
Unsupported evidence/schema, conflicting identity and unavailable sharing remain closed.
Original lineage/gaps survive filtering; sequence consumers must not join across excluded rows.
The existing strict Full-Run training contract is unchanged. Model adapters, training readiness,
model quality, free GPU availability and scientific qualification are not release claims.

Selection is bounded to 100 uploads / 256 MiB compressed input; profile view is latest 100
shared profiles, not a global unique-game count. Failed jobs remain visible and require an
explicit retry or smaller selection. Preserve artifacts and failure reports, fix the owning
cause with regression coverage, then produce a new immutable version. Roll back image/config
with matching backups; never reset upload queues or rewrite Human evidence to make gates pass.
