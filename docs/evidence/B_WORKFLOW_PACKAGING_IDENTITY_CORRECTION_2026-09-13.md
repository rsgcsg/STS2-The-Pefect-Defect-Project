# B workflow packaging identity correction — 2026-09-13

This is an explicit correction to the identity metadata in the
[B workflow baseline](B_UNIFIED_WORKFLOW_RELEASE_2026-09-13.md) and earlier private developer
candidate notes. Original reports, commits, archives, tool manifests and Human evidence are
retained. This correction changes no Mod, recording, component source or historical verifier.

The earlier value `6cf7b407ab44a48baefae0d866ebd54f159a11fe97de769a31874af59d96474e`
is the BOM field `components.evidence.component_source_digest_sha256`. It was incorrectly
reported as the whole BOM file digest; those are different identities. It is not the SHA256 of
`platform-bom.json` at Platform source `693336d7438cb24ecbbf0e90863966db89c40043`.
Direct hashing of that exact Git blob and the identical current file gives:

```text
platform-bom.json bytes: 67304
file SHA256: 6eb029ba4c7172f44b71d53ac280d8f1251f35fbaa7ae57a67a46ff27f07f042
```

Use the file-byte digest above for distribution verification; retain the Evidence component
source digest under its actual component field. Component source/contract digests inside the BOM are separate fields. The BOM's
normal validator passes; no BOM content is changed to fit the old report.

A second private-kit label called `d09552130d5aad0639b5d5358bc3acfed49ba493` the collection
tool source revision. The immutable tool manifest actually identifies it as the workspace
revision; the tool component source is `5e6addb10468b6389948bb8266832c28d7646849`.
Both must be retained separately. The tool's original release ID, file inventory and embedded
historical BOM remain unchanged. A current distribution BOM does not replace the tool's
embedded historical build identity.

The owning cause was hand-maintained release metadata in a machine-local assembly script.
STPD's public offline `tools/package_developer_kit.py` now verifies explicit pinned public
inputs with Platform's CollectionTool owner, derives identities from the clean source/lock
and original manifest, emits a complete deterministic inventory, and refuses extra/symlinked/
changed inputs or an existing output. It generates packaging facts only; release notes own
compatibility, CI, native load, Human approval and cloud claims. The final release must use
that maintained builder and the actual final main-source gates, not this correction as an
artifact qualification shortcut. See the associated final release receipt for exact results.
