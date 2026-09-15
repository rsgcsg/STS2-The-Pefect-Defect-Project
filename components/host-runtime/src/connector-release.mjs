import { spawnSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  writeFileSync
} from "node:fs";
import path from "node:path";
import { sha256File } from "./game-installation.mjs";

export const CONNECTOR_RELEASE = Object.freeze({
  version: "1.2.0-rc.5",
  protocol: "1.0.0",
  sourceRevision: "d0b4a3feab7fc707adf8a4e8fc22881564748f92",
  artifactSha256: "8bf01c6818127a9e4febc870b058945742e33e6152d1a946105dd4a76ac3976f",
  artifactMvid: "9476e499-efe8-4167-9614-8c66322677b7",
  archive: "STS2-Connector-1.2.0-rc.5-host.tar.gz",
  archiveSha256: "a0bc1985995806a93498949b213972504d73c2f4b8d52f299c1356ecec34b908",
  baseUrl: "https://github.com/rsgcsg/STS2-The-Pefect-Defect-Project/releases/download/compat/platform-import-v1"
});

export function assertConnectorReleaseIdentity(identity, release = CONNECTOR_RELEASE) {
  const expected = {
    source_revision: release.sourceRevision,
    source_protocol: release.protocol,
    artifact_sha256: release.artifactSha256,
    artifact_mvid: release.artifactMvid
  };
  const errors = Object.entries(expected)
    .filter(([key, value]) => identity?.[key] !== value)
    .map(([key, value]) => `${key}: expected ${value}, got ${identity?.[key] ?? "missing"}`);
  if (errors.length > 0) {
    throw new Error(`Connector release identity mismatch: ${errors.join("; ")}`);
  }
  return identity;
}

function connectorModsDirectory(installation, platform = process.platform) {
  if (platform === "darwin") {
    return path.join(installation.executable_cwd, "mods");
  }
  return path.join(installation.game_dir, "mods");
}

async function download(url, destination) {
  const response = await fetch(url, { redirect: "follow" });
  if (!response.ok) throw new Error(`Download failed (${response.status}): ${url}`);
  writeFileSync(destination, Buffer.from(await response.arrayBuffer()));
}

function extractArchive(archive, destination) {
  mkdirSync(destination, { recursive: true });
  const result = spawnSync("tar", ["-xzf", archive, "-C", destination], {
    encoding: "utf8",
    stdio: "pipe"
  });
  if (result.status !== 0) {
    throw new Error(`Could not extract Connector release: ${result.stderr || result.stdout}`);
  }
}

function runInstaller(releaseRoot, args) {
  const installer = path.join(releaseRoot, "tools", "install-release.mjs");
  const result = spawnSync(process.execPath, [installer, ...args], {
    cwd: releaseRoot,
    encoding: "utf8",
    stdio: "pipe"
  });
  if (result.status !== 0) {
    throw new Error(`Connector installer failed: ${result.stderr || result.stdout}`);
  }
  return JSON.parse(result.stdout);
}

export async function installConnectorRelease({ installation, localRoot }) {
  const releaseRoot = path.join(localRoot, `connector-${CONNECTOR_RELEASE.version}`);
  const archive = path.join(localRoot, CONNECTOR_RELEASE.archive);
  mkdirSync(localRoot, { recursive: true });
  if (!existsSync(archive)) {
    await download(`${CONNECTOR_RELEASE.baseUrl}/${CONNECTOR_RELEASE.archive}`, archive);
  }
  const archiveSha = sha256File(archive);
  if (archiveSha !== CONNECTOR_RELEASE.archiveSha256) {
    throw new Error(
      `Connector archive checksum mismatch: expected ${CONNECTOR_RELEASE.archiveSha256}, got ${archiveSha}`
    );
  }
  if (!existsSync(path.join(releaseRoot, "payload", "STS2_MCP.dll"))) {
    extractArchive(archive, releaseRoot);
  }
  const payloadDll = path.join(releaseRoot, "payload", "STS2_MCP.dll");
  const payloadIdentity = assertConnectorReleaseIdentity(JSON.parse(readFileSync(
    path.join(releaseRoot, "payload", "build-identity.json"),
    "utf8"
  )));
  if (sha256File(payloadDll) !== payloadIdentity.artifact_sha256) {
    throw new Error("Connector release payload does not match its exact build identity");
  }
  const installedDll = path.join(connectorModsDirectory(installation), "STS2_MCP.dll");
  const expectedSha = sha256File(payloadDll);
  const installedSha = sha256File(installedDll);
  if (expectedSha && installedSha === expectedSha) {
    return {
      status: "already_installed",
      connector_version: CONNECTOR_RELEASE.version,
      protocol: CONNECTOR_RELEASE.protocol,
      source_revision: CONNECTOR_RELEASE.sourceRevision,
      artifact_mvid: CONNECTOR_RELEASE.artifactMvid,
      installed_sha256: installedSha,
      rollback_backup: null,
      loaded: "non_claim"
    };
  }
  return {
    connector_version: CONNECTOR_RELEASE.version,
    protocol: CONNECTOR_RELEASE.protocol,
    source_revision: CONNECTOR_RELEASE.sourceRevision,
    artifact_mvid: CONNECTOR_RELEASE.artifactMvid,
    ...runInstaller(releaseRoot, ["--game-dir", installation.game_dir])
  };
}

export function rollbackConnectorRelease({ backup, localRoot }) {
  const releaseRoot = path.join(localRoot, `connector-${CONNECTOR_RELEASE.version}`);
  if (!existsSync(path.join(releaseRoot, "tools", "install-release.mjs"))) {
    throw new Error("Connector release tools are unavailable; run setup first.");
  }
  return runInstaller(releaseRoot, ["--rollback", path.resolve(backup)]);
}

export function writeInstallationRecord(file, result) {
  mkdirSync(path.dirname(file), { recursive: true });
  writeFileSync(file, `${JSON.stringify(result, null, 2)}\n`);
}

export function readInstallationRecord(file) {
  return existsSync(file) ? JSON.parse(readFileSync(file, "utf8")) : null;
}
