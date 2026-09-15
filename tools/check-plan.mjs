#!/usr/bin/env node
// One conservative check router for local use and CI. This is not qualification.
import fs from "node:fs";
import path from "node:path";
import { execFileSync, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = path.resolve(import.meta.dirname, "..");
// Explicit editorial surfaces only. Governance, contracts, component docs and
// unknown paths intentionally retain the complete suite in this first rollout.
const editorial = new Set([
  "README.md", "CONTRIBUTING.md", "docs/NEW_MEMBER_HANDOFF.zh-CN.md",
  "docs/NEW_ENGINEER_GUIDE.md", "docs/DOCUMENT_MAP.md", "docs/STATUS.md",
]);

export function classifyChanges(entries) {
  if (!entries.length) return { scope: "full", reason: "empty_or_unknown_diff" };
  if (entries.every(({ status, file }) => status === "M" && editorial.has(file))) {
    return { scope: "docs", reason: "modified_editorial_allowlist_only" };
  }
  return { scope: "full", reason: "source_contract_governance_or_unknown_change" };
}

export function parseDiff(raw) {
  const parts = raw.split("\0");
  if (parts.pop() !== "") throw new Error("unterminated_diff");
  const entries = [];
  while (parts.length) {
    const status = parts.shift();
    const file = parts.shift();
    if (!/^[AMDTUXB]$/.test(status) || !file) throw new Error("unsupported_diff_record");
    entries.push({ status, file });
  }
  return entries;
}

export function makePlan({ base, head = "HEAD", forceFull = false, cwd = root } = {}) {
  const git = (...args) => execFileSync("git", args, { cwd, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
  try {
    // Resolve options as revisions, never interpolate them into a shell.
    const exactHead = git("rev-parse", "--verify", "--end-of-options", `${head}^{commit}`).trim();
    const exactBase = git("rev-parse", "--verify", "--end-of-options", `${base}^{commit}`).trim();
    const entries = parseDiff(git("diff", "--no-renames", "--name-status", "-z", exactBase, exactHead, "--"));
    const dirty = git("status", "--porcelain", "--untracked-files=normal").trim().length > 0;
    const route = forceFull || dirty ? { scope: "full", reason: forceFull ? "explicit_full" : "dirty_worktree" } : classifyChanges(entries);
    return { ...route, base: exactBase, head: exactHead, files: entries };
  } catch {
    return { scope: "full", reason: "diff_unavailable", base: null, head: null, files: [] };
  }
}

export function aggregatePassed(scope, results) {
  if (results.plan !== "success") return false;
  if (scope === "docs") return results.docs === "success" && results.linux === "skipped" && results.windows === "skipped";
  if (scope === "full") return results.docs === "skipped" && results.linux === "success" && results.windows === "success";
  return false;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2);
  if (args[0] === "aggregate") {
    const e = process.env;
    if (!aggregatePassed(e.CHECK_SCOPE, { plan: e.PLAN_RESULT, docs: e.DOCS_RESULT, linux: e.LINUX_RESULT, windows: e.WINDOWS_RESULT })) process.exitCode = 1;
  } else {
    const baseIndex = args.indexOf("--base");
    const headIndex = args.indexOf("--head");
    const plan = makePlan({ base: baseIndex < 0 ? process.env.CHECK_BASE : args[baseIndex + 1], head: headIndex < 0 ? "HEAD" : args[headIndex + 1], forceFull: args.includes("--full") || process.env.CHECK_FULL === "true" });
    process.stdout.write(`${JSON.stringify(plan, null, 2)}\n`);
    if (process.env.GITHUB_OUTPUT) fs.appendFileSync(process.env.GITHUB_OUTPUT, `scope=${plan.scope}\n`);
    if (process.env.GITHUB_STEP_SUMMARY) fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, `Check scope: **${plan.scope}** (${plan.reason}). Base ${plan.base}; tested checkout ${plan.head}. Source/test only.\n`);
    if (args.includes("--run")) {
      const result = spawnSync(process.platform === "win32" ? "npm.cmd" : "npm", ["run", plan.scope === "docs" ? "check:docs" : "check"], { cwd: root, stdio: "inherit", shell: process.platform === "win32" });
      process.exitCode = result.status ?? 1;
    }
  }
}
