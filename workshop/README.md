# Workshop release projection — Layers 1–2 and Layer 3 Phase A

This directory is the Steam Workshop **release workspace**, not an npm workspace,
runtime component, installer or second Platform implementation. It holds metadata,
an original project preview and generated candidates from explicit approved inputs.
Staging does not build, install or upload. Preparation currently implements only
build/proposal (Phase A); approval/finalization (Phase B) and publication are not
implemented. A proposed or staged candidate is not an approved Steam release.

## External format authority

Bounded reference check: Mega Crit's official
[sts2-mod-uploader](https://github.com/megacrit/sts2-mod-uploader/tree/d7b7e6b16c413d5a124f474f9e5104ef01f76ab1),
especially its [generated workspace template](https://github.com/megacrit/sts2-mod-uploader/tree/d7b7e6b16c413d5a124f474f9e5104ef01f76ab1/template).
No uploader binary or implementation is vendored. The template supplies the
`workshop.json` field names, private visibility, required `image.png` (under 1 MB),
and uploaded `content/` directory. This reference pin is format provenance, not
approval to run a particular uploader release.

```text
workshop/
  .gitignore       deny-by-default local/output policy
  workshop.json    Workshop listing metadata, private by default
  image.png        original project preview; no game/third-party assets
  README.md        release boundary and next-layer requirements
  content/         GENERATED ONLY; absent in a clean clone until staging
  staging-receipt.json  generated LOCAL receipt, outside the upload payload
```

Git cannot retain an empty generated directory. Do not add a tracked placeholder
or manually maintained DLL/manifest under `content/`. All unlisted paths are
ignored, including content, `mod_id.txt`, uploader logs/binaries, credentials,
`.env`, Steam state, game files and `.local` evidence. Do not force-add these files.
Boundary tests also reject non-allowlisted tracked files, including force-added
ones. Keep the uploader and real secrets outside this checkout; ignore rules
are accidental-commit protection, not a secret store or upload payload filter.

## One owner per fact

[`apps/game-mod`](../apps/game-mod/README.md) remains the only game-side production
package authority. Its `mod_manifest.json` owns runtime identity, version,
dependencies and compatibility declarations. Its project/build/source-identity
code owns composition and provenance; its lifecycle owns install/load/rollback.
Workshop metadata does not override or duplicate that runtime manifest.
Workshop `dependencies` means Steam item IDs, not runtime manifest dependencies.
No Steam item is registered here; an empty list makes no third-party compatibility
claim. Private metadata does not authorize creating even a private item.

Staging projects the exact approved game-mod output without rebuilding, rewriting
its runtime manifest or copying source. The build's `package.files` currently
names exactly `STS2_PLATFORM.dll` and `STS2_PLATFORM.json`: these two files are the
entire payload. `build-provenance.json` is required validation input but is not a
runtime file and is NOT uploaded. Its SHA and source/game/artifact facts remain
in the private staging receipt. Known `.NET` output `STS2_PLATFORM.pdb` and
`STS2_PLATFORM.deps.json` may be present in the input directory but are excluded.
Any other input entry, including directories, fails closed. This is an explicit
small input/output allowlist, not recursive copying plus a blacklist.

## Deterministic staging

From a clean committed checkout, select an existing game-mod build output and the
SHA256 of its independently reviewed `build-provenance.json`:

```sh
npm run workshop:stage -- --source "/absolute/approved-output" --provenance-sha256 APPROVED_64_HEX_SHA
```

The default PE reader is the existing built Annotator Tool at
`components/annotator/src/STS2HumanAnnotator.Tool/bin/Release/net9.0/sts2-human-annotator.dll`.
If necessary provide `--identity-tool "/absolute/trusted-tool/sts2-human-annotator.dll"`
from a trusted complete tool distribution. .NET must be available. Staging never
builds or downloads that tool and never executes the candidate Mod assembly.
No approval is inferred from a path, file age or a newly calculated hash: the
operator/next-layer release owner selects the provenance pin. This integrity pin
is not a signature or native/Human qualification.

Validation requires the known provenance schema, clean producer/current source,
the current game-mod source closure via its existing `sourceSetIdentity` /
`sourceSetMatches`, the exact two-file package inventory, and byte-identical
runtime manifest against `apps/game-mod/mod_manifest.json`. The existing Tool's
PE reader independently checks SHA256/MVID against pinned build provenance. Game
identities are retained and structurally checked, not requalified against a running
game. Unrelated workspace commits are permitted when the owning compiled source
identity matches; old native source is rejected, not relabelled as current.

The only output location is this checkout's `workshop/content/`. Before replacement,
the stager checks the output tree/ancestors for links and unsafe file types and
rejects overlapping source/output paths. A local exclusive lock prevents concurrent
stagers. It removes the old generated content and receipt, validates input, writes
only the allowlisted bytes to an isolated sibling directory, re-reads/verifies
bytes and hashes, rechecks source stability, then renames the candidate into place.
Ordinary validation failures leave no candidate/receipt. Unsafe paths or an existing
lock fail before cleanup, preserving the old files; neither failure reports success.
An interrupted process may leave an ignored `.stage-*` directory or lock: inspect
it and confirm no stager is running before removing that generated state. There
is no automatic retry or stale-lock takeover. Do not run an uploader concurrently.

The deterministic JSON receipt records current and producer workspace revisions,
component source identity, game-mod version, source artifact path, SHA/MVID,
manifest/provenance hashes, game identity, ordered payload hashes/sizes and excluded
input sidecars. It has no clock-dependent field; identical inputs at the same paths
and source produce the same bytes. Paths make it local operator data, not a public
receipt or a new runtime authority. Preserve the original approved build/provenance.
Only `content/` is prospective upload payload; never upload the whole workspace.

Connector, Native Foundation, Annotator, Live UI and Policy Runtime stay in their
current paths. Workbench, immutable Collection Tool, device authorization, consent,
raw recordings and upload queues are not Workshop content. Subscribing will not
itself authorize cloud upload, model execution or research admission.

## Responsibility audit / migration decision

At base `d5785d215087719189a3a6bada9addb34b7d95c5`:

| Existing area | Decision and reason |
| --- | --- |
| game-mod project, build, source identity, manifest | KEEP: native composition and exact package authority, not Steam-specific |
| game-mod lifecycle, loaded checks, collection setup | KEEP: installation, rollback and recording binding owners shared by existing distribution |
| ingame-ui source | KEEP: runtime presentation, never release metadata |
| root lifecycle wrappers and component/BOM checks | KEEP: route to existing owners, not Workshop publication logic |
| Python developer-kit packaging/install | KEEP: composes fixed Mod/tool/application distribution, not Steam-specific |

No existing implementation was physically migrated. Adding a release consumer
does not justify moving its producer or changing component source closure/BOM.

## Checks and non-claims

`node --test tools/workshop-stage.test.mjs` runs synthetic portable staging mechanics
fixtures with injected source/PE readers; these are NOT game DLLs or native evidence.
The production CLI always uses the real owner readers, with no fixture bypass flag.
`npm run check:boundaries` includes these tests plus metadata, preview and actual
Git ignore/index tests. Tests need no Steam, credentials, STS2 or uploader.
Root governance, identity/BOM checks and `project:closeout` remain required.
This scaffold changes no runtime/install behavior and proves no upload, Workshop
subscription, installation, loading, Human recording or cloud delivery.

## Layer 3 Phase A: checked build proposal

From a clean committed checkout with the normal locked developer dependencies:

```sh
npm run workshop:prepare -- --build
```

This calls the existing Host workstation discovery and strict process enumeration,
stops if STS2 is running (never kills it), runs `check:repository` and
`game-mod:check`, rechecks source/process state, and invokes `game-mod:build`.
The authoritative build owns exact compilation and provenance. Shared read-only
Layer 2 inspection validates output allowlist, runtime manifest, source closure
and the existing Tool's SHA/MVID result without staging. No second build or
identity implementation is introduced.

The ignored `build-proposal.json` and console result bind exact workspace and
component source, game release/assembly, platform/architecture, Mod version,
DLL SHA/MVID, manifest/provenance SHA, all build file hashes, proposed payload
inventory, and Workshop metadata/image hashes. The result is explicitly
`AWAITING_APPROVAL`, `approved: false`, `checked_build_proposal_only`.
Calculating provenance SHA is not approval. No `content/` or staging receipt is
created or changed by Phase A; any prior staged candidate remains unrelated.
No prepared success is emitted. Output contains private local paths: do not
commit or paste the full proposal publicly.

A failed attempt removes its previous proposal. An exclusive `.prepare.lock`
blocks concurrent attempts; an abruptly terminated attempt may leave that lock
or an incomplete JSON proposal. Neither is success/approval. Verify no prepare
process is active before removing a stale lock; restart Phase A. Never accept a
file merely because it exists. Changes after proposal always require revalidation.

### Deferred Phase B contract (not implemented or executed)

Future explicit approval must match the actual provenance SHA and must not rebuild.
It must revalidate the exact source, all build bytes, runtime manifest and metadata
against Phase A, call existing Layer 2 staging, validate its receipt and the entire
private Workshop workspace, and bind metadata/image/staged hashes into a local
prepared receipt. Drift fails closed and requires a new Phase A. Phase A alone
cannot produce `PREPARED_CANDIDATE` or authorize Layer 4. The CLI rejects approval
arguments until that separately authorized phase is implemented.

## Later inputs

- Explicit approved game-mod output and its exact provenance/compatibility tuple.
- Phase B composes this staging command with separate explicit approval and
  complete workspace verification. It must not build a second Mod.
- Supported Workshop discovery, duplicate-local-install handling and persistent
  config/raw/queue locations outside updateable Workshop content.
- Fixed Collection Tool compatibility and update/rollback policy.
- Separately authorized uploader release/account/item ownership and visibility;
  no credentials are needed for Layer 1.
- Applicable cold-load and bounded Human evidence before advertising deployment.

Rollback is a source revert and discarding the generated candidate after checking
its path. Re-stage a retained approved build only from its compatible exact source.
No installed or cloud bytes change. Layer 3 is stacked on the exact Layer 2
parent, retaining Layers 1–2 unchanged; do not integrate the Layer 1–4 stack into
develop until the separately authorized final integration.
