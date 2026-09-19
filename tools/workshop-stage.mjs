import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { sourceSetIdentity, sourceSetMatches } from "../apps/game-mod/source-identity.mjs";
import { publicAssemblyIdentity } from "../apps/game-mod/public-provenance.mjs";

export const PAYLOAD = Object.freeze(["STS2_PLATFORM.dll", "STS2_PLATFORM.json"]);
const SIDECARS = ["STS2_PLATFORM.deps.json", "STS2_PLATFORM.pdb"];
const PROVENANCE = "build-provenance.json";
const SHA = /^[0-9a-f]{64}$/u;
const REV = /^[0-9a-f]{40}$/u;
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const sha256 = (bytes) => crypto.createHash("sha256").update(bytes).digest("hex");
const json = (bytes) => JSON.parse(bytes.toString("utf8").replace(/^\uFEFF/u, ""));

// No caller-supplied recursive deletion target. Check every existing ancestor,
// including Windows junctions; filenames from provenance never become paths.
export function safePath(target) {
  const absolute = path.resolve(target);
  let current = path.parse(absolute).root;
  for (const part of absolute.slice(current.length).split(path.sep).filter(Boolean)) {
    current = path.join(current, part);
    const stat = fs.lstatSync(current, { throwIfNoEntry: false });
    if (stat?.isSymbolicLink()) throw new Error(`symlink_or_junction: ${current}`);
  }
  return absolute;
}

export function regularFile(file) {
  safePath(file);
  const stat = fs.lstatSync(file);
  assert.ok(stat.isFile() && stat.nlink === 1, `regular_unlinked_file_required: ${file}`);
  return fs.readFileSync(file);
}

function inspectTree(directory) {
  safePath(directory);
  const stat = fs.lstatSync(directory, { throwIfNoEntry: false });
  if (!stat) return;
  assert.ok(stat.isDirectory(), `directory_required: ${directory}`);
  for (const entry of fs.readdirSync(directory)) {
    const file = path.join(directory, entry);
    const child = fs.lstatSync(file);
    assert.ok(!child.isSymbolicLink(), `symlink_or_junction: ${file}`);
    if (child.isDirectory()) inspectTree(file);
    else assert.ok(child.isFile() && child.nlink === 1, `regular_unlinked_file_required: ${file}`);
  }
}

function overlaps(left, right) {
  const inside = (a, b) => {
    const relative = path.relative(a, b);
    return relative === "" || (!relative.startsWith(`..${path.sep}`)
      && relative !== ".." && !path.isAbsolute(relative));
  };
  return inside(left, right) || inside(right, left);
}

export function assemblyIdentity(tool, file) {
  regularFile(tool);
  // Existing owner reads PE metadata; it does not execute the candidate DLL.
  return publicAssemblyIdentity(json(execFileSync("dotnet", [tool, "identity", file], {
    encoding: "buffer", timeout: 30_000, maxBuffer: 1024 * 1024,
    stdio: ["ignore", "pipe", "pipe"]
  })));
}

function validateProvenance(provenance, current, manifest, actual, dll) {
  assert.equal(provenance.schema, "sts2.platform/game-mod-build-provenance-1", "unknown_provenance_schema");
  assert.equal(current.platform.workspace_worktree_status, "clean", "current_source_dirty");
  assert.equal(provenance.source?.platform?.workspace_worktree_status, "clean", "producer_source_dirty");
  assert.match(provenance.source?.platform?.workspace_revision ?? "", REV, "missing_producer_revision");
  assert.deepEqual(Object.keys(provenance.source?.components ?? {}).sort(), Object.keys(current.components).sort(),
    "unknown_or_missing_component");
  for (const value of Object.values(provenance.source.components)) {
    assert.match(value.source_revision ?? "", REV);
    assert.match(value.source_digest_sha256 ?? "", SHA);
    assert.equal(value.component_worktree_status, "clean", "producer_component_dirty");
  }
  assert.ok(sourceSetMatches(provenance.source, current), "stale_source_identity");
  assert.deepEqual(provenance.package?.files, PAYLOAD, "unexpected_payload_inventory");
  assert.deepEqual(provenance.package?.manifest, manifest, "provenance_manifest_mismatch");
  assert.deepEqual(publicAssemblyIdentity(provenance.artifact), publicAssemblyIdentity(actual), "artifact_identity_mismatch");
  assert.equal(sha256(dll), actual.sha256, "artifact_hash_mismatch");
  publicAssemblyIdentity(provenance.game?.sts2);
  assert.match(provenance.game?.godotsharp_sha256 ?? "", SHA);
  assert.match(provenance.game?.harmony_sha256 ?? "", SHA);
  for (const field of ["version", "commit"]) {
    assert.ok(typeof provenance.game?.release?.[field] === "string" && provenance.game.release[field], "missing_game_release");
  }
  assert.ok(["win32", "linux", "darwin"].includes(provenance.platform), "unknown_build_platform");
  assert.ok(["x64", "arm64"].includes(provenance.architecture), "unknown_build_architecture");
  assert.ok(Number.isFinite(Date.parse(provenance.built_at)), "missing_build_time");
}

// Shared read-only inspection: computing the digest is NOT approval or staging.
export function inspectWorkshopBuild({ repositoryRoot = root, sourceDirectory, identityTool,
  readIdentity = assemblyIdentity, readSource = sourceSetIdentity }) {
  const repo = safePath(repositoryRoot);
  const source = safePath(sourceDirectory);
  assert.ok(fs.statSync(source).isDirectory(), "source_directory_required");
  const entries = fs.readdirSync(source).sort();
  const expected = [...PAYLOAD, PROVENANCE];
  for (const name of entries) {
    assert.ok([...expected, ...SIDECARS].includes(name), `unexpected_build_file: ${name}`);
    regularFile(path.join(source, name));
  }
  for (const name of expected) assert.ok(entries.includes(name), `missing_build_file: ${name}`);
  const provenanceBytes = regularFile(path.join(source, PROVENANCE));
  const provenance = json(provenanceBytes);
  const manifestBytes = regularFile(path.join(repo, "apps/game-mod/mod_manifest.json"));
  const manifest = json(manifestBytes);
  const bytes = Object.fromEntries(PAYLOAD.map((name) => [name, regularFile(path.join(source, name))]));
  assert.ok(bytes[PAYLOAD[1]].equals(manifestBytes), "runtime_manifest_bytes_mismatch");
  assert.equal(manifest.id, "STS2_PLATFORM");
  assert.equal(manifest.has_dll, true);
  assert.equal(manifest.has_pck, false);
  const current = readSource(repo);
  const actual = readIdentity(identityTool, path.join(source, PAYLOAD[0]));
  validateProvenance(provenance, current, manifest, actual, bytes[PAYLOAD[0]]);
  return { entries, provenanceBytes, provenance, manifestBytes, manifest, bytes, current, actual };
}

// The injected readers support portable mechanics fixtures only. The CLI always
// uses the current game-mod source owner and the existing .NET PE identity owner.
export function stageWorkshop({ repositoryRoot = root, sourceDirectory, approvedProvenanceSha256,
  identityTool, readIdentity = assemblyIdentity, readSource = sourceSetIdentity }) {
  assert.match(approvedProvenanceSha256 ?? "", SHA, "explicit_approved_provenance_sha256_required");
  assert.ok(typeof sourceDirectory === "string" && sourceDirectory.length, "explicit_source_required");
  const repo = safePath(repositoryRoot);
  const workspace = safePath(path.join(repo, "workshop"));
  assert.ok(fs.statSync(workspace).isDirectory());
  const source = safePath(sourceDirectory);
  assert.ok(!overlaps(source, workspace), "source_workshop_overlap");
  const content = path.join(workspace, "content");
  const receiptPath = path.join(workspace, "staging-receipt.json");
  const lock = path.join(workspace, ".stage.lock");
  safePath(lock);
  const lockFd = fs.openSync(lock, "wx");
  let temporary;
  try {
    // Validate exact generated targets before removal, never follow links.
    inspectTree(content);
    if (fs.existsSync(receiptPath)) regularFile(receiptPath);
    fs.rmSync(receiptPath, { force: true });
    fs.rmSync(content, { recursive: true, force: true });
    // Approval remains mandatory before inspecting/executing the PE reader.
    if (fs.existsSync(path.join(source, PROVENANCE))) {
      assert.equal(sha256(regularFile(path.join(source, PROVENANCE))), approvedProvenanceSha256,
        "approved_provenance_hash_mismatch");
    }
    const { entries, provenanceBytes, provenance, manifestBytes, manifest, bytes, current, actual }
      = inspectWorkshopBuild({ repositoryRoot: repo, sourceDirectory: source, identityTool, readIdentity, readSource });
    assert.equal(sha256(provenanceBytes), approvedProvenanceSha256, "approved_provenance_hash_mismatch");
    temporary = fs.mkdtempSync(path.join(workspace, ".stage-"));
    const inventory = PAYLOAD.map((name) => {
      const destination = path.join(temporary, name);
      fs.writeFileSync(destination, bytes[name], { flag: "wx" });
      const staged = regularFile(destination);
      assert.ok(staged.equals(bytes[name]), `staged_bytes_mismatch: ${name}`);
      assert.equal(sha256(staged), sha256(bytes[name]), `staged_hash_mismatch: ${name}`);
      return { name, size_bytes: staged.length, sha256: sha256(staged) };
    });
    assert.deepEqual(fs.readdirSync(temporary).sort(), [...PAYLOAD].sort());
    // Detect concurrent input changes before accepting the candidate.
    for (const name of [...PAYLOAD, PROVENANCE]) {
      assert.ok(regularFile(path.join(source, name)).equals(name === PROVENANCE ? provenanceBytes : bytes[name]),
        `source_changed_during_staging: ${name}`);
    }
    assert.deepEqual(fs.readdirSync(source).sort(), entries, "source_inventory_changed");
    assert.ok(regularFile(path.join(repo, "apps/game-mod/mod_manifest.json")).equals(manifestBytes), "authority_changed");
    assert.deepEqual(readSource(repo), current, "source_identity_changed");
    const receipt = {
      schema: "spireagent/workshop-stage-1", result: "staged_candidate",
      workspace_revision: current.platform.workspace_revision,
      producer_workspace_revision: provenance.source.platform.workspace_revision,
      source: provenance.source, game_mod_version: manifest.version,
      source_artifact: path.join(source, PAYLOAD[0]),
      artifact: publicAssemblyIdentity(actual),
      provenance_sha256: approvedProvenanceSha256, manifest_sha256: sha256(manifestBytes),
      game: provenance.game, build_platform: provenance.platform, build_architecture: provenance.architecture,
      inventory, excluded_build_files: entries.filter((name) => !PAYLOAD.includes(name)),
      evidence_level: "byte_preserving_staging_only"
    };
    fs.renameSync(temporary, content);
    temporary = undefined;
    try {
      fs.writeFileSync(receiptPath, `${JSON.stringify(receipt, null, 2)}\n`, { flag: "wx" });
    } catch (error) {
      inspectTree(content);
      fs.rmSync(content, { recursive: true, force: true });
      fs.rmSync(receiptPath, { force: true });
      throw error;
    }
    return receipt;
  } finally {
    if (temporary) {
      inspectTree(temporary);
      fs.rmSync(temporary, { recursive: true, force: true });
    }
    fs.closeSync(lockFd);
    fs.unlinkSync(lock);
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const { values } = parseArgs({ options: {
      source: { type: "string" }, "provenance-sha256": { type: "string" },
      "identity-tool": { type: "string" }
    }, allowPositionals: false, strict: true });
    const receipt = stageWorkshop({
      sourceDirectory: values.source, approvedProvenanceSha256: values["provenance-sha256"],
      identityTool: values["identity-tool"] ?? path.join(root,
        "components/annotator/src/STS2HumanAnnotator.Tool/bin/Release/net9.0/sts2-human-annotator.dll")
    });
    console.log(JSON.stringify(receipt, null, 2));
  } catch (error) {
    console.error(`Workshop staging failed: ${error.message}`);
    process.exitCode = 1;
  }
}
