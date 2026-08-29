/* eslint-disable testing-library/no-container, testing-library/no-node-access -- native paint falsifiers deliberately mutate governed nodes */
import type { AvailableConfidenceLedgerRiskSpendPacket } from "@polisyos/runtime-api-client";
import { fireEvent, render } from "@testing-library/react";

import openApiDocument from "../../../../../../schemas/runtime_api_v1.openapi.json";
import type { ConfidenceLedgerRiskSpendProjection } from "@/features/runs/api/useConfidenceLedgerRiskSpend";
import { ConfidenceLedgerRiskSpend } from "@/features/runs/components/ConfidenceLedgerRiskSpend";
import {
  CONFIDENCE_LEDGER_LIVE_EVALUATION_BUDGET,
  CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA,
  type ConfidenceLedgerProtectedAnswer,
  type ConfidenceLedgerProtectedQuery,
  type ConfidenceLedgerRiskSpendPacket,
} from "@/features/runs/domain/confidenceLedgerRiskSpend";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

import { evaluateConfidenceLedgerRiskSpendTwin } from "./confidenceLedgerRiskSpendTwin";

function availablePacket(): AvailableConfidenceLedgerRiskSpendPacket {
  const openApi = openApiDocument as unknown as {
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

function renderNativeEvaluation() {
  const packet = availablePacket();
  const rawPacketBytes = new TextEncoder().encode(JSON.stringify(packet));
  const ownedBytes = new Uint8Array(rawPacketBytes);
  const projection: ConfidenceLedgerRiskSpendProjection = {
    capturedResponseBytes: Object.freeze({
      byteLength: ownedBytes.byteLength,
      copy: () => new Uint8Array(ownedBytes),
    }),
    packet: packet as unknown as ConfidenceLedgerRiskSpendPacket,
    protectedQueries: Object.freeze(
      Object.fromEntries(
        CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA.map((query) => [
          query,
          "denied" as const,
        ]),
      ) as Record<
        ConfidenceLedgerProtectedQuery,
        ConfidenceLedgerProtectedAnswer
      >,
    ),
    receipt: {
      observation_basis: "candidate_and_captured_bytes_independently_admitted",
      packet_availability: "available",
      packet_projection_hash: packet.projection_hash,
      protected_query_count: 9,
      schema_version:
        "policyos.runtime.confidence_ledger_protected_query_evaluation.v1",
    },
    status: "exact",
  };
  const view = render(
    <LocaleProvider>
      <ConfidenceLedgerRiskSpend projection={projection} />
    </LocaleProvider>,
  );
  const root = view.container.querySelector<HTMLElement>(
    '[data-confidence-surface="risk-spend"]',
  );
  if (root === null) throw new Error("risk-spend surface did not render");
  const trigger = root.querySelector<HTMLButtonElement>("figure button");
  if (trigger === null)
    throw new Error("conditionality trigger did not render");
  fireEvent.click(trigger);
  return { packet, rawPacketBytes, root };
}

function evaluateNative(
  fixture: ReturnType<typeof renderNativeEvaluation>,
  extra: Readonly<Record<string, unknown>> = {},
) {
  const input = {
    evaluationMode: "exact_finite_schema" as const,
    packetCandidate: fixture.packet,
    rawPacketBytes: fixture.rawPacketBytes,
    root: fixture.root,
    stepBudget: CONFIDENCE_LEDGER_LIVE_EVALUATION_BUDGET,
    ...extra,
  };
  return evaluateConfidenceLedgerRiskSpendTwin(input);
}

const NATIVE_PAINT_EFFECTS = [
  {
    apply: (element: HTMLElement) =>
      element.style.setProperty("-webkit-text-fill-color", "transparent"),
    name: "transparent text fill",
  },
  {
    apply: (element: HTMLElement) => {
      element.style.textShadow = "0 0 24px transparent";
    },
    name: "non-admitted text effect",
  },
  {
    apply: (element: HTMLElement) => {
      element.style.boxShadow = "inset 0 0 0 9999px currentcolor";
    },
    name: "non-admitted paint effect",
  },
  {
    apply: (element: HTMLElement) => {
      element.style.mixBlendMode = "difference";
    },
    name: "non-admitted compositing effect",
  },
] as const;

const NATIVE_EFFECT_CASES = NATIVE_PAINT_EFFECTS.flatMap((effect) =>
  (["leaf", "ancestor"] as const).map((target) => ({ ...effect, target })),
);

describe.runIf(
  typeof navigator !== "undefined" &&
    !navigator.userAgent.toLowerCase().includes("jsdom"),
)("confidence-ledger native Chromium visibility proof", () => {
  it("admits the baseline through the native finite paint grammar", async () => {
    const fixture = renderNativeEvaluation();

    const result = await evaluateNative(fixture);

    expect(result.status === "blocked" ? result.reason : result.status).toBe(
      "exact",
    );
  });

  it.each(NATIVE_EFFECT_CASES)(
    "blocks $name on a governed $target",
    async ({ apply, target }) => {
      const fixture = renderNativeEvaluation();
      const leaf = fixture.root.querySelector<HTMLElement>(
        '[data-confidence-leaf="actual.instance_ref"]',
      );
      if (leaf === null) throw new Error("governed leaf is missing");
      apply(target === "leaf" ? leaf : (leaf.parentElement ?? leaf));

      await expect(evaluateNative(fixture)).resolves.toEqual({
        reason: "unproved_approximation",
        status: "blocked",
      });
    },
  );

  it("cannot mint a visibility bypass by spoofing the UA and passing an arbitrary object", async () => {
    const fixture = renderNativeEvaluation();
    const leaf = fixture.root.querySelector<HTMLElement>(
      '[data-confidence-leaf="actual.instance_ref"]',
    );
    if (leaf === null) throw new Error("governed leaf is missing");
    leaf.style.setProperty("-webkit-text-fill-color", "transparent");
    const originalUserAgent = Object.getOwnPropertyDescriptor(
      navigator,
      "userAgent",
    );
    Object.defineProperty(navigator, "userAgent", {
      configurable: true,
      value: "Mozilla/5.0 jsdom native-spoof",
    });
    try {
      const productionExports = await import("./confidenceLedgerRiskSpendTwin");
      const legacyFactory = Reflect.get(
        productionExports,
        "createConfidenceLedgerTestVisibilityOracle",
      );
      const arbitraryObject =
        typeof legacyFactory === "function"
          ? Reflect.apply(legacyFactory, undefined, [document])
          : Object.freeze({
              document,
              kind: "explicit_jsdom_test_oracle",
              prove: () => "visible",
            });

      await expect(
        evaluateNative(fixture, { visibilityOracle: arbitraryObject }),
      ).resolves.toEqual({
        reason: "unproved_approximation",
        status: "blocked",
      });
    } finally {
      if (originalUserAgent === undefined) {
        Reflect.deleteProperty(navigator, "userAgent");
      } else {
        Object.defineProperty(navigator, "userAgent", originalUserAgent);
      }
    }
  });
});
