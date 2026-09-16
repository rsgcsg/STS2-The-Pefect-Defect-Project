import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import test from "node:test";
import { classifyChanges, parseDiff, makePlan, aggregatePassed, scopeCommands } from "./check-plan.mjs";

test("only modified editorial surfaces select docs; additions, deletion and rename stay full", () => {
  assert.equal(classifyChanges([{ status: "M", file: "README.md" }]).scope, "docs");
  for (const file of ["AGENTS.md", "docs/TESTING.md", "docs/adr/example.md", "components/annotator/docs/DATA_CONTRACT.md", "python/uv.lock", ".github/workflows/ci.yml", "tools/check-plan.mjs", "new.md"]) {
    assert.equal(classifyChanges([{ status: "M", file }]).scope, "full", file);
  }
  for (const status of ["A", "D", "T", "R100"]) assert.equal(classifyChanges([{ status, file: "README.md" }]).scope, "full");
  assert.equal(classifyChanges([]).scope, "full");
});

test("NUL diff parsing preserves unusual names and refuses ambiguous records", () => {
  assert.deepEqual(parseDiff("M\0docs/name\nwith spaces.md\0"), [{ status: "M", file: "docs/name\nwith spaces.md" }]);
  for (const raw of ["M\0README.md", "M\0", "R100\0a\0b\0"]) assert.throws(() => parseDiff(raw));
});

test("exact Git comparison works, dirty or missing provenance fails closed", () => {
  const cwd = fs.mkdtempSync(path.join(os.tmpdir(), "check-plan-"));
  const git = (...args) => execFileSync("git", args, { cwd, encoding: "utf8", stdio: "pipe" }).trim();
  try {
    git("init"); git("config", "user.email", "test@example.invalid"); git("config", "user.name", "Test");
    fs.writeFileSync(path.join(cwd, "README.md"), "old\n"); git("add", "."); git("commit", "-m", "base");
    const base = git("rev-parse", "HEAD");
    fs.writeFileSync(path.join(cwd, "README.md"), "new\n"); git("commit", "-am", "docs");
    assert.equal(makePlan({ base, cwd }).scope, "docs");
    assert.equal(makePlan({ base, cwd, forceFull: true }).scope, "full");
    assert.equal(makePlan({ base: "missing", cwd }).reason, "diff_unavailable");
    fs.writeFileSync(path.join(cwd, "untracked.js"), "change");
    assert.equal(makePlan({ base, cwd }).reason, "dirty_worktree");
  } finally { fs.rmSync(cwd, { recursive: true, force: true }); }
});

test("required aggregate rejects missing, failed, cancelled or unexpectedly skipped work", () => {
  const full = { plan: "success", docs: "skipped", linux: "success", windows: "success" };
  const docs = { plan: "success", docs: "success", linux: "skipped", windows: "skipped" };
  assert.ok(aggregatePassed("full", full)); assert.ok(aggregatePassed("docs", docs));
  for (const key of ["plan", "linux", "windows"]) for (const value of ["skipped", "cancelled", "failure", ""]) assert.equal(aggregatePassed("full", { ...full, [key]: value }), false);
  for (const key of ["plan", "docs"]) for (const value of ["skipped", "cancelled", "failure", ""]) assert.equal(aggregatePassed("docs", { ...docs, [key]: value }), false);
  assert.equal(aggregatePassed("unknown", full), false);
});

test("Python owner changes retain repository guards and both OS Python consumers", () => {
  for (const file of ["python/spireagent/hub/exports.py", "python/stpd/models/new.py", "python/tests/new.py"])
    for (const status of ["M", "A", "D"]) assert.equal(classifyChanges([{file,status}]).scope, "python");
  for (const file of ["python/pyproject.toml", "python/uv.lock", "python/tools/project.py", "components/evidence/src/a.py", "python/deploy/hub/Dockerfile", "contracts/new.json"])
    assert.equal(classifyChanges([{file,status:"M"}, {file:"python/stpd/a.py",status:"M"}]).scope, "full");
  assert.deepEqual(scopeCommands("python"), ["check:python-scope"]);
  assert.deepEqual(scopeCommands("full"), ["check"]);
  assert.deepEqual(scopeCommands("reuse"), ["check:repository"]);
  assert.throws(() => scopeCommands("typo"));
});
test("reuse requires fresh repository checks; Python scope still requires Windows", () => {
  const reused = {plan:"success",docs:"success",linux:"skipped",windows:"skipped"};
  assert.ok(aggregatePassed("reuse",reused));
  for (const key of ["plan","docs"]) assert.equal(aggregatePassed("reuse",{...reused,[key]:"failure"}),false);
  assert.equal(aggregatePassed("python",reused),false);
  assert.ok(aggregatePassed("python",{...reused,docs:"skipped",linux:"success",windows:"success"}));
});
