export type CacheAgePresentation = Readonly<{
  classification: "unrecognized";
  ownerLabel: string | null;
}>;

export function presentCacheAgeLabel(
  ownerValue: unknown,
): CacheAgePresentation {
  const ownerLabel =
    typeof ownerValue === "string" && ownerValue.trim()
      ? ownerValue.trim()
      : null;
  return Object.freeze({
    classification: "unrecognized" as const,
    ownerLabel,
  });
}
