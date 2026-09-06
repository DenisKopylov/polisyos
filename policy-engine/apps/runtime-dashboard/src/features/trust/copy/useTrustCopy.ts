import { useI18n, useOptionalI18n } from "@/shared/i18n/LocaleProvider";

/** Complete locale-leaf denominator owned by the `/trust` surface. */
export const TRUST_COPY_KEYS = [
  "accessibilityFrame",
  "accessibilityTitle",
  "antiRolesTitle",
  "asOfLabel",
  "blockersLabel",
  "detailControlLabel",
  "downloadMachine",
  "evidenceDetailLabel",
  "eyebrow",
  "groupsLabel",
  "identitySourceLabel",
  "identityTitle",
  "limitationsLabel",
  "loading",
  "methodologyFrame",
  "methodologyTitle",
  "noneDeclared",
  "notEstablished",
  "pageFrame",
  "payloadLabel",
  "registerEyebrow",
  "registerFrame",
  "registerTitle",
  "reviewDueLabel",
  "reviewOnLabel",
  "ruleLabel",
  "schemaLabel",
  "sourceAsOfLabel",
  "sourcesLabel",
  "sourceSetLabel",
  "title",
  "unavailableFrame",
  "unavailableTitle",
] as const;

export const TRUST_AUDIENCE_KEYS = ["PUBLIC", "REVIEWER", "EXPERT"] as const;

export type TrustCopyKey = (typeof TRUST_COPY_KEYS)[number];
export type TrustAudienceKey = (typeof TRUST_AUDIENCE_KEYS)[number];

type Translate = (path: string) => string;

function bindTrustCopy(t: Translate) {
  return {
    tTrust: (key: TrustCopyKey) => t(`trust.${key}`),
    tTrustAudience: (audience: TrustAudienceKey) =>
      t(`trust.audience.${audience}`),
  };
}

/** Resolve only the audited `/trust` namespace from the active locale catalog. */
export function useTrustCopy() {
  return bindTrustCopy(useI18n().t);
}

/** Optional-provider variant for bounded embedded trust-register consumers. */
export function useOptionalTrustCopy() {
  return bindTrustCopy(useOptionalI18n().t);
}
