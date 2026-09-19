import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { sourceSetIdentity } from "../apps/game-mod/source-identity.mjs";
import { PAYLOAD, inspectWorkshopBuild, regularFile, safePath, sha256 } from "./workshop-stage.mjs";

// Explicitly authorized tool evolution only; no generic same-tree/ancestor bypass.
const TOOL_PATHS = new Set(["tools/workshop-prepare.mjs", "tools/workshop-prepare.test.mjs",
  "tools/workshop-finalize.mjs", "tools/workshop-finalize.test.mjs",
  "tools/workshop-boundary.test.mjs", "README.md", "workshop/README.md"]);
export function verifyToolEvolution(repo, producer, current) {
  for (const sha of [producer, current]) assert.match(sha, /^[a-f0-9]{40}$/u);
  const git = (args) => execFileSync("git", args, { cwd: repo, encoding: "utf8" });
  git(["merge-base", "--is-ancestor", producer, current]);
  const changed = git(["diff", "--name-only", "--no-renames", "-z", producer, current]).split("\0").filter(Boolean);
  for (const file of changed) assert.ok(TOOL_PATHS.has(file), `non_orchestration_source_drift:${file}`);
  return changed.sort();
}

const readJson = (bytes) => JSON.parse(bytes.toString("utf8"));
function inventory(directory, names) {
  return names.map((name) => {
    const bytes = regularFile(path.join(directory, name));
    return { name, size_bytes: bytes.length, sha256: sha256(bytes) };
  });
}
function listingIdentity(repo) {
  const directory = path.join(repo, "workshop");
  const listing = readJson(regularFile(path.join(directory, "workshop.json")));
  assert.deepEqual(Object.keys(listing).sort(), ["title", "description", "visibility", "changeNote",
    "tags", "dependencies", "contentDescriptors"].sort(), "unknown_workshop_metadata");
  assert.equal(listing.visibility, "private", "private_visibility_required");
  for (const field of ["title", "description", "changeNote"]) assert.ok(typeof listing[field] === "string" && listing[field].trim());
  assert.deepEqual(listing.tags, ["Tools & APIs"]);
  assert.deepEqual(listing.dependencies, []);
  assert.deepEqual(listing.contentDescriptors, []);
  // Same bounded format contract as Layer 1, plus immutable Phase A hash binding.
  const image = regularFile(path.join(directory, "image.png"));
  assert.ok(image.length >= 33 && image.length < 1_000_000, "invalid_preview_size");
  assert.deepEqual(image.subarray(0, 8), Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]));
  assert.equal(image.toString("ascii", 12, 16), "IHDR");
  assert.ok(image.readUInt32BE(16) >= 256 && image.readUInt32BE(20) >= 256, "invalid_preview_dimensions");
  return Object.fromEntries(inventory(directory, ["workshop.json", "image.png"]).map((item) => [item.name, item.sha256]));
}
function verifyWorkspace(repo, final = false) {
  const directory = safePath(path.join(repo, "workshop"));
  const local = [".gitignore", "README.md", "workshop.json", "image.png", "build-proposal.json",
    ".prepare.lock", "content", "staging-receipt.json", "prepare-receipt.json"];
  for (const name of fs.readdirSync(directory)) {
    assert.ok(local.includes(name), `unexpected_workshop_file:${name}`);
    const file = path.join(directory, name);
    safePath(file);
    if (name === "content") {
      assert.ok(fs.statSync(file).isDirectory());
      assert.deepEqual(fs.readdirSync(file).sort(), [...PAYLOAD].sort(), "unexpected_payload");
      inventory(file, PAYLOAD);
    } else regularFile(file);
  }
  if (final) assert.ok(fs.existsSync(path.join(directory, "content")), "missing_staged_payload");
}

// Tests inject mechanics only. The public CLI uses the real owners with no bypass.
export async function finalizeWorkshop({ repositoryRoot, approvedProvenanceSha256, run,
  readSource = sourceSetIdentity, inspect = inspectWorkshopBuild, verifyEvolution = verifyToolEvolution }) {
  const repo = safePath(repositoryRoot);
  const workspace = safePath(path.join(repo, "workshop"));
  const prepared = safePath(path.join(workspace, "prepare-receipt.json"));
  const lockPath = safePath(path.join(workspace, ".prepare.lock"));
  const lock = fs.openSync(lockPath, "wx");
  try {
    if (fs.existsSync(prepared)) { regularFile(prepared); fs.unlinkSync(prepared); }
    assert.match(approvedProvenanceSha256 ?? "", /^[a-f0-9]{64}$/u, "explicit_approval_required");
    const proposalPath = path.join(workspace, "build-proposal.json");
    const proposalBytes = regularFile(proposalPath);
    const p = readJson(proposalBytes);
    assert.equal(p.schema, "spireagent/workshop-build-proposal-1");
    assert.equal(p.result, "AWAITING_APPROVAL");
    assert.equal(p.approved, false);
    assert.equal(p.evidence_level, "checked_build_proposal_only");
    assert.equal(p.provenance_sha256, approvedProvenanceSha256, "approval_pin_mismatch");
    assert.equal(p.workspace_revision, p.source.platform.workspace_revision);
    const current = readSource(repo);
    assert.equal(current.platform.workspace_worktree_status, "clean", "current_source_dirty");
    assert.deepEqual(current.components, p.source.components, "compiled_source_drift");
    assert.deepEqual({ ...current.platform, workspace_revision: p.workspace_revision }, p.source.platform,
      "compiled_platform_drift");
    const evolution = verifyEvolution(repo, p.workspace_revision, current.platform.workspace_revision);
    const source = path.join(repo, "apps/game-mod/bin/Release/net9.0");
    assert.equal(path.resolve(p.source_directory), source, "proposal_output_path_drift");
    const validateInputs = () => {
      assert.ok(regularFile(proposalPath).equals(proposalBytes), "proposal_drift");
      assert.deepEqual(readSource(repo), current, "current_source_drift");
      assert.deepEqual(listingIdentity(repo), p.metadata_sha256, "metadata_drift");
      const names = fs.readdirSync(safePath(source)).sort();
      assert.deepEqual(inventory(source, names), p.build_inventory, "build_bytes_drift");
      assert.equal(sha256(regularFile(path.join(source, "build-provenance.json"))), approvedProvenanceSha256,
        "provenance_drift");
      assert.equal(sha256(regularFile(path.join(repo, "apps/game-mod/mod_manifest.json"))), p.manifest_sha256,
        "runtime_manifest_drift");
    };
    verifyWorkspace(repo);
    validateInputs();
    const verified = inspect({ repositoryRoot: repo, sourceDirectory: source, readSource,
      identityTool: path.join(repo, "components/annotator/src/STS2HumanAnnotator.Tool/bin/Release/net9.0/sts2-human-annotator.dll") });
    assert.deepEqual(verified.provenance.source, p.source, "producer_drift");
    assert.deepEqual(verified.actual, p.artifact, "artifact_drift");
    assert.deepEqual(verified.provenance.game, p.game, "game_identity_drift");
    assert.equal(verified.provenance.platform, p.build_platform);
    assert.equal(verified.provenance.architecture, p.build_architecture);
    assert.equal(verified.manifest.version, p.game_mod_version);
    assert.deepEqual(inventory(source, PAYLOAD), p.proposed_payload);
    await run("workshop:stage", repo, ["--", "--source", source, "--provenance-sha256", approvedProvenanceSha256]);
    validateInputs();
    verifyWorkspace(repo, true);
    const stagingBytes = regularFile(path.join(workspace, "staging-receipt.json"));
    const staging = readJson(stagingBytes);
    assert.deepEqual(staging, {
      schema: "spireagent/workshop-stage-1", result: "staged_candidate",
      workspace_revision: current.platform.workspace_revision, producer_workspace_revision: p.workspace_revision,
      source: p.source, game_mod_version: p.game_mod_version, source_artifact: path.join(source, PAYLOAD[0]),
      artifact: p.artifact, provenance_sha256: approvedProvenanceSha256, manifest_sha256: p.manifest_sha256,
      game: p.game, build_platform: p.build_platform, build_architecture: p.build_architecture,
      inventory: p.proposed_payload, excluded_build_files: verified.entries.filter((name) => !PAYLOAD.includes(name)),
      evidence_level: "byte_preserving_staging_only"
    }, "staging_receipt_mismatch");
    assert.deepEqual(inventory(path.join(workspace, "content"), PAYLOAD), p.proposed_payload, "staged_hash_mismatch");
    for (const name of PAYLOAD) assert.ok(regularFile(path.join(source, name)).equals(regularFile(path.join(workspace, "content", name))), "staged_bytes_mismatch");
    const receipt = {
      schema: "spireagent/workshop-prepare-1", result: "PREPARED_CANDIDATE",
      evidence_level: "approved_byte_preserving_workshop_candidate_only",
      producer_workspace_revision: p.workspace_revision, prepare_workspace_revision: current.platform.workspace_revision,
      orchestration_changed_paths: evolution, source: p.source,
      proposal_sha256: sha256(proposalBytes), approved_provenance_sha256: approvedProvenanceSha256,
      artifact: p.artifact, manifest_sha256: p.manifest_sha256, metadata_sha256: p.metadata_sha256,
      game_mod_version: p.game_mod_version, game: p.game, build_platform: p.build_platform,
      build_architecture: p.build_architecture, inventory: p.proposed_payload,
      staging_receipt_schema: staging.schema, staging_receipt_sha256: sha256(stagingBytes)
    };
    fs.writeFileSync(prepared, `${JSON.stringify(receipt, null, 2)}\n`, { flag: "wx" });
    return receipt;
  } catch (error) {
    if (fs.existsSync(prepared)) { regularFile(prepared); fs.unlinkSync(prepared); }
    throw error;
  } finally {
    fs.closeSync(lock);
    fs.unlinkSync(lockPath);
  }
}
