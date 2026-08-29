/* eslint-disable testing-library/no-container, testing-library/no-node-access -- adversarial DOM mutation is the twin falsifier */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import type { AvailableConfidenceLedgerRiskSpendPacket } from "@polisyos/runtime-api-client";
import { fireEvent, render } from "@testing-library/react";

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

function protectedQueries(): Readonly<
  Record<ConfidenceLedgerProtectedQuery, ConfidenceLedgerProtectedAnswer>
> {
  return Object.freeze(
    Object.fromEntries(
      CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA.map((query) => [
        query,
        "denied" as const,
      ]),
    ) as Record<
      ConfidenceLedgerProtectedQuery,
      ConfidenceLedgerProtectedAnswer
    >,
  );
}

function exactProjection(
  packet: AvailableConfidenceLedgerRiskSpendPacket,
  rawPacketBytes: Uint8Array,
): ConfidenceLedgerRiskSpendProjection {
  return {
    packet: packet as unknown as ConfidenceLedgerRiskSpendPacket,
    protectedQueries: protectedQueries(),
    rawPacketBytes,
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
}

function renderEvaluation({ openDialog = true } = {}) {
  const packet = availablePacket();
  const rawPacketBytes = new TextEncoder().encode(JSON.stringify(packet));
  const view = render(
    <LocaleProvider>
      <ConfidenceLedgerRiskSpend
        projection={exactProjection(packet, rawPacketBytes)}
      />
    </LocaleProvider>,
  );
  const root = view.container.querySelector<HTMLElement>(
    '[data-confidence-surface="risk-spend"]',
  );
  if (root === null) throw new Error("risk-spend surface did not render");
  if (openDialog) {
    const trigger = root.querySelector<HTMLButtonElement>("figure button");
    if (trigger === null) throw new Error("conditionality chip did not render");
    fireEvent.click(trigger);
  }
  return { packet, rawPacketBytes, root, view };
}

function evaluate(
  fixture: ReturnType<typeof renderEvaluation>,
  overrides: Partial<
    Parameters<typeof evaluateConfidenceLedgerRiskSpendTwin>[0]
  > = {},
) {
  return evaluateConfidenceLedgerRiskSpendTwin({
    evaluationMode: "exact_finite_schema",
    packetCandidate: fixture.packet,
    rawPacketBytes: fixture.rawPacketBytes,
    root: fixture.root,
    stepBudget: CONFIDENCE_LEDGER_LIVE_EVALUATION_BUDGET,
    ...overrides,
  });
}

function envelopeLeafPaths(value: unknown, prefix = ""): readonly string[] {
  if (Array.isArray(value)) {
    if (value.every((item) => item === null || typeof item !== "object")) {
      return [prefix];
    }
    return value.flatMap((item, index) =>
      envelopeLeafPaths(item, `${prefix}.${index}`),
    );
  }
  if (typeof value === "object" && value !== null) {
    return Object.entries(value).flatMap(([field, nested]) =>
      envelopeLeafPaths(nested, prefix ? `${prefix}.${field}` : field),
    );
  }
  return [prefix];
}

describe("confidence-ledger risk-spend production twin", () => {
  it("runs the shared preflight then independently reconciles all visible root and dialog text", async () => {
    const fixture = renderEvaluation();
    const result = await evaluate(fixture);

    expect(result.status === "blocked" ? result.reason : result.status).toBe(
      "exact",
    );
    if (result.status !== "exact") return;
    expect(result.byteTwin).toBe(fixture.rawPacketBytes);
    expect(Object.keys(result.protectedQueries)).toEqual(
      CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA,
    );
  });

  it("projects and behaviorally requires every packet-owned envelope leaf", async () => {
    const fixture = renderEvaluation();
    const dialog = document.querySelector<HTMLElement>(
      "[data-confidence-dialog-envelope-ref]",
    );
    if (dialog === null) throw new Error("bound dialog is missing");
    const observedFields = [
      ...dialog.querySelectorAll<HTMLElement>(
        '[data-confidence-text^="dialog.field."][data-confidence-text$=".label"]',
      ),
    ].map((element) =>
      (element.dataset.confidenceText ?? "")
        .replace(/^dialog\.field\./u, "")
        .replace(/\.label$/u, ""),
    );

    expect(observedFields).toEqual(
      envelopeLeafPaths(fixture.packet.payload.coverage_envelope),
    );

    const reasonLabel = dialog.querySelector<HTMLElement>(
      '[data-confidence-text="dialog.field.reason_codes.label"]',
    );
    if (reasonLabel === null || reasonLabel.parentElement === null) {
      throw new Error("reason-code envelope row is missing");
    }
    reasonLabel.parentElement.remove();
    await expect(evaluate(fixture)).resolves.toEqual({
      reason: "model_observation_inconsistent",
      status: "blocked",
    });
  });

  it("blocks DOM text work beyond the declared finite evaluator cap", async () => {
    const fixture = renderEvaluation();
    const leaf = fixture.root.querySelector<HTMLElement>(
      '[data-confidence-text="positive.empty.body"]',
    );
    if (leaf === null) throw new Error("positive empty copy is missing");
    leaf.append("x".repeat(80_001));

    await expect(evaluate(fixture)).resolves.toEqual({
      reason: "unsupported_or_out_of_model",
      status: "blocked",
    });
  });

  it.each([Number.NaN, Number.POSITIVE_INFINITY, 1.5, 0, 64])(
    "returns timeout for invalid or exhausted budget %s",
    async (stepBudget) => {
      const fixture = renderEvaluation();
      await expect(evaluate(fixture, { stepBudget })).resolves.toEqual({
        status: "blocked",
        reason: "timeout",
      });
    },
  );

  it("returns missing history when the governed root is absent", async () => {
    const fixture = renderEvaluation();
    await expect(evaluate(fixture, { root: null })).resolves.toEqual({
      status: "blocked",
      reason: "missing_input_or_incomplete_history",
    });
  });

  it("returns missing history when no bound dialog portal is open", async () => {
    const fixture = renderEvaluation({ openDialog: false });
    await expect(evaluate(fixture)).resolves.toEqual({
      status: "blocked",
      reason: "missing_input_or_incomplete_history",
    });
  });

  it("returns parser failure for malformed captured bytes", async () => {
    const fixture = renderEvaluation();
    await expect(
      evaluate(fixture, { rawPacketBytes: new TextEncoder().encode("{}") }),
    ).resolves.toEqual({
      status: "blocked",
      reason: "parser_or_schema_failure",
    });
  });

  it("returns unsupported for a novel transport schema", async () => {
    const fixture = renderEvaluation();
    await expect(
      evaluate(fixture, {
        packetCandidate: {
          ...fixture.packet,
          packet_schema_version:
            "policyos.runtime.confidence_ledger_risk_spend_packet.v2",
        },
      }),
    ).resolves.toEqual({
      status: "blocked",
      reason: "unsupported_or_out_of_model",
    });
  });

  it("returns an empty consistency set when valid candidate and byte observations disagree", async () => {
    const fixture = renderEvaluation();
    const captured = structuredClone(fixture.packet);
    captured.freshness.observed_at = "2026-02-11T12:00:01Z";
    await expect(
      evaluate(fixture, {
        rawPacketBytes: new TextEncoder().encode(JSON.stringify(captured)),
      }),
    ).resolves.toEqual({
      status: "blocked",
      reason: "empty_consistency_set",
    });
  });

  it("returns unproved approximation for sampled evaluation", async () => {
    const fixture = renderEvaluation();
    await expect(
      evaluate(fixture, { evaluationMode: "sampled_search" }),
    ).resolves.toEqual({
      status: "blocked",
      reason: "unproved_approximation",
    });
  });

  it.each(["class-spend", "instrument-definitions"])(
    "rejects reordered %s rows instead of reconstructing a ranking",
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
      await expect(evaluate(fixture)).resolves.toEqual({
        status: "blocked",
        reason: "model_observation_inconsistent",
      });
    },
  );

  it("rejects a visible unclassified authority claim", async () => {
    const fixture = renderEvaluation();
    const rogue = document.createElement("p");
    rogue.textContent = "PUBLIC authorized";
    fixture.root.append(rogue);

    await expect(evaluate(fixture)).resolves.toEqual({
      status: "blocked",
      reason: "parser_or_schema_failure",
    });
  });

  it("rejects a forged figure caption while all old semantic markers remain", async () => {
    const fixture = renderEvaluation();
    const caption = fixture.root.querySelector("figcaption");
    if (caption === null) throw new Error("figure caption is missing");
    caption.textContent = "Family total—narrowed claim satisfied";

    await expect(evaluate(fixture)).resolves.toEqual({
      status: "blocked",
      reason: "model_observation_inconsistent",
    });
  });

  it("binds the honest-zero register copy to packet-derived count and authority posture", async () => {
    const fixture = renderEvaluation();
    expect(fixture.root).toHaveTextContent("Positive promotion certificates");
    expect(fixture.root).toHaveTextContent(
      "0 issued · institutional authority unappointed · governed empty register",
    );
    const body = fixture.root.querySelector<HTMLElement>(
      '[data-confidence-text="positive.empty.body"]',
    );
    if (body === null) throw new Error("honest empty copy is missing");
    body.textContent = "1 issued · authority appointed";

    await expect(evaluate(fixture)).resolves.toEqual({
      status: "blocked",
      reason: "model_observation_inconsistent",
    });
  });

  it.each([
    ["dialog description", "dialog.description"],
    ["coverage reason", "dialog.field.reason_codes.value.0"],
    ["unknown remainder", "dialog.field.unknown_remainder.kind.value.0"],
    [
      "source verifier",
      "dialog.field.source_identities.1.verifier_ref.value.0",
    ],
  ])("rejects forged %s text in the bound portal", async (_label, marker) => {
    const fixture = renderEvaluation();
    const leaf = document.querySelector<HTMLElement>(
      `[data-confidence-text="${marker}"]`,
    );
    if (leaf === null) throw new Error(`${marker} is missing`);
    leaf.textContent = `${leaf.textContent ?? ""}-forged`;

    await expect(evaluate(fixture)).resolves.toEqual({
      status: "blocked",
      reason: "model_observation_inconsistent",
    });
  });

  it("rejects a portal whose envelope binding is removed", async () => {
    const fixture = renderEvaluation();
    const dialog = document.querySelector<HTMLElement>(
      "[data-confidence-dialog-envelope-ref]",
    );
    if (dialog === null) throw new Error("bound dialog is missing");
    dialog.removeAttribute("data-confidence-dialog-envelope-ref");

    await expect(evaluate(fixture)).resolves.toEqual({
      status: "blocked",
      reason: "missing_input_or_incomplete_history",
    });
  });

  it.each([
    [
      "standard visually-hidden class",
      (element: HTMLElement) => element.classList.add("visually-hidden"),
    ],
    [
      "clip rect",
      (element: HTMLElement) =>
        element.style.setProperty("clip", "rect(0px, 0px, 0px, 0px)"),
    ],
    [
      "clip path",
      (element: HTMLElement) => (element.style.clipPath = "inset(50%)"),
    ],
    [
      "one-pixel overflow",
      (element: HTMLElement) => {
        element.style.position = "absolute";
        element.style.width = "1px";
        element.style.height = "1px";
        element.style.overflow = "hidden";
      },
    ],
    [
      "offscreen position",
      (element: HTMLElement) => {
        element.style.position = "absolute";
        element.style.left = "-10000px";
      },
    ],
  ])("rejects a %s governed text ancestor", async (_label, hide) => {
    const fixture = renderEvaluation();
    const leaf = fixture.root.querySelector<HTMLElement>(
      '[data-confidence-leaf="actual.instance_ref"]',
    );
    if (leaf === null) throw new Error("actual ref is missing");
    hide(leaf.parentElement ?? leaf);

    await expect(evaluate(fixture)).resolves.toEqual({
      status: "blocked",
      reason: "parser_or_schema_failure",
    });
  });
});
