import type { QuantityValueOutput } from "@polisyos/runtime-api-client";
import { ChartQuantityEvidence } from "@/shared/charts/quantityChartSemantics";
import { Quantity } from "@/shared/ui/quantity/Quantity";

/**
 * DS16-C07 — the set-valued value viz family.
 *
 * The canonical object is the SET. A scalar is a lossy view of it and is never the
 * authority, so nothing here can collapse a multi-member set to a point: the members are
 * handed to `ChartQuantityEvidence`, which is the existing set-vs-point seam, rather than
 * reduced first.
 *
 * WHY NO RANKING MODE EXISTS AT ALL
 * ---------------------------------
 * The DS16 plan binds a single ranked recommendation to a `GY-PA1`
 * `NormativeAuthorizationRecord`, with a `NormativeDecisionRequest` shown in its absence.
 * Measured: BOTH types have zero occurrences in `src/`, `schemas/` and `architecture/`.
 * So no authorization can exist, and this family therefore has no code path that emits an
 * order — no ordered list, no rank, no set position. Inventing an authorization record so
 * that a ranking could render is the authority-minting this slice exists to close.
 *
 * TWO DIFFERENT STATEMENTS, DELIBERATELY NOT CONFLATED
 * ----------------------------------------------------
 *   `incomparable` — a claim about the VALUES: no admissible ranking exists between
 *     them. Only a producer may say this, because it is a property of the sets.
 *   order-not-authorized — a claim about the SURFACE: nothing authorizes this glass to
 *     rank anything. True today for every set, and it is DS16's own statement to make.
 *
 * Collapsing the second into the first would have the surface assert a property of the
 * values it has no standing to assert.
 *
 * Vocabulary is REFERENCED, never coined. `OuterSetComparison` is exactly
 * `ValueOuterSetComparison` from `src/polisyos/core/contracts/value_outer_set.py:36`.
 * `null` is not a fourth member of that vocabulary — it is the absence of a producer
 * verdict, which is a different thing from the producer saying "unknown".
 */

/** `value_outer_set.py:36` — the producer's verdict about the order, verbatim. */
export type OuterSetComparison = "dominates" | "incomparable" | "unknown";

/**
 * The three states C01's negative 5 requires to stay pairwise distinct, plus the ordinary
 * case. `gap` has no representation in `Quantity` (`data-quantity-presentation` is only
 * scalar | non-scalar | unknown), which is precisely why it is modelled here.
 */
export type OuterSetValueState = "value" | "zero" | "unknown" | "gap";

/**
 * Rendered copy is i18n-key-shaped TOKENS, never prose. `shared/i18n/**` is DS6's
 * exclusive territory, so this slice may not add catalog keys, and inventing the eventual
 * wording here would squat on copy DS16 does not own. C08 resolves these through DS6's
 * catalog when the copy is actually owned.
 */
export const OUTER_SET_GAP_TOKEN = "ds16.value_state.no_observation_in_period";
export const OUTER_SET_NO_ADMISSIBLE_RANKING_TOKEN =
  "ds16.comparison.no_admissible_ranking_exists";
export const OUTER_SET_ORDER_UNAUTHORIZED_TOKEN =
  "ds16.comparison.order_not_authorized";
export const OUTER_SET_DOMINANCE_TOKEN = "ds16.comparison.dominance_reported";
export const OUTER_SET_COMPARISON_UNKNOWN_TOKEN =
  "ds16.comparison.order_unknown";

const COMPARISON_TOKENS: Record<OuterSetComparison, string> = {
  dominates: OUTER_SET_DOMINANCE_TOKEN,
  incomparable: OUTER_SET_NO_ADMISSIBLE_RANKING_TOKEN,
  unknown: OUTER_SET_COMPARISON_UNKNOWN_TOKEN,
};

/**
 * One member's value state. The three states are separated by BOTH the rendered
 * presentation and the rendered text, so no two can produce the same signature — which
 * is exactly what C01's negative 5 checks.
 */
export function OuterSetValueStateCell({
  state,
  value,
}: {
  state: OuterSetValueState;
  value: QuantityValueOutput;
}) {
  // Branched rather than spread: `Quantity`'s absent-value props are a discriminated
  // union, so a spread cannot narrow them and would erase the very distinction the gap
  // state depends on.
  return (
    <span data-testid="ds16-value-state" data-value-state={state}>
      {state === "gap" ? (
        <Quantity
          absentValue={
            <span data-testid="ds16-gap-marker">{OUTER_SET_GAP_TOKEN}</span>
          }
          absentValueLabel={OUTER_SET_GAP_TOKEN}
          provenanceMode="off"
          value={value}
        />
      ) : (
        <Quantity provenanceMode="off" value={value} />
      )}
    </span>
  );
}

/**
 * The set itself. Members are never reduced; the order statement is rendered beside them
 * and never as an ordering of them.
 */
export function OuterSetValue({
  comparison,
  members,
}: {
  comparison: OuterSetComparison | null;
  members: readonly QuantityValueOutput[];
}) {
  const orderToken =
    comparison === null
      ? OUTER_SET_ORDER_UNAUTHORIZED_TOKEN
      : COMPARISON_TOKENS[comparison];

  return (
    <ul
      data-comparison={comparison ?? "unauthorized"}
      data-outer-set-cardinality={members.length}
      data-testid="ds16-comparison"
    >
      <li data-testid="ds16-order-statement">{orderToken}</li>
      <li>
        <ChartQuantityEvidence value={members} />
      </li>
    </ul>
  );
}
