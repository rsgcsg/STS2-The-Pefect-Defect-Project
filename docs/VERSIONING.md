# Component Versioning

The monorepo does not impose lockstep component versions.

- Connector, Host Runtime, Annotator, evidence tools and Workbench have
  independent semantic versions.
- Component tags use `<component>/v<version>`.
- `platform-bom/v<version>` names a tested compatible composition.
- Player Environment protocol, SDK version, component version and exact artifact
  identity are distinct.
- Consumer SDK and Host Runtime package assets are immutable release inputs;
  external consumers do not install a branch or sibling source checkout.

The component identity report records the workspace commit, the most recent
commit that changed each component path, the component Git tree, and source and
contract digests. A change outside a component cannot change its path-scoped
identities. Runtime evidence binds artifact bytes and does not transfer across
a rebuild.

## Compatibility is not equal Git revisions

Connection compatibility belongs to the declared protocol, capabilities and auth contract;
game-native compatibility belongs to actual loaded native seams and operands. Dataset
compatibility belongs to schema/semantic interpretation and explicit selection policy; model
compatibility belongs to representation, adapter, Reads/action catalog and environment support.
Record exact game, Mod, collector, application and research provenance without requiring all
components or machines to share a Git SHA. An unrelated edit is not a required client update.

Exact binding remains necessary for artifact integrity, the executing native tuple, immutable
queue/tool association, frozen dataset/splits, checkpoints and reproducible evaluations. Unknown
compatibility stays unknown; this rule does not waive an existing native or schema check.
Keep historical data unchanged and publish a new derived dataset/model when interpretation
changes. Upgrade/release triggers and rollout ownership are defined once in
[Development Workflow](DEVELOPMENT_WORKFLOW.md#compatibility-and-update-policy).
