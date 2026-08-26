import type { CapabilityManifestPayload } from "@/api/validators";

/** Reads a server-produced execution-policy arm, never discovery or admission. */
export function isExecutionPolicyEnabled(
  manifest: CapabilityManifestPayload | undefined,
  key: string,
): boolean {
  const projection = manifest?.fallback_rules?.execution_policy;
  if (
    typeof projection !== "object" ||
    projection === null ||
    Array.isArray(projection)
  ) {
    return false;
  }
  const value = (projection as Record<string, unknown>)[key];
  return typeof value === "boolean" ? value : false;
}

export function readNumericConstraint(
  manifest: CapabilityManifestPayload | undefined,
  key: string,
  fallback: number,
): number {
  const raw = manifest?.constraints?.[key];
  return typeof raw === "number" && Number.isFinite(raw) ? raw : fallback;
}

/** Reads a numeric execution-policy constraint from the narrow policy manifest. */
export function readExecutionPolicyConstraint(
  manifest: CapabilityManifestPayload | undefined,
  key: string,
  fallback: number,
): number {
  return readNumericConstraint(manifest, key, fallback);
}
