import { useQuery } from "@tanstack/react-query";

import {
  RuntimeApiClient,
  type AuthoritySurface,
  type RunAuthorityProjection,
} from "@polisyos/runtime-api-client";

import { authAwareRuntimeFetch } from "@/app/auth/authSession";
import { API_BASE_URL } from "@/shared/lib/constants";

export type AuthorityValue = RunAuthorityProjection["values"][number];
export type { AuthoritySurface };

/**
 * A flat display record over the served discriminated union.
 *
 * The union is normalized HERE rather than on the panel because narrowing it on the
 * glass would be a conditional in a rendered position, which the C02 gate refuses on
 * purpose. Nothing is invented in the process: `detail` is the producer's own `reason`
 * for a refusal and its own `metric_id` for a supplied value, so a supplied member can
 * never arrive and be silently blanked — the failure this slice exists to close.
 */
export type AuthorityMember = {
  detail: string;
  ownerSurface: string | null;
  refusalCode: string | null;
  state: AuthorityValue["state"];
  valueId: string;
};

function toMember(value: AuthorityValue): AuthorityMember {
  return value.state === "refused"
    ? {
        detail: value.reason,
        ownerSurface: value.owner_surface ?? null,
        refusalCode: value.refusal_code,
        state: value.state,
        valueId: value.value_id,
      }
    : {
        detail: value.metric_id,
        ownerSurface: null,
        refusalCode: null,
        state: value.state,
        valueId: value.value_id,
      };
}

/**
 * DS16-C05 — intake for the retired DS4-C23 inventory.
 *
 * WHY THIS HOOK USES THE PACKAGE CLIENT DIRECTLY, unlike its neighbours.
 * `src/api/client.ts` types `runtimeApiClient` from the LOCAL `src/api/types.ts`, which
 * C04 measured as 1504 lines stale against its own schema on `main` and deliberately did
 * not regenerate — repairing that drift is not this slice's scope and would have buried
 * an additive change under it. The generated `@polisyos/runtime-api-client` package is
 * the intake the DS16 plan names, C04 regenerated it, and it carries this operation. So
 * this hook consumes the package client and the stale local types stay untouched.
 *
 * The partition between the two surfaces is read from the producer's `surface` field,
 * never derived here by parsing a value id: deriving it would be a local routing
 * decision over authority data, the class of thing this slice keeps off the glass.
 *
 * There is no fallback list and no default. When the producer has not answered, the
 * panel renders its sanctioned refusal and nothing else — an invented placeholder is how
 * "unavailable" becomes "zero" one slice later.
 */
const authorityValuesClient = new RuntimeApiClient({
  baseUrl: API_BASE_URL,
  // The generated client calls `fetch(url, init)` with a path-relative URL, while
  // `authAwareRuntimeFetch` takes a `Request` and `new Request()` cannot parse a
  // relative URL. Resolving against the origin first keeps the session/refresh
  // behaviour every other hook gets.
  fetchImpl: (input, init) =>
    authAwareRuntimeFetch(
      new Request(new URL(String(input), globalThis.location.origin), init),
    ),
});

export function useRunAuthorityValues(runId: string, surface: AuthoritySurface) {
  const query = useQuery({
    queryFn: () => authorityValuesClient.getRunAuthorityValues({ run_id: runId }),
    queryKey: ["runs", runId, "authority-values"],
  });

  const values = (query.data?.values ?? [])
    .filter((value) => value.surface === surface)
    .map(toMember);

  return { values };
}
