import assert from "node:assert/strict";
import test from "node:test";
import { publicAssemblyIdentity } from "./public-provenance.mjs";

test("new release provenance retains exact identity without builder paths or extra fields", () => {
  const expected = { sha256: "a".repeat(64), module_version_id: "12345678-1234-1234-1234-123456789abc" };
  const input = { ...expected, path: "/private/builder/assembly.dll", untrusted: "local metadata" };
  assert.deepEqual(publicAssemblyIdentity(input), expected);
  assert.equal(input.path, "/private/builder/assembly.dll");
  assert.throws(() => publicAssemblyIdentity({ ...input, sha256: "unknown" }));
});
