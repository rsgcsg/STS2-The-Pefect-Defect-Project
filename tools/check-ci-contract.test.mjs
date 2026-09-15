import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { ciWorkflowErrors } from "./check-ci-contract.mjs";

const workflow = path.resolve(import.meta.dirname, "..", ".github", "workflows", "ci.yml");

function currentSource() {
  return fs.readFileSync(workflow, "utf8").replace(/\r\n?/gu, "\n");
}

test("current CI workflow satisfies the repository CI contract", () => {
  assert.deepEqual(ciWorkflowErrors(currentSource()), []);
});

test("current CI workflow also validates with CRLF newlines", () => {
  assert.deepEqual(ciWorkflowErrors(currentSource().replace(/\n/gu, "\r\n")), []);
});

test("CI contract rejects unscoped push duplication", () => {
  const source = currentSource().replace(
    "  push:\n    branches:\n      - develop\n      - main\n      - \"release/**\"\n      - \"hotfix/**\"\n",
    "  push:\n"
  );
  assert.ok(ciWorkflowErrors(source).includes("CI push trigger must be branch-scoped"));
});

test("CI contract rejects a hand-picked Windows subset", () => {
  const source = currentSource().replace(
    "      - name: Run full portable source/test gate\n        run: npm run check\n      - name: Check patch hygiene\n        run: git diff --check\n\n  portable:\n",
    "      - name: Run selected Windows checks\n        run: npm --prefix components/annotator run test\n      - name: Check patch hygiene\n        run: git diff --check\n\n  portable:\n"
  );
  const errors = ciWorkflowErrors(source);
  assert.ok(errors.includes("Windows portability must run the root check"));
  assert.ok(errors.includes("Windows portability must not maintain a hand-picked component subset"));
});

test("CI contract rejects a required status that does not aggregate Windows", () => {
  const source = currentSource().replace(
    "needs: [linux-portability, windows-portability]",
    "needs: [linux-portability]"
  );
  assert.ok(ciWorkflowErrors(source).includes("portable must aggregate both OS lanes"));
});

test("CI contract rejects hosted exact-game qualification", () => {
  const source = `${currentSource()}\n# npm run check:exact-game\n`;
  assert.ok(ciWorkflowErrors(source).some((error) => error.includes("check:exact-game")));
});

test("CI contract rejects unpinned GitHub Actions", () => {
  const source = currentSource().replace(
    "actions/setup-node@820762786026740c76f36085b0efc47a31fe5020",
    "actions/setup-node@v7"
  );
  assert.ok(ciWorkflowErrors(source).some((error) => error.includes("actions/setup-node@v7")));
});

// Same root contract covers both language stacks after consolidation.

test("both language environments remain required on both OS lanes", () => {
  for (const command of ["uv sync --project python --locked --all-extras", "npm ci --prefix python"]) {
    const source = currentSource().replaceAll(`run: ${command}`, "run: echo omitted");
    const errors = ciWorkflowErrors(source);
    assert.ok(errors.some((error) => error.startsWith("Linux must install")));
    assert.ok(errors.some((error) => error.startsWith("Windows must install")));
  }
});
