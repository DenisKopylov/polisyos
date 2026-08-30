/* eslint-disable testing-library/no-container, testing-library/no-node-access -- native paint falsifiers deliberately mutate governed nodes */
import type { AvailableConfidenceLedgerRiskSpendPacket } from "@polisyos/runtime-api-client";
import { fireEvent, render } from "@testing-library/react";
import { page } from "vitest/browser";

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
  return { packet, rawPacketBytes, root, view };
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

function appendOverlay(
  leaf: HTMLElement,
  placement: "descendant" | "sibling",
  pointerEvents: "auto" | "none",
  rect: Readonly<{
    height: number;
    left: number;
    top: number;
    width: number;
  }>,
): void {
  const parent = leaf.parentElement;
  if (parent === null) throw new Error("governed leaf parent is missing");
  const anchor = placement === "descendant" ? leaf : parent;
  const view = leaf.ownerDocument.defaultView;
  if (view === null) throw new Error("governed document view is missing");
  if (view.getComputedStyle(anchor).position === "static") {
    anchor.style.position = "relative";
  }
  const anchorRect = anchor.getBoundingClientRect();
  const overlay = leaf.ownerDocument.createElement("span");
  Object.assign(overlay.style, {
    backgroundColor: "rgb(0, 0, 0)",
    height: `${rect.height}px`,
    left: `${rect.left - anchorRect.left}px`,
    pointerEvents,
    position: "absolute",
    top: `${rect.top - anchorRect.top}px`,
    width: `${rect.width}px`,
    zIndex: "2147483647",
  });
  if (placement === "descendant") {
    leaf.append(overlay);
    return;
  }
  parent.append(overlay);
}

function governedTextRect(leaf: HTMLElement): DOMRect {
  const range = leaf.ownerDocument.createRange();
  range.selectNodeContents(governedTextNode(leaf));
  const rect = range.getClientRects().item(0);
  if (rect === null || rect.width <= 0 || rect.height <= 0) {
    throw new Error("governed text range has no painted rectangle");
  }
  return rect;
}

function coverGovernedTextAroundFormerSamples(
  leaf: HTMLElement,
  placement: "descendant" | "sibling",
  pointerEvents: "auto" | "none",
): void {
  const rect = governedTextRect(leaf);
  const holeWidth = rect.width * 0.0176;
  const segmentWidth = (rect.width - holeWidth) / 2;
  appendOverlay(leaf, placement, pointerEvents, {
    height: rect.height,
    left: rect.left,
    top: rect.top,
    width: segmentWidth,
  });
  appendOverlay(leaf, placement, pointerEvents, {
    height: rect.height,
    left: rect.right - segmentWidth,
    top: rect.top,
    width: segmentWidth,
  });
}

function intersectGovernedTextAtEdge(
  leaf: HTMLElement,
  placement: "descendant" | "sibling",
  pointerEvents: "auto" | "none",
): void {
  const rect = governedTextRect(leaf);
  const positiveSliver = Math.min(0.5, rect.width / 100);
  appendOverlay(leaf, placement, pointerEvents, {
    height: rect.height,
    left: rect.left,
    top: rect.top,
    width: positiveSliver,
  });
}

function coverGovernedTextWithPseudo(leaf: HTMLElement): void {
  const rect = governedTextRect(leaf);
  const document = leaf.ownerDocument;
  const parent = leaf.parentElement;
  const view = document.defaultView;
  if (parent === null) throw new Error("governed leaf parent is missing");
  if (view === null) throw new Error("governed document view is missing");
  if (view.getComputedStyle(parent).position === "static") {
    parent.style.position = "relative";
  }
  const parentRect = parent.getBoundingClientRect();
  const pseudoHost = document.createElement("span");
  pseudoHost.dataset.confidencePseudoOverlay = "range-region";
  Object.assign(pseudoHost.style, {
    height: "0px",
    left: `${rect.left - parentRect.left}px`,
    pointerEvents: "none",
    position: "absolute",
    top: `${rect.top - parentRect.top}px`,
    width: "0px",
  });
  const style = document.createElement("style");
  style.textContent = `
    [data-confidence-pseudo-overlay="range-region"]::before {
      background: rgb(0, 0, 0);
      content: "";
      height: ${rect.height}px;
      left: 0;
      pointer-events: none;
      position: absolute;
      top: 0;
      width: ${rect.width}px;
      z-index: 2147483647;
    }
  `;
  document.head.append(style);
  parent.append(pseudoHost);
}

const NATIVE_OVERLAY_CASES = (["descendant", "sibling"] as const).flatMap(
  (placement) =>
    (["auto", "none"] as const).map((pointerEvents) => ({
      placement,
      pointerEvents,
    })),
);

const NATIVE_RANGE_REGION_CASES = (["descendant", "sibling"] as const).flatMap(
  (placement) =>
    (["auto", "none"] as const).map((pointerEvents) => ({
      placement,
      pointerEvents,
    })),
);

const NATIVE_PAINT_EXTENSION_CASES = [
  {
    apply: (element: HTMLElement) => {
      element.style.boxShadow = "0 0 0 1000px black";
    },
    name: "box-shadow spread",
    remove: (element: HTMLElement) => {
      element.style.removeProperty("box-shadow");
    },
  },
  {
    apply: (element: HTMLElement) => {
      element.style.outline = "1000px solid black";
      element.style.outlineOffset = "1px";
    },
    name: "offset outline",
    remove: (element: HTMLElement) => {
      element.style.removeProperty("outline");
      element.style.removeProperty("outline-offset");
    },
  },
  {
    apply: (element: HTMLElement) => {
      element.style.filter = "drop-shadow(0 0 1000px black)";
    },
    name: "drop-shadow filter",
    remove: (element: HTMLElement) => {
      element.style.removeProperty("filter");
    },
  },
  {
    apply: (element: HTMLElement) => {
      element.style.textShadow = "0 0 1000px black";
    },
    name: "text-shadow blur",
    remove: (element: HTMLElement) => {
      element.style.removeProperty("text-shadow");
    },
  },
] as const;

function appendDisjointPaintSibling(
  root: HTMLElement,
  marker: string,
): HTMLElement {
  const leaf = governedLeaf(root);
  const parent = root.parentElement;
  if (parent === null) throw new Error("governed surface host is missing");
  const sibling = leaf.ownerDocument.createElement("span");
  sibling.dataset.confidencePaintExtension = marker;
  sibling.textContent = "x";
  Object.assign(sibling.style, {
    backgroundColor: "rgb(0, 0, 0)",
    color: "rgb(0, 0, 0)",
    fontSize: "1px",
    height: "1px",
    left: "0px",
    lineHeight: "1px",
    pointerEvents: "none",
    position: "fixed",
    top: "0px",
    width: "1px",
    zIndex: "2147483647",
  });
  parent.append(sibling);
  const siblingRect = sibling.getClientRects().item(0);
  if (
    siblingRect === null ||
    siblingRect.width <= 0 ||
    siblingRect.height <= 0
  ) {
    throw new Error("paint-extension sibling has no layout rectangle");
  }
  const textRect = governedTextRect(leaf);
  if (
    siblingRect.left < textRect.right &&
    siblingRect.right > textRect.left &&
    siblingRect.top < textRect.bottom &&
    siblingRect.bottom > textRect.top
  ) {
    throw new Error("paint-extension sibling layout intersects governed text");
  }
  return sibling;
}

function appendFirstLetterPaintExtension(
  root: HTMLElement,
): Readonly<{ host: HTMLElement; rule: HTMLStyleElement }> {
  const host = appendDisjointPaintSibling(root, "first-letter-text-shadow");
  const rule = host.ownerDocument.createElement("style");
  rule.dataset.confidencePaintExtensionRule = "first-letter-text-shadow";
  rule.textContent = `
    [data-confidence-paint-extension="first-letter-text-shadow"]::first-letter {}
  `;
  host.before(rule);
  return { host, rule };
}

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

  it.each(NATIVE_RANGE_REGION_CASES)(
    "blocks $placement overlays that cover the text around every former sample with pointer-events:$pointerEvents",
    async ({ placement, pointerEvents }) => {
      const fixture = renderNativeEvaluation();
      coverGovernedTextAroundFormerSamples(
        governedLeaf(fixture.root),
        placement,
        pointerEvents,
      );

      await expect(evaluateNative(fixture)).resolves.toEqual({
        reason: "unproved_approximation",
        status: "blocked",
      });
    },
  );

  it.each(NATIVE_RANGE_REGION_CASES)(
    "blocks a positive-area $placement sliver at the text edge with pointer-events:$pointerEvents",
    async ({ placement, pointerEvents }) => {
      const fixture = renderNativeEvaluation();
      intersectGovernedTextAtEdge(
        governedLeaf(fixture.root),
        placement,
        pointerEvents,
      );

      await expect(evaluateNative(fixture)).resolves.toEqual({
        reason: "unproved_approximation",
        status: "blocked",
      });
    },
  );

  it.each(NATIVE_PAINT_EXTENSION_CASES)(
    "admits a marked disjoint sibling after only $name is removed, then blocks the extension",
    async ({ apply, name, remove }) => {
      const fixture = renderNativeEvaluation();
      const sibling = appendDisjointPaintSibling(fixture.root, name);
      try {
        apply(sibling);
        remove(sibling);
        expect(sibling.dataset.confidencePaintExtension).toBe(name);
        await expect(evaluateNative(fixture)).resolves.toMatchObject({
          status: "exact",
        });

        apply(sibling);
        await expect(evaluateNative(fixture)).resolves.toEqual({
          reason: "unproved_approximation",
          status: "blocked",
        });
      } finally {
        sibling.remove();
        fixture.view.unmount();
      }
    },
  );

  it("blocks a first-letter paint extension while its host and rule markers remain", async () => {
    const fixture = renderNativeEvaluation();
    const extension = appendFirstLetterPaintExtension(fixture.root);
    try {
      await expect(evaluateNative(fixture)).resolves.toMatchObject({
        status: "exact",
      });

      extension.rule.textContent = `
        [data-confidence-paint-extension="first-letter-text-shadow"]::first-letter {
          text-shadow: 0 0 1000px black;
        }
      `;
      expect(extension.host.dataset.confidencePaintExtension).toBe(
        "first-letter-text-shadow",
      );
      expect(extension.rule.dataset.confidencePaintExtensionRule).toBe(
        "first-letter-text-shadow",
      );
      await expect(evaluateNative(fixture)).resolves.toEqual({
        reason: "unproved_approximation",
        status: "blocked",
      });
    } finally {
      extension.rule.remove();
      extension.host.remove();
      fixture.view.unmount();
    }
  });

  it("blocks an open shadow-root paint extension while its host marker remains", async () => {
    const fixture = renderNativeEvaluation();
    const host = appendDisjointPaintSibling(fixture.root, "open-shadow-root");
    try {
      await expect(evaluateNative(fixture)).resolves.toMatchObject({
        status: "exact",
      });

      const shadow = host.attachShadow({ mode: "open" });
      const extension = host.ownerDocument.createElement("span");
      extension.textContent = "x";
      Object.assign(extension.style, {
        boxShadow: "0 0 0 1000px black",
        display: "block",
        height: "1px",
        width: "1px",
      });
      shadow.append(extension);
      expect(host.dataset.confidencePaintExtension).toBe("open-shadow-root");
      await expect(evaluateNative(fixture)).resolves.toEqual({
        reason: "unproved_approximation",
        status: "blocked",
      });
    } finally {
      host.remove();
      fixture.view.unmount();
    }
  });

  // DS17 MACHINE-twin threat-model amendment: closed-root inspection requires equal script privilege.
  it("documents the declared limitation: closed shadow roots require script privilege equal to the twin's own", async () => {
    const fixture = renderNativeEvaluation();
    const host = appendDisjointPaintSibling(fixture.root, "closed-shadow-root");
    host.textContent = "";
    try {
      await expect(evaluateNative(fixture)).resolves.toMatchObject({
        status: "exact",
      });
      const baselinePixels = await page.screenshot({
        element: governedLeaf(fixture.root),
        save: false,
      });

      const shadow = host.attachShadow({ mode: "closed" });
      const extension = host.ownerDocument.createElement("span");
      extension.textContent = "x";
      Object.assign(extension.style, {
        boxShadow: "0 0 0 1000px black",
        display: "block",
        height: "1px",
        width: "1px",
      });
      shadow.append(extension);
      expect(host.shadowRoot).toBeNull();
      expect(host.dataset.confidencePaintExtension).toBe("closed-shadow-root");
      const coveredPixels = await page.screenshot({
        element: governedLeaf(fixture.root),
        save: false,
      });
      expect(coveredPixels).not.toBe(baselinePixels);
      await expect(evaluateNative(fixture)).resolves.toMatchObject({
        status: "exact",
      });
    } finally {
      host.remove();
      fixture.view.unmount();
    }
  });

  it("blocks text paint escaping a disjoint element rectangle while its marker remains", async () => {
    const fixture = renderNativeEvaluation();
    const leaf = governedLeaf(fixture.root);
    const host = appendDisjointPaintSibling(
      fixture.root,
      "text-indent-overflow",
    );
    Object.assign(host.style, {
      display: "block",
      left: "500px",
      top: "100px",
    });
    try {
      await expect(evaluateNative(fixture)).resolves.toMatchObject({
        status: "exact",
      });

      host.style.textIndent = "-400px";
      const hostRect = host.getClientRects().item(0);
      const textNode = host.firstChild;
      if (hostRect === null || !(textNode instanceof Text)) {
        throw new Error("text-paint extension geometry is unavailable");
      }
      const range = host.ownerDocument.createRange();
      range.selectNodeContents(textNode);
      const textRect = range.getClientRects().item(0);
      if (textRect === null) {
        throw new Error("text-paint extension range is unavailable");
      }
      const governedRect = governedTextRect(leaf);
      expect(hostRect.left).toBeGreaterThanOrEqual(governedRect.right);
      expect(
        textRect.left < governedRect.right &&
          textRect.right > governedRect.left,
      ).toBe(true);
      expect(host.dataset.confidencePaintExtension).toBe(
        "text-indent-overflow",
      );
      await expect(evaluateNative(fixture)).resolves.toEqual({
        reason: "unproved_approximation",
        status: "blocked",
      });
    } finally {
      host.remove();
      fixture.view.unmount();
    }
  });

  it("blocks generated pseudo paint over a governed text range", async () => {
    const fixture = renderNativeEvaluation();
    coverGovernedTextWithPseudo(governedLeaf(fixture.root));

    await expect(evaluateNative(fixture)).resolves.toEqual({
      reason: "unproved_approximation",
      status: "blocked",
    });
  });

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
