export type CgfDispositionPresentation = Readonly<{
  classification: "unrecognized";
  ownerValue: unknown;
}>;

/**
 * Preserve an owner-issued CGF value without guessing a disposition.
 *
 * This is the single presentation swap point for the DS5-owned generated
 * vocabulary that does not yet exist at the canonical HTTP waist.
 */
export function presentCgfDisposition(
  ownerValue: unknown,
): CgfDispositionPresentation {
  return Object.freeze({
    classification: "unrecognized" as const,
    ownerValue,
  });
}
