import type { AuthorityMember } from "@/api/hooks/useRunAuthorityValues";

/**
 * DS16-C06 — the MACHINE twin of the readiness / scientific-depth surface.
 *
 * A typed JSON packet carrying exactly what the glass carries, so a machine reader
 * never has to scrape the panel and never receives a different answer than a person.
 *
 * The parity property is sharper here than usual because the payload is refusals. A
 * twin that summarized ("11 values unavailable"), ranked, or dropped a member because it
 * "carries no value" would be the same minting sin in machine clothing — so the twin is
 * a member-for-member projection with no aggregate of any kind, and the parity check
 * below fails on a member present on one side and absent on the other.
 */

export const AUTHORITY_VALUE_TWIN_SCHEMA =
  "policyos.atlas.ds16.authority_values.twin.v1";

export type AuthorityValueTwinMember = {
  owner_surface: string | null;
  reason: string;
  refusal_code: string | null;
  state: string;
  value_id: string;
};

export type AuthorityValueTwin = {
  members: AuthorityValueTwinMember[];
  run_id: string;
  schema: typeof AUTHORITY_VALUE_TWIN_SCHEMA;
  surface: string;
};

export function buildAuthorityValueTwin(input: {
  runId: string;
  surface: string;
  values: readonly AuthorityMember[];
}): AuthorityValueTwin {
  return {
    members: input.values.map((value) => ({
      owner_surface: value.ownerSurface,
      reason: value.detail,
      refusal_code: value.refusalCode,
      state: value.state,
      value_id: value.valueId,
    })),
    run_id: input.runId,
    schema: AUTHORITY_VALUE_TWIN_SCHEMA,
    surface: input.surface,
  };
}

export type TwinParityReport = {
  codeMismatches: string[];
  missingFromSurface: string[];
  missingFromTwin: string[];
  orderMismatch: boolean;
  passed: boolean;
  reasonMismatches: string[];
};

/**
 * Surface ↔ twin parity, read off the rendered DOM rather than off the model both were
 * built from — comparing the twin to its own input would prove only that a pure function
 * is pure.
 */
export function checkAuthorityValueTwinParity(
  container: HTMLElement,
  twin: AuthorityValueTwin,
): TwinParityReport {
  const rendered = [...container.querySelectorAll("[data-value-id]")].map(
    (node) => ({
      owner_surface: node.getAttribute("data-owner-surface"),
      reason: (node.textContent ?? "").trim(),
      refusal_code: node.getAttribute("data-refusal-code"),
      state: node.getAttribute("data-state"),
      value_id: node.getAttribute("data-value-id") ?? "",
    }),
  );

  const renderedIds = rendered.map((member) => member.value_id);
  const twinIds = twin.members.map((member) => member.value_id);
  const renderedById = new Map(rendered.map((member) => [member.value_id, member]));

  const missingFromTwin = renderedIds.filter((id) => !twinIds.includes(id)).sort();
  const missingFromSurface = twinIds.filter((id) => !renderedIds.includes(id)).sort();

  const codeMismatches: string[] = [];
  const reasonMismatches: string[] = [];
  for (const member of twin.members) {
    const match = renderedById.get(member.value_id);
    if (!match) continue;
    if (match.refusal_code !== member.refusal_code) {
      codeMismatches.push(member.value_id);
    }
    if (match.reason !== member.reason) {
      reasonMismatches.push(member.value_id);
    }
  }

  // Order is part of parity: a twin that reordered members into a ranking would be
  // asserting a precedence the producer never supplied.
  const orderMismatch =
    missingFromTwin.length === 0 &&
    missingFromSurface.length === 0 &&
    renderedIds.join("|") !== twinIds.join("|");

  return {
    codeMismatches: codeMismatches.sort(),
    missingFromSurface,
    missingFromTwin,
    orderMismatch,
    passed:
      missingFromTwin.length === 0 &&
      missingFromSurface.length === 0 &&
      codeMismatches.length === 0 &&
      reasonMismatches.length === 0 &&
      !orderMismatch,
    reasonMismatches: reasonMismatches.sort(),
  };
}
