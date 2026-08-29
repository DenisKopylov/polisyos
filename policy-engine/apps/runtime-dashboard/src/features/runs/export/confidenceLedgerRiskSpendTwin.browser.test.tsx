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

const NATIVE_NORMALIZED_COLOR_FAMILIES = [
  {
    family: "legacy RGB",
    opaque: "rgba(17, 34, 51, 1)",
    tiny: "rgba(17, 34, 51, 0.0001)",
    zero: "rgba(17, 34, 51, 0)",
  },
  {
    family: "color(srgb)",
    opaque: "color(srgb 0.1 0.2 0.3 / 1)",
    tiny: "color(srgb 0.1 0.2 0.3 / 0.0001)",
    zero: "color(srgb 0.1 0.2 0.3 / 0)",
  },
  {
    family: "color(display-p3)",
    opaque: "color(display-p3 0.1 0.2 0.3 / 1)",
    tiny: "color(display-p3 0.1 0.2 0.3 / 0.0001)",
    zero: "color(display-p3 0.1 0.2 0.3 / 0)",
  },
  {
    family: "Lab",
    opaque: "lab(50% 20 30 / 1)",
    tiny: "lab(50% 20 30 / 0.0001)",
    zero: "lab(50% 20 30 / 0)",
  },
  {
    family: "LCH",
    opaque: "lch(50% 30 40 / 1)",
    tiny: "lch(50% 30 40 / 0.0001)",
    zero: "lch(50% 30 40 / 0)",
  },
  {
    family: "OKLab",
    opaque: "oklab(0.5 0.1 0.1 / 1)",
    tiny: "oklab(0.5 0.1 0.1 / 0.0001)",
    zero: "oklab(0.5 0.1 0.1 / 0)",
  },
  {
    family: "OKLCH",
    opaque: "oklch(0.5 0.1 40 / 1)",
    tiny: "oklch(0.5 0.1 40 / 0.0001)",
    zero: "oklch(0.5 0.1 40 / 0)",
  },
] as const;

const NATIVE_COLOR_CASES = NATIVE_NORMALIZED_COLOR_FAMILIES.flatMap((color) =>
  (["opaque", "zero", "tiny"] as const).flatMap((alpha) =>
    (["leaf", "ancestor"] as const).map((target) => ({
      alpha,
      color: color[alpha],
      expected: alpha === "opaque" ? "exact" : "unproved_approximation",
      family: color.family,
      target,
    })),
  ),
);

function governedLeaf(root: HTMLElement): HTMLElement {
  const leaf = root.querySelector<HTMLElement>(
    '[data-confidence-leaf="actual.instance_ref"]',
  );
  if (leaf === null) throw new Error("governed leaf is missing");
  return leaf;
}

function governedTextNode(leaf: HTMLElement): Text {
  const showText = leaf.ownerDocument.defaultView?.NodeFilter.SHOW_TEXT ?? 4;
  const walker = leaf.ownerDocument.createTreeWalker(leaf, showText);
  let node = walker.nextNode();
  while (node !== null) {
    if ((node.textContent ?? "").trim().length > 0) return node as Text;
    node = walker.nextNode();
  }
  throw new Error("governed text node is missing");
}

function coverGovernedText(
  leaf: HTMLElement,
  placement: "descendant" | "sibling",
  pointerEvents: "auto" | "none",
): void {
  const document = leaf.ownerDocument;
  const range = document.createRange();
  range.selectNodeContents(governedTextNode(leaf));
  const rect = range.getClientRects().item(0);
  if (rect === null || rect.width <= 0 || rect.height <= 0) {
    throw new Error("governed text range has no painted rectangle");
  }
  const overlay = document.createElement("span");
  Object.assign(overlay.style, {
    backgroundColor: "rgb(0, 0, 0)",
    height: `${rect.height}px`,
    left: `${rect.left}px`,
    pointerEvents,
    position: "fixed",
    top: `${rect.top}px`,
    width: `${rect.width}px`,
    zIndex: "2147483647",
  });
  if (placement === "descendant") {
    leaf.append(overlay);
    return;
  }
  const parent = leaf.parentElement;
  if (parent === null) throw new Error("governed leaf parent is missing");
  parent.append(overlay);
}

const NATIVE_OVERLAY_CASES = (["descendant", "sibling"] as const).flatMap(
  (placement) =>
    (["auto", "none"] as const).map((pointerEvents) => ({
      placement,
      pointerEvents,
    })),
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

  it.each(NATIVE_COLOR_CASES)(
    "$family $alpha color on a governed $target has the expected positive alpha proof",
    async ({ color, expected, target }) => {
      const fixture = renderNativeEvaluation();
      const leaf = governedLeaf(fixture.root);
      const styled = target === "leaf" ? leaf : (leaf.parentElement ?? leaf);
      styled.style.color = color;
      expect(styled.style.color).not.toBe("");

      const result = await evaluateNative(fixture);

      expect(result.status === "blocked" ? result.reason : result.status).toBe(
        expected,
      );
    },
  );

  it.each(NATIVE_OVERLAY_CASES)(
    "blocks an empty $placement overlay with pointer-events:$pointerEvents over governed glyphs",
    async ({ placement, pointerEvents }) => {
      const fixture = renderNativeEvaluation();
      coverGovernedText(governedLeaf(fixture.root), placement, pointerEvents);

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
