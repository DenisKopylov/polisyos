import type { CapabilityManifestPayload } from "@/api/validators";

export function isCapabilityEnabled(
  manifest: CapabilityManifestPayload | undefined,
  key: string,
): boolean {
  return (
    manifest?.features?.some(
      (feature) => feature.key === key && feature.enabled,
    ) ?? false
  );
}

export function getCapability(
  manifest: CapabilityManifestPayload | undefined,
  key: string,
) {
  return manifest?.features?.find((feature) => feature.key === key) ?? null;
}

export function readNumericConstraint(
  manifest: CapabilityManifestPayload | undefined,
  key: string,
  fallback: number,
): number {
  const raw = manifest?.constraints?.[key];
  return typeof raw === "number" && Number.isFinite(raw) ? raw : fallback;
}
