import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AuthorityMember } from "@/api/hooks/useRunAuthorityValues";
import { PublicSectorReadinessPanel } from "@/features/runs/components/PublicSectorReadinessPanel";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/render";

import {
  AUTHORITY_VALUE_TWIN_SCHEMA,
  buildAuthorityValueTwin,
  checkAuthorityValueTwinParity,
} from "./authorityValueTwin";

/**
 * DS16-C06 — surface ↔ twin parity.
 *
 * Every parity assertion below is paired with the mutation that breaks it, because a
 * parity check that has never reported a mismatch proves nothing about parity.
 */

const RUN_ID = "run-ds16-c06";

const SERVED = [
  {
    owner_surface: null,
    reason: "No governed artifact composes a readiness verdict.",
    refusal_code: "no_runtime_composition_rule",
    retired_from: "x.ts",
    state: "refused",
    surface: "readiness",
    value_id: "readiness.composite_verdict",
  },
  {
    owner_surface: "atlas audience mapping (DS0/DS3)",
    reason: "Stakeholder lens is audience mapping.",
    refusal_code: "owned_by_another_surface",
    retired_from: "x.ts",
    state: "refused",
    surface: "readiness",
    value_id: "readiness.lens_projection",
  },
  {
    owner_surface: null,
    reason: "No embargo concept exists in the source tree.",
    refusal_code: "no_runtime_producer",
    retired_from: "x.ts",
    state: "refused",
    surface: "readiness",
    value_id: "readiness.embargo_overlay",
  },
] as const;

/** What the hook hands the twin: the same members, flattened, nothing invented. */
const MEMBERS: AuthorityMember[] = SERVED.map((value) => ({
  detail: value.reason,
  ownerSurface: value.owner_surface,
  refusalCode: value.refusal_code,
  state: value.state,
  valueId: value.value_id,
}));

async function renderSurface() {
  server.use(
    http.get("*/api/v1/runs/:runId/authority-values", () =>
      HttpResponse.json({
        inventory_version: "ds16-c05.1",
        retirement_commit: "bc1d01001",
        run_id: RUN_ID,
        values: SERVED,
      }),
    ),
  );
  const view = renderWithProviders(<PublicSectorReadinessPanel runId={RUN_ID} />);
  await screen.findByText(SERVED[0].reason);
  return view;
}

describe("DS16-C06 authority value MACHINE twin", () => {
  it("carries every member the surface carries, with the same reason codes", async () => {
    const view = await renderSurface();
    const twin = buildAuthorityValueTwin({
      runId: RUN_ID,
      surface: "readiness",
      values: MEMBERS,
    });

    expect(twin.schema).toBe(AUTHORITY_VALUE_TWIN_SCHEMA);
    expect(twin.members).toHaveLength(MEMBERS.length);
    expect(checkAuthorityValueTwinParity(view.container, twin)).toEqual({
      codeMismatches: [],
      missingFromSurface: [],
      missingFromTwin: [],
      orderMismatch: false,
      passed: true,
      reasonMismatches: [],
    });
  });

  it("fails when the twin drops a member because it carries no value", async () => {
    const view = await renderSurface();
    const dropped = buildAuthorityValueTwin({
      runId: RUN_ID,
      surface: "readiness",
      values: MEMBERS.slice(1),
    });

    const parity = checkAuthorityValueTwinParity(view.container, dropped);
    expect(parity.passed).toBe(false);
    expect(parity.missingFromTwin).toEqual(["readiness.composite_verdict"]);
  });

  it("fails when the twin carries a member the surface never rendered", async () => {
    const view = await renderSurface();
    const invented = buildAuthorityValueTwin({
      runId: RUN_ID,
      surface: "readiness",
      values: [
        ...MEMBERS,
        {
          detail: "invented",
          ownerSurface: null,
          refusalCode: "no_runtime_producer",
          state: "refused",
          valueId: "readiness.slow_review",
        },
      ],
    });

    const parity = checkAuthorityValueTwinParity(view.container, invented);
    expect(parity.passed).toBe(false);
    expect(parity.missingFromSurface).toEqual(["readiness.slow_review"]);
  });

  it("fails when the twin reorders members into a ranking", async () => {
    const view = await renderSurface();
    const ranked = buildAuthorityValueTwin({
      runId: RUN_ID,
      surface: "readiness",
      values: [...MEMBERS].reverse(),
    });

    const parity = checkAuthorityValueTwinParity(view.container, ranked);
    expect(parity.passed).toBe(false);
    expect(parity.orderMismatch).toBe(true);
  });

  it("fails when the twin softens a reason code or a reason", async () => {
    const view = await renderSurface();
    const twin = buildAuthorityValueTwin({
      runId: RUN_ID,
      surface: "readiness",
      values: MEMBERS,
    });

    const softenedCode = {
      ...twin,
      members: twin.members.map((member, index) =>
        index === 0 ? { ...member, refusal_code: "no_runtime_producer" } : member,
      ),
    };
    expect(
      checkAuthorityValueTwinParity(view.container, softenedCode).codeMismatches,
    ).toEqual(["readiness.composite_verdict"]);

    const softenedReason = {
      ...twin,
      members: twin.members.map((member, index) =>
        index === 0 ? { ...member, reason: "Unavailable." } : member,
      ),
    };
    expect(
      checkAuthorityValueTwinParity(view.container, softenedReason).reasonMismatches,
    ).toEqual(["readiness.composite_verdict"]);
  });

  it("carries no aggregate of any kind", async () => {
    await renderSurface();
    const twin = buildAuthorityValueTwin({
      runId: RUN_ID,
      surface: "readiness",
      values: MEMBERS,
    });

    // A count, share, score or verdict over eleven refusals is the DS4-C23 sin in
    // machine clothing. The twin's only keys are identity plus the member list.
    expect(Object.keys(twin).sort()).toEqual([
      "members",
      "run_id",
      "schema",
      "surface",
    ]);
    for (const member of twin.members) {
      expect(Object.keys(member).sort()).toEqual([
        "owner_surface",
        "reason",
        "refusal_code",
        "state",
        "value_id",
      ]);
    }
  });
});
