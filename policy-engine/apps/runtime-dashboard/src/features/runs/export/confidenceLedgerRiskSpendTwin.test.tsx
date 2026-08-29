/* eslint-disable testing-library/no-container, testing-library/no-node-access -- adversarial DOM mutation is the twin falsifier */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import type { AvailableConfidenceLedgerRiskSpendPacket } from "@polisyos/runtime-api-client";
import { render } from "@testing-library/react";

import { ConfidenceLedgerRiskSpend } from "@/features/runs/components/ConfidenceLedgerRiskSpend";
import type { ConfidenceLedgerRiskSpendPacket } from "@/features/runs/domain/confidenceLedgerRiskSpend";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

import {
  CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA,
  createConfidenceLedgerRiskSpendEvaluationContext,
  evaluateConfidenceLedgerRiskSpendTwin,
} from "./confidenceLedgerRiskSpendTwin";

function availablePacket(): AvailableConfidenceLedgerRiskSpendPacket {
  const openApi = JSON.parse(
    readFileSync(
      resolve(process.cwd(), "../../schemas/runtime_api_v1.openapi.json"),
      "utf8",
    ),
  ) as {
    paths: Record<
      string,
      {
        get: {
          responses: Record<
            string,
            {
              content: Record<
                string,
                {
                  examples: {
                    default: {
                      value: AvailableConfidenceLedgerRiskSpendPacket;
                    };
                  };
                }
              >;
            }
          >;
        };
      }
    >;
  };
  return structuredClone(
    openApi.paths[
      "/api/v1/exports/governed-projections/confidence-ledger-risk-spend"
    ].get.responses["200"].content["application/json"].examples.default.value,
  );
}

function renderEvaluation() {
  const packet = availablePacket();
  const rawPacketBytes = new TextEncoder().encode(JSON.stringify(packet));
  const view = render(
    <LocaleProvider>
      <ConfidenceLedgerRiskSpend
        projection={{
          packet: packet as unknown as ConfidenceLedgerRiskSpendPacket,
          rawPacketBytes,
        }}
      />
    </LocaleProvider>,
  );
  const root = view.container.querySelector<HTMLElement>(
    '[data-confidence-surface="risk-spend"]',
  );
  if (root === null) throw new Error("risk-spend surface did not render");
  return {
    context: createConfidenceLedgerRiskSpendEvaluationContext({
      rawPacketBytes,
      root,
    }),
    packet,
    rawPacketBytes,
    root,
    view,
  };
}

describe("confidence-ledger risk-spend production twin", () => {
  it("admits the packet, decodes visible ordered semantics, and evaluates PV-K04/PV-K06 exactly", async () => {
    const fixture = renderEvaluation();

    const result = await evaluateConfidenceLedgerRiskSpendTwin({
      context: fixture.context,
      packetCandidate: fixture.packet,
      rawPacketBytes: fixture.rawPacketBytes,
      root: fixture.root,
    });

    expect(result.status).toBe("exact");
    if (result.status !== "exact") return;
    expect(result.byteTwin).toBe(fixture.rawPacketBytes);
    expect(Object.keys(result.protectedQueries)).toEqual(
      CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA,
    );
    expect(Object.values(result.protectedQueries)).toEqual(
      CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA.map(() => "denied"),
    );
  });

  it.each([
    [
      "timeout",
      (fixture: ReturnType<typeof renderEvaluation>) => ({
        ...fixture.context,
        stepBudget: 0,
      }),
    ],
    [
      "missing_input_or_incomplete_history",
      (fixture: ReturnType<typeof renderEvaluation>) => ({
        ...fixture.context,
        history: [],
      }),
    ],
    [
      "model_observation_inconsistent",
      (fixture: ReturnType<typeof renderEvaluation>) => ({
        ...fixture.context,
        recordModels: [],
      }),
    ],
    [
      "model_observation_inconsistent",
      (fixture: ReturnType<typeof renderEvaluation>) => ({
        ...fixture.context,
        controlledObservations: [],
      }),
    ],
    [
      "empty_consistency_set",
      (fixture: ReturnType<typeof renderEvaluation>) => ({
        ...fixture.context,
        consistencySet: [],
      }),
    ],
    [
      "unproved_approximation",
      (fixture: ReturnType<typeof renderEvaluation>) => ({
        ...fixture.context,
        evaluationMode: "sampled_search" as const,
      }),
    ],
  ])(
    "returns %s when the evaluation record changes but bytes, DOM markers, and apparent copy remain fixed",
    async (reason, mutateContext) => {
      const fixture = renderEvaluation();

      await expect(
        evaluateConfidenceLedgerRiskSpendTwin({
          context: mutateContext(fixture),
          packetCandidate: fixture.packet,
          rawPacketBytes: fixture.rawPacketBytes,
          root: fixture.root,
        }),
      ).resolves.toEqual({ status: "blocked", reason });
    },
  );

  it.each(["class-spend", "instrument-definitions"])(
    "rejects reordered %s rows rather than reconstructing a ranked packet",
    async (listName) => {
      const fixture = renderEvaluation();
      const list = fixture.root.querySelector<HTMLElement>(
        `[data-confidence-list="${listName}"]`,
      );
      const first = list?.children.item(0);
      if (!(list instanceof HTMLElement) || !(first instanceof HTMLElement)) {
        throw new Error(`${listName} list is incomplete`);
      }
      list.append(first);

      await expect(
        evaluateConfidenceLedgerRiskSpendTwin({
          context: fixture.context,
          packetCandidate: fixture.packet,
          rawPacketBytes: fixture.rawPacketBytes,
          root: fixture.root,
        }),
      ).resolves.toEqual({
        status: "blocked",
        reason: "model_observation_inconsistent",
      });
    },
  );

  it("rejects omission of the honest-zero register instead of inferring completeness", async () => {
    const fixture = renderEvaluation();
    fixture.root
      .querySelector<HTMLElement>(
        '[data-confidence-section="positive-register"]',
      )
      ?.remove();

    await expect(
      evaluateConfidenceLedgerRiskSpendTwin({
        context: fixture.context,
        packetCandidate: fixture.packet,
        rawPacketBytes: fixture.rawPacketBytes,
        root: fixture.root,
      }),
    ).resolves.toEqual({
      status: "blocked",
      reason: "model_observation_inconsistent",
    });
  });

  it("returns parser_or_schema_failure for a malformed packet", async () => {
    const fixture = renderEvaluation();
    const malformed = structuredClone(fixture.packet);
    Object.assign(malformed.payload, { authority_by_marker: true });

    await expect(
      evaluateConfidenceLedgerRiskSpendTwin({
        context: fixture.context,
        packetCandidate: malformed,
        rawPacketBytes: fixture.rawPacketBytes,
        root: fixture.root,
      }),
    ).resolves.toEqual({
      status: "blocked",
      reason: "parser_or_schema_failure",
    });
  });

  it("parses the captured bytes instead of trusting an unrelated admitted object", async () => {
    const fixture = renderEvaluation();
    const malformedBytes = new TextEncoder().encode("{}");

    await expect(
      evaluateConfidenceLedgerRiskSpendTwin({
        context: createConfidenceLedgerRiskSpendEvaluationContext({
          rawPacketBytes: malformedBytes,
          root: fixture.root,
        }),
        packetCandidate: fixture.packet,
        rawPacketBytes: malformedBytes,
        root: fixture.root,
      }),
    ).resolves.toEqual({
      status: "blocked",
      reason: "parser_or_schema_failure",
    });
  });

  it("returns unsupported_or_out_of_model before a novel packet schema can be treated as malformed", async () => {
    const fixture = renderEvaluation();
    const unsupported = {
      ...fixture.packet,
      packet_schema_version:
        "policyos.runtime.confidence_ledger_risk_spend_packet.v2",
    };

    await expect(
      evaluateConfidenceLedgerRiskSpendTwin({
        context: fixture.context,
        packetCandidate: unsupported,
        rawPacketBytes: fixture.rawPacketBytes,
        root: fixture.root,
      }),
    ).resolves.toEqual({
      status: "blocked",
      reason: "unsupported_or_out_of_model",
    });
  });

  it("evaluates the declared finite schema exactly and rejects an expanded proxy schema", async () => {
    const fixture = renderEvaluation();

    await expect(
      evaluateConfidenceLedgerRiskSpendTwin({
        context: {
          ...fixture.context,
          declaredFiniteSchema: [
            ...fixture.context.declaredFiniteSchema,
            "caller_declared_safe_marker",
          ],
        },
        packetCandidate: fixture.packet,
        rawPacketBytes: fixture.rawPacketBytes,
        root: fixture.root,
      }),
    ).resolves.toEqual({
      status: "blocked",
      reason: "unsupported_or_out_of_model",
    });
  });

  it("fails PV-K04 when a protected-use value is removed but its list and surface markers remain", async () => {
    const fixture = renderEvaluation();
    fixture.root
      .querySelector<HTMLElement>(
        '[data-confidence-leaf="posture.packet_may_not_use_for.0"]',
      )
      ?.remove();

    await expect(
      evaluateConfidenceLedgerRiskSpendTwin({
        context: fixture.context,
        packetCandidate: fixture.packet,
        rawPacketBytes: fixture.rawPacketBytes,
        root: fixture.root,
      }),
    ).resolves.toEqual({
      status: "blocked",
      reason: "model_observation_inconsistent",
    });
  });

  it("fails when a marker remains constant but its visible semantic value changes", async () => {
    const fixture = renderEvaluation();
    const leaf = fixture.root.querySelector<HTMLElement>(
      '[data-confidence-leaf="positive.population_state"]',
    );
    if (leaf === null) throw new Error("population state leaf is missing");
    leaf.textContent = "apparently_safe";

    await expect(
      evaluateConfidenceLedgerRiskSpendTwin({
        context: fixture.context,
        packetCandidate: fixture.packet,
        rawPacketBytes: fixture.rawPacketBytes,
        root: fixture.root,
      }),
    ).resolves.toEqual({
      status: "blocked",
      reason: "model_observation_inconsistent",
    });
  });

  it.each([
    "scope.scope_id",
    "actual.blocker",
    "class.check_refs.0",
    "definition.blocker",
    "route.blocker",
    "positive.authority_posture",
    "posture.coverage_assessment",
    "good_event.composition_rule",
  ])(
    "fails when the governed %s leaf is forged while its marker remains constant",
    async (field) => {
      const fixture = renderEvaluation();
      const leaf = fixture.root.querySelector<HTMLElement>(
        `[data-confidence-leaf="${field}"]`,
      );
      if (leaf === null) throw new Error(`${field} leaf is missing`);
      leaf.textContent = `${leaf.textContent ?? ""}-forged`;

      await expect(
        evaluateConfidenceLedgerRiskSpendTwin({
          context: fixture.context,
          packetCandidate: fixture.packet,
          rawPacketBytes: fixture.rawPacketBytes,
          root: fixture.root,
        }),
      ).resolves.toEqual({
        status: "blocked",
        reason: "model_observation_inconsistent",
      });
    },
  );

  it.each([
    [
      "hidden attribute",
      (element: HTMLElement) => element.setAttribute("hidden", ""),
    ],
    [
      "aria-hidden",
      (element: HTMLElement) => element.setAttribute("aria-hidden", "true"),
    ],
    [
      "display none",
      (element: HTMLElement) => (element.style.display = "none"),
    ],
    [
      "visibility hidden",
      (element: HTMLElement) => (element.style.visibility = "hidden"),
    ],
    ["zero opacity", (element: HTMLElement) => (element.style.opacity = "0")],
  ])(
    "rejects a %s semantic leaf instead of decoding hidden payload",
    async (_label, hide) => {
      const fixture = renderEvaluation();
      const leaf = fixture.root.querySelector<HTMLElement>(
        '[data-confidence-leaf="actual.instance_ref"]',
      );
      if (leaf === null) throw new Error("actual row leaf is missing");
      hide(leaf);

      await expect(
        evaluateConfidenceLedgerRiskSpendTwin({
          context: fixture.context,
          packetCandidate: fixture.packet,
          rawPacketBytes: fixture.rawPacketBytes,
          root: fixture.root,
        }),
      ).resolves.toEqual({
        status: "blocked",
        reason: "parser_or_schema_failure",
      });
    },
  );
});
