#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { cpSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { readIdentityReport } from "../../../tools/component-identity.mjs";

export const componentRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export function npm(args, cwd) {
  const npmPath = process.env.npm_execpath;
  const result = npmPath
    ? spawnSync(process.execPath, [npmPath, ...args], { cwd, encoding: "utf8" })
    : spawnSync(process.platform === "win32" ? "npm.cmd" : "npm", args, { cwd, encoding: "utf8", shell: process.platform === "win32" });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(result.stderr || result.stdout);
  return result.stdout;
}

export function packageRuntime(outputDirectory, { allowDirty = false } = {}) {
  const source = JSON.parse(readFileSync(path.join(componentRoot, "package.json"), "utf8"));
  const lock = JSON.parse(readFileSync(path.join(componentRoot, "package-lock.json"), "utf8"));
  const identity = readIdentityReport(path.resolve(componentRoot, "../.." )).components["policy-runtime"];
  if (!allowDirty && identity.source_worktree_status !== "clean") throw new Error("Commit Policy Runtime source before creating an external candidate package");
  const sdkName = "@rsgcsg/sts2-connector-client";
  const sdk = lock.packages[`node_modules/${sdkName}`];
  if (source.dependencies[sdkName] !== sdk?.resolved || !/^https:\/\/github\.com\/rsgcsg\/STS2-The-Pefect-Defect-Project\/releases\/download\/compat\/platform-import-v1\/rsgcsg-sts2-connector-client-[^/]+\.tgz$/u.test(sdk.resolved) || !/^sha512-/u.test(sdk.integrity)) throw new Error("Policy Runtime requires an exact released Connector SDK URL and integrity");
  const stage = mkdtempSync(path.join(os.tmpdir(), "sts2-policy-package-stage-"));
  try {
    const packedPackage = { ...source, files: ["bin", "dist", "README.md", "LICENSE", "package-identity.json", "npm-shrinkwrap.json"] };
    delete packedPackage.devDependencies;
    delete packedPackage.scripts;
    const packages = { "": { name: source.name, version: source.version, license: source.license, dependencies: source.dependencies, bin: source.bin, engines: source.engines } };
    for (const [key, value] of Object.entries(lock.packages)) {
      if (!key || value.dev) continue;
      if (value.link || !key.startsWith("node_modules/") || !/^https:\/\//u.test(value.resolved ?? "") || !/^sha512-/u.test(value.integrity ?? "")) throw new Error(`Nonportable production dependency: ${key}`);
      packages[key] = value;
    }
    const shrinkwrap = { name: source.name, version: source.version, lockfileVersion: 3, requires: true, packages };
    const packageIdentity = { schema: "sts2.policy-runtime/package-identity-1", ...identity, connector_sdk: { name: sdkName, version: sdk.version, url: sdk.resolved, integrity: sdk.integrity } };
    for (const name of ["bin", "dist", "README.md"]) cpSync(path.join(componentRoot, name), path.join(stage, name), { recursive: true });
    cpSync(path.resolve(componentRoot, "../../LICENSE"), path.join(stage, "LICENSE"));
    for (const [name, value] of Object.entries({ "package.json": packedPackage, "npm-shrinkwrap.json": shrinkwrap, "package-identity.json": packageIdentity })) writeFileSync(path.join(stage, name), `${JSON.stringify(value, null, 2)}\n`);
    mkdirSync(outputDirectory, { recursive: true });
    const report = JSON.parse(npm(["pack", "--ignore-scripts", "--json", "--pack-destination", outputDirectory], stage))[0];
    const tarball = path.join(outputDirectory, report.filename);
    const sha256 = createHash("sha256").update(readFileSync(tarball)).digest("hex");
    const result = { schema: "sts2.policy-runtime/package-report-1", name: report.name, version: report.version, filename: report.filename, sha256, integrity: report.integrity, identity: packageIdentity, files: report.files.map((entry) => entry.path) };
    writeFileSync(path.join(outputDirectory, "policy-runtime-package.json"), `${JSON.stringify(result, null, 2)}\n`);
    writeFileSync(path.join(outputDirectory, "checksums.sha256"), `${sha256}  ${report.filename}\n`);
    return { ...result, tarball };
  } finally { rmSync(stage, { recursive: true, force: true }); }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2);
  if (args.length !== 2 || args[0] !== "--output") throw new Error("Usage: npm run package -- --output /absolute/output-directory");
  console.log(JSON.stringify(packageRuntime(path.resolve(args[1])), null, 2));
}
