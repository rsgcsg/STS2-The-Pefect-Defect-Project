import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { parseArgs } from "node:util";
import { fileURLToPath } from "node:url";
import { sourceSetIdentity } from "../apps/game-mod/source-identity.mjs";
import { loadHostRuntimeWorkstationApi, resolveWorkstationInstallation }
  from "../components/annotator/tools/workstation-platform.mjs";
import { PAYLOAD, inspectWorkshopBuild, regularFile, safePath, sha256 } from "./workshop-stage.mjs";
import { finalizeWorkshop } from "./workshop-finalize.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const CHECKS = Object.freeze(["check:repository", "game-mod:check"]);

export function runOwner(script, repo, args = []) {
  // npm supplies its actual CLI path on both Windows and POSIX. No shell quoting,
  // npm.cmd execution, command interpolation, or independent build command.
  assert.ok(process.env.npm_execpath, "invoke_via_npm_run_workshop_prepare");
  const result = spawnSync(process.execPath, [process.env.npm_execpath, "run", script, ...args], {
    cwd: repo, stdio: "inherit", windowsHide: true
  });
  if (result.error || result.status !== 0) throw new Error(`owner_failed:${script}:${result.error?.message ?? result.status}`);
}

export async function exactBuildPreflight(repo) {
  const host = await loadHostRuntimeWorkstationApi(path.join(repo, "components/annotator"));
  assert.ok(host, "host_workstation_owner_unavailable");
  assert.equal(host.listGameProcesses(process.platform, { failClosed: true }).length, 0,
    "STS2_RUNNING_CLOSE_MANUALLY");
  const installation = resolveWorkstationInstallation({ headlessApi: host });
  for (const file of [installation.executable, installation.release_info,
    ...["sts2.dll", "GodotSharp.dll", "0Harmony.dll"].map((name) => path.join(installation.data_dir, name))]) {
    assert.ok(fs.statSync(file).isFile(), "exact_game_input_missing");
  }
}

function metadata(repo) {
  return Object.fromEntries(["workshop.json", "image.png"].map((name) =>
    [name, sha256(regularFile(path.join(repo, "workshop", name)))]));
}

// Injection is for portable orchestration tests only; production has no bypass flags.
export async function proposeWorkshopBuild({ repositoryRoot = root, run = runOwner,
  preflight = exactBuildPreflight, readSource = sourceSetIdentity, inspect = inspectWorkshopBuild } = {}) {
  const repo = safePath(repositoryRoot);
  const workspace = safePath(path.join(repo, "workshop"));
  const proposalPath = safePath(path.join(workspace, "build-proposal.json"));
  const lockPath = safePath(path.join(workspace, ".prepare.lock"));
  const lock = fs.openSync(lockPath, "wx");
  try {
    const prepared = safePath(path.join(workspace, "prepare-receipt.json"));
    if (fs.existsSync(prepared)) { regularFile(prepared); fs.unlinkSync(prepared); }
    // Invalidate only this owner's previous proposal, never staging/raw evidence.
    if (fs.existsSync(proposalPath)) { regularFile(proposalPath); fs.unlinkSync(proposalPath); }
    const source = readSource(repo);
    assert.match(source.platform.workspace_revision, /^[0-9a-f]{40}$/u, "committed_source_required");
    assert.equal(source.platform.workspace_worktree_status, "clean", "current_source_dirty");
    const listing = metadata(repo);
    await preflight(repo);
    for (const check of CHECKS) await run(check, repo);
    // Checks may take time: recheck stopped game and exact source before build.
    await preflight(repo);
    assert.deepEqual(readSource(repo), source, "source_changed_before_build");
    await run("game-mod:build", repo);
    const sourceDirectory = path.join(repo, "apps/game-mod/bin/Release/net9.0");
    const inspected = inspect({ repositoryRoot: repo, sourceDirectory, readSource,
      identityTool: path.join(repo, "components/annotator/src/STS2HumanAnnotator.Tool/bin/Release/net9.0/sts2-human-annotator.dll") });
    const { provenance, provenanceBytes, manifestBytes, manifest, bytes, actual, current, entries } = inspected;
    assert.deepEqual(current, source, "source_changed_during_build");
    assert.deepEqual(provenance.source, source, "build_producer_not_current_workspace");
    assert.deepEqual(metadata(repo), listing, "workshop_metadata_changed");
    assert.deepEqual(readSource(repo), source, "source_changed_after_inspection");
    const inventory = (names) => names.map((name) => {
      const data = regularFile(path.join(sourceDirectory, name));
      if (bytes[name]) assert.ok(data.equals(bytes[name]), "artifact_changed_after_inspection");
      if (name === "build-provenance.json") assert.ok(data.equals(provenanceBytes), "provenance_changed_after_inspection");
      return { name, size_bytes: data.length, sha256: sha256(data) };
    });
    const proposal = {
      schema: "spireagent/workshop-build-proposal-1", result: "AWAITING_APPROVAL",
      approved: false, evidence_level: "checked_build_proposal_only",
      workspace_revision: source.platform.workspace_revision, source,
      source_directory: sourceDirectory, game_mod_version: manifest.version,
      game: provenance.game, build_platform: provenance.platform, build_architecture: provenance.architecture,
      artifact: actual, manifest_sha256: sha256(manifestBytes),
      provenance_sha256: sha256(provenanceBytes), metadata_sha256: listing,
      proposed_payload: inventory(PAYLOAD), build_inventory: inventory(entries), checks: [...CHECKS]
    };
    assert.deepEqual(fs.readdirSync(sourceDirectory).sort(), entries, "build_inventory_changed_after_inspection");
    // Exclusive creation; partial write is removed on ordinary failure. A later
    // consumer must validate the full schema/hashes, never trust mere existence.
    fs.writeFileSync(proposalPath, `${JSON.stringify(proposal, null, 2)}\n`, { flag: "wx" });
    return proposal;
  } catch (error) {
    if (fs.existsSync(proposalPath)) { regularFile(proposalPath); fs.unlinkSync(proposalPath); }
    throw error;
  } finally {
    fs.closeSync(lock);
    fs.unlinkSync(lockPath);
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const { values } = parseArgs({ options: { build: { type: "boolean" },
      "approve-provenance-sha256": { type: "string" } }, strict: true, allowPositionals: false });
    assert.ok(Boolean(values.build) !== Boolean(values["approve-provenance-sha256"]), "select_exactly_one_phase");
    const result = values.build ? await proposeWorkshopBuild()
      : await finalizeWorkshop({ repositoryRoot: root, approvedProvenanceSha256: values["approve-provenance-sha256"], run: runOwner });
    console.log(JSON.stringify(result, null, 2));
  } catch (error) {
    console.error(`Workshop proposal failed: ${error.message}`);
    process.exitCode = 1;
  }
}
