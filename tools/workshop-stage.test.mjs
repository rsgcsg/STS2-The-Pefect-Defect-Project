import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { execFileSync } from "node:child_process";
import { PAYLOAD, sha256, stageWorkshop } from "./workshop-stage.mjs";

const ROOT = path.resolve(import.meta.dirname, "..");
// Synthetic non-executable bytes prove mechanics, never an exact-game artifact.
function fixture(t) {
  const parent = fs.mkdtempSync(path.join(os.tmpdir(), "workshop-stage-"));
  t.after(() => fs.rmSync(parent, { recursive: true, force: true }));
  const repo = path.join(parent, "repo with spaces");
  const source = path.join(parent, "approved output");
  fs.mkdirSync(path.join(repo, "workshop"), { recursive: true });
  fs.mkdirSync(path.join(repo, "apps/game-mod"), { recursive: true });
  fs.mkdirSync(source);
  const manifest = fs.readFileSync(path.join(ROOT, "apps/game-mod/mod_manifest.json"));
  fs.writeFileSync(path.join(repo, "apps/game-mod/mod_manifest.json"), manifest);
  fs.writeFileSync(path.join(source, PAYLOAD[1]), manifest);
  fs.writeFileSync(path.join(source, PAYLOAD[0]), Buffer.from("synthetic fixture: not a PE or qualified Mod\0\xff"));
  const component = { source_revision: "a".repeat(40), source_digest_sha256: "b".repeat(64), component_worktree_status: "clean" };
  const current = { platform: { ...component, workspace_revision: "c".repeat(40), workspace_worktree_status: "clean" },
    components: Object.fromEntries(["native_foundation", "connector", "annotator", "live_ui", "game_mod"]
      .map((name) => [name, { ...component }])) };
  const identity = { sha256: sha256(fs.readFileSync(path.join(source, PAYLOAD[0]))),
    module_version_id: "12345678-1234-1234-1234-123456789abc" };
  const provenance = { schema: "sts2.platform/game-mod-build-provenance-1",
    built_at: "2026-09-18T00:00:00Z", platform: "win32", architecture: "x64", source: structuredClone(current),
    artifact: identity, package: { files: [...PAYLOAD], manifest: JSON.parse(manifest) },
    game: { release: { version: "fixture", commit: "fixture" }, sts2: identity,
      godotsharp_sha256: "e".repeat(64), harmony_sha256: "f".repeat(64) } };
  const options = { repositoryRoot: repo, sourceDirectory: source,
    readSource: () => structuredClone(current), readIdentity: () => ({ ...identity }) };
  function seal() {
    const bytes = Buffer.from(JSON.stringify(provenance));
    fs.writeFileSync(path.join(source, "build-provenance.json"), bytes);
    options.approvedProvenanceSha256 = sha256(bytes);
  }
  seal();
  return { repo, source, options, provenance, current, identity, seal,
    content: path.join(repo, "workshop/content"), receipt: path.join(repo, "workshop/staging-receipt.json") };
}

test("valid candidate preserves bytes/hashes and deterministic inventory; sidecars stay out", (t) => {
  const f = fixture(t);
  for (const name of ["STS2_PLATFORM.pdb", "STS2_PLATFORM.deps.json"]) fs.writeFileSync(path.join(f.source, name), "build sidecar");
  const first = stageWorkshop(f.options);
  assert.deepEqual(fs.readdirSync(f.content).sort(), [...PAYLOAD].sort());
  for (const item of first.inventory) {
    const original = fs.readFileSync(path.join(f.source, item.name));
    const staged = fs.readFileSync(path.join(f.content, item.name));
    assert.deepEqual(staged, original);
    assert.equal(item.sha256, sha256(original));
  }
  assert.deepEqual(first.excluded_build_files.sort(), ["STS2_PLATFORM.deps.json", "STS2_PLATFORM.pdb", "build-provenance.json"].sort());
  const receipt = fs.readFileSync(f.receipt);
  assert.deepEqual(stageWorkshop(f.options), first);
  assert.deepEqual(fs.readFileSync(f.receipt), receipt);
});

test("stale generated files are replaced, not inherited", (t) => {
  const f = fixture(t);
  fs.mkdirSync(path.join(f.content, "obsolete"), { recursive: true });
  fs.writeFileSync(path.join(f.content, "obsolete/old.txt"), "stale");
  stageWorkshop(f.options);
  assert.deepEqual(fs.readdirSync(f.content).sort(), [...PAYLOAD].sort());
});

for (const name of [...PAYLOAD, "build-provenance.json"]) {
  test(`missing ${name} fails and invalidates old generated candidate`, (t) => {
    const f = fixture(t);
    stageWorkshop(f.options);
    fs.unlinkSync(path.join(f.source, name));
    assert.throws(() => stageWorkshop(f.options), /missing_build_file/);
    assert.ok(!fs.existsSync(f.content));
    assert.ok(!fs.existsSync(f.receipt));
  });
}

for (const name of ["unknown.dll", "sts2.dll", "GodotSharp.dll", "0Harmony.dll", "source.cs", "model.pt",
  "Qwen.safetensors", "session.json", "dataset.jsonl", "Hub.py", "train.py", "mod_id.txt", "ModUploader.exe",
  ".env", "steam_appid.txt", "upload.log", ".local", "research", "obj"]) {
  test(`non-allowlisted input rejected: ${name}`, (t) => {
    const f = fixture(t);
    fs.writeFileSync(path.join(f.source, name), "forbidden");
    assert.throws(() => stageWorkshop(f.options), /unexpected_build_file/);
    assert.ok(!fs.existsSync(f.content));
  });
}

for (const [label, mutate, pattern] of [
  ["unknown schema", (f) => { f.provenance.schema = "unknown"; }, /unknown_provenance_schema/],
  ["manifest claim", (f) => { f.provenance.package.manifest.version = "wrong"; }, /provenance_manifest_mismatch/],
  ["extra payload", (f) => { f.provenance.package.files.push("../secret"); }, /unexpected_payload_inventory/],
  ["stale source", (f) => { f.provenance.source.components.connector.source_revision = "d".repeat(40); }, /stale_source_identity/],
  ["wrong SHA", (f) => { f.provenance.artifact = { ...f.identity, sha256: "e".repeat(64) }; }, /artifact_identity_mismatch/],
  ["wrong MVID", (f) => { f.provenance.artifact = { ...f.identity, module_version_id: "87654321-1234-1234-1234-123456789abc" }; }, /artifact_identity_mismatch/],
  ["unknown component", (f) => { f.provenance.source.components.other = {}; }, /unknown_or_missing_component/],
  ["dirty producer", (f) => { f.provenance.source.platform.workspace_worktree_status = "dirty"; }, /producer_source_dirty/]
]) {
  test(`${label} fails closed even with a matching provenance pin`, (t) => {
    const f = fixture(t); mutate(f); f.seal();
    assert.throws(() => stageWorkshop(f.options), pattern);
  });
}

test("approval pin, current source, runtime manifest bytes and corrupted DLL are checked", (t) => {
  const f = fixture(t);
  assert.throws(() => stageWorkshop({ ...f.options, approvedProvenanceSha256: "e".repeat(64) }), /approved_provenance_hash_mismatch/);
  f.current.platform.workspace_worktree_status = "dirty";
  assert.throws(() => stageWorkshop(f.options), /current_source_dirty/);
  f.current.platform.workspace_worktree_status = "clean";
  const manifest = path.join(f.source, PAYLOAD[1]);
  const bytes = fs.readFileSync(manifest);
  fs.appendFileSync(manifest, " ");
  assert.throws(() => stageWorkshop(f.options), /runtime_manifest_bytes_mismatch/);
  fs.writeFileSync(manifest, bytes);
  fs.appendFileSync(path.join(f.source, PAYLOAD[0]), "corrupt");
  assert.throws(() => stageWorkshop(f.options), /artifact_hash_mismatch/);
});

test("concurrent input change or unavailable identity cannot create a candidate", (t) => {
  const f = fixture(t);
  assert.throws(() => stageWorkshop({ ...f.options, readIdentity: () => { throw new Error("PE identity unavailable"); } }), /PE identity unavailable/);
  assert.throws(() => stageWorkshop({ ...f.options, readIdentity: () => {
    fs.appendFileSync(path.join(f.source, PAYLOAD[0]), "changed");
    return f.identity;
  } }), /source_changed_during_staging/);
  assert.ok(!fs.existsSync(f.content));
  assert.ok(!fs.existsSync(f.receipt));
});

test("source/output overlap and concurrent stager are rejected without deleting data", (t) => {
  const f = fixture(t);
  const lock = path.join(f.repo, "workshop/.stage.lock");
  assert.throws(() => stageWorkshop({ ...f.options, sourceDirectory: f.repo }), /source_workshop_overlap/);
  fs.writeFileSync(lock, "another stager");
  assert.throws(() => stageWorkshop(f.options), /EEXIST/);
  assert.equal(fs.readFileSync(lock, "utf8"), "another stager");
});

test("directory links cannot redirect generated cleanup outside Workspace", (t) => {
  const f = fixture(t);
  const outside = path.join(f.source, "preserve");
  fs.mkdirSync(outside);
  fs.writeFileSync(path.join(outside, "precious"), "keep");
  fs.symlinkSync(outside, f.content, process.platform === "win32" ? "junction" : "dir");
  assert.throws(() => stageWorkshop(f.options), /symlink_or_junction/);
  assert.equal(fs.readFileSync(path.join(outside, "precious"), "utf8"), "keep");
});

test("native and forward-slash absolute paths with spaces yield the same candidate", (t) => {
  const f = fixture(t);
  const first = stageWorkshop(f.options);
  assert.deepEqual(stageWorkshop({ ...f.options, sourceDirectory: f.source.split(path.sep).join("/") }), first);
});

test("CLI requires explicit input/pin and has no build/upload fallback", () => {
  assert.throws(() => execFileSync(process.execPath, [path.join(ROOT, "tools/workshop-stage.mjs")],
    { encoding: "utf8", stdio: "pipe" }), /explicit_approved_provenance_sha256_required/);
});
