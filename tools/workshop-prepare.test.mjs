import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { spawnSync, execFileSync } from "node:child_process";
import { proposeWorkshopBuild, CHECKS } from "./workshop-prepare.mjs";
import { inspectWorkshopBuild, sha256, stageWorkshop } from "./workshop-stage.mjs";
import { finalizeWorkshop, verifyToolEvolution } from "./workshop-finalize.mjs";

const root = path.resolve(import.meta.dirname, "..");
function fixture(t) {
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), "prepare space-"));
  t.after(() => fs.rmSync(repo, { recursive: true, force: true }));
  const output = path.join(repo, "apps/game-mod/bin/Release/net9.0");
  fs.mkdirSync(output, { recursive: true });
  fs.mkdirSync(path.join(repo, "workshop"));
  for (const name of ["workshop.json", "image.png"]) fs.copyFileSync(path.join(root, "workshop", name), path.join(repo, "workshop", name));
  const manifest = fs.readFileSync(path.join(root, "apps/game-mod/mod_manifest.json"));
  fs.writeFileSync(path.join(repo, "apps/game-mod/mod_manifest.json"), manifest);
  fs.writeFileSync(path.join(output, "STS2_PLATFORM.json"), manifest);
  const dll = Buffer.from("synthetic non-PE fixture only");
  fs.writeFileSync(path.join(output, "STS2_PLATFORM.dll"), dll);
  const component = { source_revision: "a".repeat(40), source_digest_sha256: "b".repeat(64), component_worktree_status: "clean" };
  const source = { platform: { ...component, workspace_revision: "c".repeat(40), workspace_worktree_status: "clean" },
    components: { fixture: { ...component } } };
  const identity = { sha256: sha256(dll), module_version_id: "12345678-1234-1234-1234-123456789abc" };
  const provenance = { schema: "sts2.platform/game-mod-build-provenance-1", built_at: "2026-09-19T00:00:00Z",
    platform: process.platform, architecture: process.arch, source: structuredClone(source), artifact: identity,
    package: { manifest: JSON.parse(manifest), files: ["STS2_PLATFORM.dll", "STS2_PLATFORM.json"] },
    game: { release: { version: "fixture", commit: "fixture" }, sts2: identity,
      godotsharp_sha256: "d".repeat(64), harmony_sha256: "e".repeat(64) } };
  const seal = () => fs.writeFileSync(path.join(output, "build-provenance.json"), JSON.stringify(provenance));
  seal();
  const calls = [];
  const options = { repositoryRoot: repo, readSource: () => structuredClone(source),
    preflight: async () => { calls.push("preflight"); }, run: async (script) => { calls.push(script); },
    inspect: (args) => inspectWorkshopBuild({ ...args, readIdentity: () => identity }) };
  return { repo, output, source, provenance, identity, seal, calls, options,
    proposal: path.join(repo, "workshop/build-proposal.json") };
}

test("Phase A invokes existing checks/build and only writes an unapproved proposal", async (t) => {
  const f = fixture(t);
  const result = await proposeWorkshopBuild(f.options);
  assert.deepEqual(f.calls, ["preflight", ...CHECKS, "preflight", "game-mod:build"]);
  assert.equal(result.result, "AWAITING_APPROVAL");
  assert.equal(result.approved, false);
  assert.deepEqual(result.source, f.source);
  assert.equal(result.provenance_sha256, sha256(fs.readFileSync(path.join(f.output, "build-provenance.json"))));
  assert.deepEqual(result.proposed_payload.map((item) => item.name), ["STS2_PLATFORM.dll", "STS2_PLATFORM.json"]);
  for (const item of result.proposed_payload) assert.equal(item.sha256, sha256(fs.readFileSync(path.join(f.output, item.name))));
  assert.deepEqual(JSON.parse(fs.readFileSync(f.proposal)), result);
  assert.deepEqual(fs.readdirSync(path.join(f.repo, "workshop")).sort(), ["build-proposal.json", "image.png", "workshop.json"]);
});

for (const failure of ["dirty", "running", "discovery", ...CHECKS, "game-mod:build", "metadata", "source", "provenance", "extra"]) {
  test(`${failure} fails closed and invalidates previous proposal`, async (t) => {
    const f = fixture(t);
    fs.writeFileSync(f.proposal, "old proposal");
    if (failure === "dirty") f.source.platform.workspace_worktree_status = "dirty";
    if (["running", "discovery"].includes(failure)) f.options.preflight = async () => { throw new Error(failure); };
    f.options.run = async (script) => {
      f.calls.push(script);
      if (failure === script) throw new Error(`failed ${script}`);
      if (script !== "game-mod:build") return;
      if (failure === "metadata") fs.appendFileSync(path.join(f.repo, "workshop/workshop.json"), " ");
      if (failure === "source") f.source.platform.workspace_revision = "d".repeat(40);
      if (failure === "provenance") { f.provenance.artifact.sha256 = "f".repeat(64); f.seal(); }
      if (failure === "extra") fs.writeFileSync(path.join(f.output, "sts2.dll"), "forbidden");
    };
    await assert.rejects(proposeWorkshopBuild(f.options));
    assert.ok(!fs.existsSync(f.proposal));
    assert.ok(!fs.existsSync(path.join(f.repo, "workshop/content")));
    assert.ok(!fs.existsSync(path.join(f.repo, "workshop/.prepare.lock")));
  });
}

test("source changes during checks block build; game rechecked before build", async (t) => {
  const f = fixture(t);
  f.options.run = async (script) => { f.calls.push(script); f.source.platform.workspace_revision = "e".repeat(40); };
  await assert.rejects(proposeWorkshopBuild(f.options), /source_changed_before_build/);
  assert.ok(!f.calls.includes("game-mod:build"));
  assert.equal(f.calls.filter((call) => call === "preflight").length, 2);
});

test("proposal never modifies an existing Layer 2 candidate or receipt", async (t) => {
  const f = fixture(t);
  fs.mkdirSync(path.join(f.repo, "workshop/content"));
  fs.writeFileSync(path.join(f.repo, "workshop/content/retained"), "old bytes");
  fs.writeFileSync(path.join(f.repo, "workshop/staging-receipt.json"), "old receipt");
  await proposeWorkshopBuild(f.options);
  assert.equal(fs.readFileSync(path.join(f.repo, "workshop/content/retained"), "utf8"), "old bytes");
  assert.equal(fs.readFileSync(path.join(f.repo, "workshop/staging-receipt.json"), "utf8"), "old receipt");
});

test("concurrent/interrupted lock fails closed without overwriting prior state", async (t) => {
  const f = fixture(t);
  fs.writeFileSync(path.join(f.repo, "workshop/.prepare.lock"), "");
  await assert.rejects(proposeWorkshopBuild(f.options), /EEXIST/);
  assert.equal(f.calls.length, 0);
  assert.ok(!fs.existsSync(f.proposal));
});

test("native/forward slash paths with spaces produce identical proposal", async (t) => {
  const f = fixture(t);
  const first = await proposeWorkshopBuild(f.options);
  const next = await proposeWorkshopBuild({ ...f.options, repositoryRoot: f.repo.replaceAll("\\", "/") });
  assert.deepEqual(next, first);
});

test("production CLI rejects implicit/both phases and fixture bypass flags", () => {
  for (const args of [[], ["--build", "--approve-provenance-sha256", "a".repeat(64)], ["--build", "--fixture"]]) {
    const result = spawnSync(process.execPath, [path.join(root, "tools/workshop-prepare.mjs"), ...args], { encoding: "utf8" });
    assert.equal(result.status, 1);
    assert.match(result.stderr, /Workshop proposal failed/);
  }
});

async function approvedFixture(t) {
  const f = fixture(t);
  const proposal = await proposeWorkshopBuild(f.options);
  f.calls.length = 0;
  const stage = () => stageWorkshop({ repositoryRoot: f.repo, sourceDirectory: f.output,
    approvedProvenanceSha256: proposal.provenance_sha256,
    readSource: f.options.readSource, readIdentity: () => f.identity });
  const options = { repositoryRoot: f.repo, approvedProvenanceSha256: proposal.provenance_sha256,
    readSource: f.options.readSource, inspect: f.options.inspect, verifyEvolution: () => [],
    run: async (script, repo, args) => {
      f.calls.push(script);
      assert.equal(script, "workshop:stage");
      assert.equal(repo, f.repo);
      assert.deepEqual(args, ["--", "--source", f.output, "--provenance-sha256", proposal.provenance_sha256]);
      stage();
    } };
  return { ...f, proposalData: proposal, finalizeOptions: options, stage,
    prepared: path.join(f.repo, "workshop/prepare-receipt.json") };
}

test("Phase B invokes only existing staging, binds receipt and never changes proposal/build", async (t) => {
  const f = await approvedFixture(t);
  const proposalBytes = fs.readFileSync(f.proposal);
  const result = await finalizeWorkshop(f.finalizeOptions);
  assert.equal(result.result, "PREPARED_CANDIDATE");
  assert.deepEqual(f.calls, ["workshop:stage"]);
  assert.deepEqual(fs.readFileSync(f.proposal), proposalBytes);
  assert.equal(result.proposal_sha256, sha256(proposalBytes));
  assert.equal(result.staging_receipt_sha256, sha256(fs.readFileSync(path.join(f.repo, "workshop/staging-receipt.json"))));
  assert.deepEqual(result.inventory, f.proposalData.proposed_payload);
  assert.deepEqual(JSON.parse(fs.readFileSync(f.prepared)), result);
  assert.deepEqual(await finalizeWorkshop(f.finalizeOptions), result);
});

for (const fault of ["pin", "dirty", "source", "dll", "provenance", "sidecar", "metadata", "image",
  "extra-workspace", "extra-payload", "stage-failure", "receipt", "staged-bytes", "proposal-during-stage"]) {
  test(`Phase B ${fault} cannot emit success or rebuild`, async (t) => {
    const f = await approvedFixture(t);
    fs.writeFileSync(f.prepared, "old success");
    if (fault === "pin") f.finalizeOptions.approvedProvenanceSha256 = "0".repeat(64);
    if (fault === "dirty") f.source.platform.workspace_worktree_status = "dirty";
    if (fault === "source") f.source.components.fixture.source_revision = "f".repeat(40);
    if (fault === "dll") fs.appendFileSync(path.join(f.output, "STS2_PLATFORM.dll"), "tamper");
    if (fault === "provenance") fs.appendFileSync(path.join(f.output, "build-provenance.json"), " ");
    if (fault === "sidecar") fs.writeFileSync(path.join(f.output, "STS2_PLATFORM.pdb"), "new sidecar");
    if (fault === "metadata") fs.appendFileSync(path.join(f.repo, "workshop/workshop.json"), " ");
    if (fault === "image") fs.appendFileSync(path.join(f.repo, "workshop/image.png"), "tamper");
    if (fault === "extra-workspace") fs.writeFileSync(path.join(f.repo, "workshop/mod_id.txt"), "forbidden");
    f.finalizeOptions.run = async (script) => {
      assert.equal(script, "workshop:stage");
      if (fault === "stage-failure") throw new Error("stage failed");
      f.stage();
      if (fault === "extra-payload") fs.writeFileSync(path.join(f.repo, "workshop/content/build-provenance.json"), "forbidden");
      if (fault === "receipt") fs.writeFileSync(path.join(f.repo, "workshop/staging-receipt.json"), "{}");
      if (fault === "staged-bytes") fs.appendFileSync(path.join(f.repo, "workshop/content/STS2_PLATFORM.dll"), "tamper");
      if (fault === "proposal-during-stage") fs.appendFileSync(f.proposal, " ");
    };
    await assert.rejects(finalizeWorkshop(f.finalizeOptions));
    assert.ok(!fs.existsSync(f.prepared));
    assert.ok(!fs.existsSync(path.join(f.repo, "workshop/.prepare.lock")));
  });
}

test("Phase B records authorized orchestration HEAD separately from unchanged producer", async (t) => {
  const f = await approvedFixture(t);
  f.source.platform.workspace_revision = "d".repeat(40);
  f.finalizeOptions.verifyEvolution = () => ["tools/workshop-finalize.mjs"];
  const result = await finalizeWorkshop(f.finalizeOptions);
  assert.equal(result.producer_workspace_revision, "c".repeat(40));
  assert.equal(result.prepare_workspace_revision, "d".repeat(40));
});

test("real Git evolution allows only authorized tools/docs, rejecting unrelated changes", (t) => {
  const f = fixture(t);
  const git = (args) => execFileSync("git", args, { cwd: f.repo, encoding: "utf8" });
  git(["init", "--quiet"]);
  git(["config", "user.name", "Fixture"]); git(["config", "user.email", "fixture@example.invalid"]);
  git(["add", "."]); git(["commit", "-qm", "base"]);
  const base = git(["rev-parse", "HEAD"]).trim();
  fs.writeFileSync(path.join(f.repo, "README.md"), "tool docs");
  git(["add", "README.md"]); git(["commit", "-qm", "docs"]);
  assert.deepEqual(verifyToolEvolution(f.repo, base, git(["rev-parse", "HEAD"]).trim()), ["README.md"]);
  fs.writeFileSync(path.join(f.repo, "package.json"), "{}");
  git(["add", "package.json"]); git(["commit", "-qm", "unapproved source"]);
  assert.throws(() => verifyToolEvolution(f.repo, base, git(["rev-parse", "HEAD"]).trim()), /non_orchestration_source_drift/);
});
