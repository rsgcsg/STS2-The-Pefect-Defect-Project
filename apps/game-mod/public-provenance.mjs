// Release provenance contains byte identity, never the builder's local filesystem.
export function publicAssemblyIdentity(identity) {
  if (!/^[0-9a-f]{64}$/u.test(identity?.sha256 ?? "")
      || !/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/u.test(identity?.module_version_id ?? "")) {
    throw new Error("Assembly identity requires exact SHA256 and MVID");
  }
  return { sha256: identity.sha256, module_version_id: identity.module_version_id };
}
