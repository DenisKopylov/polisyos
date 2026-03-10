export function buildRunSummary(
  overrides?: Partial<{
    run_id: string;
    status: string;
  }>,
) {
  return {
    run_id: "run-1",
    status: "completed",
    ...overrides,
  };
}

export function buildCapabilityManifest(
  overrides?: Partial<{
    default_locale: "en" | "uk";
    features: Array<{ enabled: boolean; key: string; label: string }>;
  }>,
) {
  return {
    default_locale: "en" as const,
    features: [],
    ...overrides,
  };
}
