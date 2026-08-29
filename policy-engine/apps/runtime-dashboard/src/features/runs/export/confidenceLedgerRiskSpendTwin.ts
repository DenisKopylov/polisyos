import type { ConditionalDeltaAmount } from "@polisyos/runtime-api-client";

import {
  CONFIDENCE_LEDGER_LIVE_EVALUATION_BUDGET,
  CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA,
  confidenceLedgerPromotionBlockers,
  evaluateConfidenceLedgerProtectedQuery,
  orderedConfidenceLedgerActualRows,
  type ConfidenceLedgerProtectedAnswer,
  type ConfidenceLedgerProtectedQuery,
  type ConfidenceLedgerCapturedResponseBytes,
  type ConfidenceLedgerRiskSpendPacket,
  type ConfidenceLedgerSafetyBlockedReason,
} from "@/features/runs/domain/confidenceLedgerRiskSpend";
import en from "@/shared/i18n/locales/en.json";
import uk from "@/shared/i18n/locales/uk.json";

export type ConfidenceLedgerTwinBlockedReason =
  ConfidenceLedgerSafetyBlockedReason;

export type ConfidenceLedgerRiskSpendTwinResult =
  | Readonly<{
      byteTwin: ConfidenceLedgerCapturedResponseBytes;
      protectedQueries: Readonly<
        Record<ConfidenceLedgerProtectedQuery, ConfidenceLedgerProtectedAnswer>
      >;
      status: "exact";
    }>
  | Readonly<{
      reason: ConfidenceLedgerTwinBlockedReason;
      status: "blocked";
    }>;

type EvaluateConfidenceLedgerRiskSpendTwinInput = Readonly<{
  evaluationMode: "exact_finite_schema" | "sampled_search";
  packetCandidate: unknown;
  rawPacketBytes: Uint8Array;
  root: HTMLElement | null;
  stepBudget: number;
}>;

type VisibleFigure = Readonly<{
  canonicalDecimal: string;
  rationalDisplay: string;
  riders: string;
}>;

type VisibleSemanticLeaf = Readonly<{
  field: string;
  value: string;
}>;

type VisibleSemanticList = Readonly<{
  field: string;
  itemCount: number;
}>;

type VisibleSemanticProjection = Readonly<{
  actualRefs: readonly string[];
  actualRoles: readonly string[];
  classes: readonly string[];
  definitions: readonly string[];
  figures: readonly VisibleFigure[];
  packetMayNotUseFor: readonly string[];
  positiveAppointmentState: readonly string[];
  positivePopulationCount: readonly string[];
  positivePopulationState: readonly string[];
  promotionBlockers: readonly string[];
  replayAddress: readonly string[];
  replayPins: Readonly<Record<string, readonly string[]>>;
  routes: readonly string[];
  semanticLeaves: readonly VisibleSemanticLeaf[];
  semanticLists: readonly VisibleSemanticList[];
  sections: readonly string[];
  sourceArtifactHash: readonly string[];
  sourcePath: readonly string[];
  sourceProvenance: readonly string[];
  sourceValidationStatus: readonly string[];
  sourceValidatorId: readonly string[];
  sourceValidatorVersion: readonly string[];
  workerReceiptHash: readonly string[];
  workerReceiptRef: readonly string[];
  envelopeMayNotUseFor: readonly string[];
}>;

class SemanticDomError extends Error {}
class VisibilityUnprovedError extends Error {}

type VisibilityProof = "hidden" | "unproved" | "visible";

function blocked(
  reason: ConfidenceLedgerTwinBlockedReason,
): ConfidenceLedgerRiskSpendTwinResult {
  return Object.freeze({ reason, status: "blocked" });
}

function compactCss(value: string): string {
  return value.toLowerCase().replaceAll(" ", "").replaceAll("\n", "");
}

function cssValue(style: CSSStyleDeclaration, property: string): string {
  return compactCss(style.getPropertyValue(property));
}

function isOpaqueColor(value: string): boolean {
  return (
    value.length > 0 &&
    value !== "transparent" &&
    value !== "rgba(0,0,0,0)" &&
    !/^rgba\([^)]*,0(?:\.0+)?\)$/u.test(value) &&
    !/^hsla\([^)]*,0(?:\.0+)?\)$/u.test(value) &&
    !/^oklch\([^/]+\/0(?:\.0+)?\)$/u.test(value)
  );
}

function isZeroCssLength(value: string): boolean {
  return /^(?:0|0\.0+)(?:px|em|rem|%)?$/u.test(value);
}

function isPureTranslation(value: string): boolean {
  if (value === "none") return true;
  if (/^-?[\d.]+(?:px|%)-?[\d.]+(?:px|%)$/u.test(value)) return true;
  if (/^matrix\(1,0,0,1,-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?\)$/u.test(value)) {
    return true;
  }
  return /^translate(?:3d)?\(-?[\d.]+(?:px|%),-?[\d.]+(?:px|%)(?:,0(?:px)?)?\)$/u.test(
    value,
  );
}

const ADMITTED_INLINE_VISIBILITY_PROPERTIES = new Set([
  "-webkit-text-fill-color",
  "-webkit-text-security",
  "-webkit-text-stroke-width",
  "backdrop-filter",
  "background-blend-mode",
  "box-shadow",
  "clip",
  "clip-path",
  "color",
  "content-visibility",
  "display",
  "filter",
  "font-size",
  "height",
  "isolation",
  "left",
  "mask",
  "mask-image",
  "mix-blend-mode",
  "opacity",
  "overflow",
  "overflow-x",
  "overflow-y",
  "paint-order",
  "perspective",
  "position",
  "rotate",
  "scale",
  "text-decoration-line",
  "text-emphasis-style",
  "text-indent",
  "text-shadow",
  "text-transform",
  "top",
  "transform",
  "translate",
  "visibility",
  "width",
  "will-change",
  "-webkit-mask-image",
]);

function finitePaintGrammarProof(
  element: HTMLElement,
  style: CSSStyleDeclaration,
  allowGeometricProof: boolean,
): VisibilityProof {
  for (let index = 0; index < element.style.length; index += 1) {
    const property = element.style.item(index);
    if (
      !property.startsWith("--") &&
      !ADMITTED_INLINE_VISIBILITY_PROPERTIES.has(property)
    ) {
      return "unproved";
    }
  }
  const color = cssValue(style, "color");
  const textFill = cssValue(style, "-webkit-text-fill-color");
  if (!isOpaqueColor(color)) return "hidden";
  if (
    !isOpaqueColor(textFill) ||
    (textFill !== "currentcolor" && textFill !== color)
  ) {
    return "unproved";
  }
  const exactDefaults: Readonly<Record<string, readonly string[]>> = {
    "-webkit-text-security": ["none"],
    "backdrop-filter": ["none"],
    "background-blend-mode": ["normal"],
    clip: ["auto"],
    "clip-path": ["none"],
    "content-visibility": ["visible"],
    filter: ["none"],
    isolation: ["auto", "isolate"],
    "mask-image": ["none"],
    "-webkit-mask-image": ["none"],
    "mix-blend-mode": ["normal"],
    "paint-order": ["normal"],
    perspective: ["none"],
    rotate: ["none"],
    scale: ["none", "1"],
    "text-decoration-line": ["none"],
    "text-emphasis-style": ["none"],
    "text-shadow": ["none"],
    "text-transform": ["none"],
    "will-change": ["auto"],
  };
  for (const [property, admitted] of Object.entries(exactDefaults)) {
    const value = cssValue(style, property);
    if (value.length === 0 || !admitted.includes(value)) {
      return "unproved";
    }
  }
  const strokeWidth = cssValue(style, "-webkit-text-stroke-width");
  if (strokeWidth.length === 0 || !isZeroCssLength(strokeWidth)) {
    return "unproved";
  }
  const boxShadow = cssValue(style, "box-shadow");
  if (boxShadow.length === 0 || boxShadow.includes("inset")) {
    return "unproved";
  }
  const opacity = Number.parseFloat(cssValue(style, "opacity"));
  if (!Number.isFinite(opacity) || opacity !== 1) {
    return "unproved";
  }
  const transform = cssValue(style, "transform");
  if (
    transform.length === 0 ||
    (!allowGeometricProof && transform !== "none") ||
    !isPureTranslation(transform)
  ) {
    return "unproved";
  }
  const translate = cssValue(style, "translate");
  if (
    translate.length === 0 ||
    (!allowGeometricProof && translate !== "none") ||
    !isPureTranslation(translate)
  ) {
    return "unproved";
  }
  return "visible";
}

function styleVisibilityProof(
  element: HTMLElement,
  style: CSSStyleDeclaration,
  allowGeometricProof: boolean,
): VisibilityProof {
  const contentVisibility = cssValue(style, "content-visibility");
  const overflowX = compactCss(
    `${cssValue(style, "overflow")} ${cssValue(style, "overflow-x")}`,
  );
  const overflowY = compactCss(
    `${cssValue(style, "overflow")} ${cssValue(style, "overflow-y")}`,
  );
  const width = Number.parseFloat(cssValue(style, "width"));
  const height = Number.parseFloat(cssValue(style, "height"));
  const opacity = Number.parseFloat(cssValue(style, "opacity"));
  const fontSize = Number.parseFloat(cssValue(style, "font-size"));
  const textIndent = Number.parseFloat(
    cssValue(style, "text-indent") || element.style.textIndent,
  );
  const left = Number.parseFloat(cssValue(style, "left") || element.style.left);
  const top = Number.parseFloat(cssValue(style, "top") || element.style.top);
  const positioned =
    cssValue(style, "position") === "absolute" ||
    cssValue(style, "position") === "fixed";
  const clipValues = [
    style.getPropertyValue("clip"),
    element.style.getPropertyValue("clip"),
  ];
  const clipPathValues = [cssValue(style, "clip-path"), element.style.clipPath];
  const filterValues = [cssValue(style, "filter"), element.style.filter];
  const transformValues = [
    cssValue(style, "transform"),
    element.style.transform,
  ];
  const clip = compactCss(clipValues.join(" ")).replaceAll(",", "");
  const clipPath = compactCss(clipPathValues.join(" "));
  const filter = compactCss(filterValues.join(" "));
  const transform = compactCss(transformValues.join(" "));
  const color = cssValue(style, "color");
  if (
    element.hidden ||
    element.getAttribute("aria-hidden") === "true" ||
    element.classList.contains("sr-only") ||
    element.classList.contains("visually-hidden") ||
    cssValue(style, "display") === "none" ||
    cssValue(style, "visibility") === "hidden" ||
    cssValue(style, "visibility") === "collapse" ||
    opacity === 0 ||
    contentVisibility === "hidden" ||
    fontSize === 0 ||
    color === "transparent" ||
    color === "rgba(0,0,0,0)" ||
    clip.includes("rect(0px0px0px0px)") ||
    clip.includes("rect(0000)") ||
    clipPath.includes("circle(0)") ||
    clipPath.includes("circle(0px)") ||
    clipPath.includes("inset(50%)") ||
    clipPath.includes("inset(100%)") ||
    filter.includes("opacity(0)") ||
    filter.includes("opacity(0%)") ||
    transform.includes("scale(0)") ||
    transform.includes("scale(0,0)") ||
    transform.includes("matrix(0,0,0,0,") ||
    (Number.isFinite(width) &&
      width <= 1 &&
      (overflowX.includes("hidden") || overflowX.includes("clip"))) ||
    (Number.isFinite(height) &&
      height <= 1 &&
      (overflowY.includes("hidden") || overflowY.includes("clip"))) ||
    (positioned && Number.isFinite(left) && Math.abs(left) >= 10_000) ||
    (positioned && Number.isFinite(top) && Math.abs(top) >= 10_000) ||
    (Number.isFinite(textIndent) && Math.abs(textIndent) >= 10_000)
  ) {
    return "hidden";
  }
  return finitePaintGrammarProof(element, style, allowGeometricProof);
}

type ScrollSnapshot = Readonly<{
  element: HTMLElement;
  left: number;
  top: number;
}>;

class RenderedVisibilitySession {
  readonly #cache = new WeakMap<HTMLElement, VisibilityProof>();
  readonly #chainVisible = new WeakSet<HTMLElement>();
  readonly #document: Document;
  readonly #focus: Element | null;
  readonly #scroll: readonly ScrollSnapshot[];
  readonly #view: Window & typeof globalThis;
  readonly #windowX: number;
  readonly #windowY: number;
  #remainingWork: number;

  constructor(document: Document, workBudget: number) {
    const view = document.defaultView;
    if (view === null) {
      throw new VisibilityUnprovedError("document view is unavailable");
    }
    this.#document = document;
    this.#view = view;
    const documentElement = document.documentElement as HTMLElement & {
      checkVisibility?: () => boolean;
    };
    if (
      typeof documentElement.checkVisibility !== "function" ||
      typeof document.elementsFromPoint !== "function" ||
      typeof documentElement.scrollIntoView !== "function" ||
      typeof view.scrollTo !== "function"
    ) {
      throw new VisibilityUnprovedError(
        "native rendered visibility APIs are unavailable",
      );
    }
    this.#remainingWork = workBudget;
    this.#focus = document.activeElement;
    this.#windowX = view.scrollX;
    this.#windowY = view.scrollY;
    this.#scroll = [...document.querySelectorAll<HTMLElement>("*")].map(
      (element) =>
        Object.freeze({
          element,
          left: element.scrollLeft,
          top: element.scrollTop,
        }),
    );
    this.consume(this.#scroll.length);
  }

  consume(work: number): void {
    this.#remainingWork -= work;
    if (this.#remainingWork < 0) {
      throw new VisibilityUnprovedError("rendered visibility budget exhausted");
    }
  }

  prove(element: HTMLElement, boundary: HTMLElement): VisibilityProof {
    this.consume(1);
    if (!boundary.contains(element) && boundary !== element) return "unproved";
    const newlyProved: HTMLElement[] = [];
    let current: HTMLElement | null = element;
    while (current !== null) {
      this.consume(4);
      if (this.#chainVisible.has(current)) {
        newlyProved.forEach((proved) => this.#chainVisible.add(proved));
        return "visible";
      }
      const cached = this.#cache.get(current);
      if (cached !== undefined) {
        if (cached !== "visible") return cached;
        newlyProved.push(current);
        current = current.parentElement;
        continue;
      }
      const proof = this.proveNativeElement(current);
      this.#cache.set(current, proof);
      if (proof !== "visible") return proof;
      newlyProved.push(current);
      current = current.parentElement;
    }
    newlyProved.forEach((proved) => this.#chainVisible.add(proved));
    return "visible";
  }

  private proveNativeElement(element: HTMLElement): VisibilityProof {
    const nativeElement = element as HTMLElement & {
      checkVisibility?: (options?: {
        checkOpacity?: boolean;
        checkVisibilityCSS?: boolean;
        contentVisibilityAuto?: boolean;
      }) => boolean;
    };
    if (
      typeof nativeElement.checkVisibility !== "function" ||
      typeof this.#document.elementsFromPoint !== "function" ||
      typeof element.scrollIntoView !== "function" ||
      typeof this.#view.scrollTo !== "function"
    ) {
      return "unproved";
    }
    let platformVisible: boolean;
    try {
      platformVisible = nativeElement.checkVisibility({
        checkOpacity: true,
        checkVisibilityCSS: true,
        contentVisibilityAuto: true,
      });
    } catch {
      return "unproved";
    }
    if (!platformVisible) return "hidden";
    const styleProof = styleVisibilityProof(
      element,
      this.#view.getComputedStyle(element),
      true,
    );
    if (styleProof !== "visible") return styleProof;
    this.consume(2);
    try {
      for (const pseudo of ["::before", "::after"] as const) {
        const content = cssValue(
          this.#view.getComputedStyle(element, pseudo),
          "content",
        );
        if (content !== "none" && content !== "normal") return "unproved";
      }
    } catch {
      return "unproved";
    }
    try {
      element.scrollIntoView({ block: "center", inline: "center" });
    } catch {
      return "unproved";
    }
    const rect = element.getBoundingClientRect();
    if (
      !Number.isFinite(rect.left) ||
      !Number.isFinite(rect.top) ||
      !Number.isFinite(rect.width) ||
      !Number.isFinite(rect.height)
    ) {
      return "unproved";
    }
    if (rect.width <= 0 || rect.height <= 0) return "hidden";
    const viewportWidth = this.#view.innerWidth;
    const viewportHeight = this.#view.innerHeight;
    const left = Math.max(0, rect.left);
    const right = Math.min(viewportWidth, rect.right);
    const top = Math.max(0, rect.top);
    const bottom = Math.min(viewportHeight, rect.bottom);
    if (right <= left || bottom <= top) return "unproved";
    const x = left + (right - left) / 2;
    const y = top + (bottom - top) / 2;
    const paintedStack = this.#document.elementsFromPoint(x, y);
    return paintedStack.some(
      (painted) => painted === element || element.contains(painted),
    )
      ? "visible"
      : "unproved";
  }

  restore(): boolean {
    let restored = true;
    try {
      if (this.#document.activeElement !== this.#focus) {
        const focus = this.#focus;
        if (focus instanceof this.#view.HTMLElement) {
          focus.focus({ preventScroll: true });
        } else {
          restored = false;
        }
      }
      for (const snapshot of this.#scroll) {
        snapshot.element.scrollLeft = snapshot.left;
        snapshot.element.scrollTop = snapshot.top;
      }
      this.#view.scrollTo(this.#windowX, this.#windowY);
      restored =
        restored &&
        this.#document.activeElement === this.#focus &&
        this.#view.scrollX === this.#windowX &&
        this.#view.scrollY === this.#windowY &&
        this.#scroll.every(
          (snapshot) =>
            snapshot.element.scrollLeft === snapshot.left &&
            snapshot.element.scrollTop === snapshot.top,
        );
    } catch {
      restored = false;
    }
    return restored;
  }
}

function assertVisible(
  element: HTMLElement,
  boundary: HTMLElement,
  visibility: RenderedVisibilitySession,
): void {
  const proof = visibility.prove(element, boundary);
  if (proof === "hidden") {
    throw new SemanticDomError("semantic element is hidden");
  }
  if (proof === "unproved") {
    throw new VisibilityUnprovedError(
      `semantic visibility is unproved for ${element.tagName}:${element.dataset.confidenceText ?? element.dataset.confidenceLeaf ?? "unclassified"}`,
    );
  }
}

function visibleText(
  element: HTMLElement,
  root: HTMLElement,
  visibility: RenderedVisibilitySession,
): string {
  assertVisible(element, root, visibility);
  const value = element.textContent?.trim() ?? "";
  if (value.length === 0) {
    throw new SemanticDomError("semantic element has no visible text");
  }
  return value;
}

function directListItems(list: HTMLElement): readonly HTMLElement[] {
  return [...list.children].filter(
    (child): child is HTMLElement =>
      child instanceof HTMLElement && child.tagName === "LI",
  );
}

function leafValues(
  leaves: readonly HTMLElement[],
  root: HTMLElement,
  field: string,
  visibility: RenderedVisibilitySession,
): readonly string[] {
  return leaves
    .filter((leaf) => leaf.dataset.confidenceLeaf === field)
    .map((leaf) => visibleText(leaf, root, visibility));
}

function indexedLeafValues(
  leaves: readonly HTMLElement[],
  root: HTMLElement,
  field: string,
  visibility: RenderedVisibilitySession,
): readonly string[] {
  const prefix = `${field}.`;
  return leaves
    .filter((leaf) => {
      const candidate = leaf.dataset.confidenceLeaf;
      return (
        candidate?.startsWith(prefix) === true && candidate !== `${field}.count`
      );
    })
    .map((leaf) => visibleText(leaf, root, visibility));
}

function decodeOrderedRowField(
  root: HTMLElement,
  listName: string,
  field: string,
  visibility: RenderedVisibilitySession,
): readonly string[] {
  const lists = [
    ...root.querySelectorAll<HTMLElement>("[data-confidence-list]"),
  ].filter((list) => list.dataset.confidenceList === listName);
  if (lists.length !== 1) return [];
  return directListItems(lists[0]).map((item) => {
    const matches = [
      ...item.querySelectorAll<HTMLElement>("[data-confidence-leaf]"),
    ].filter((leaf) => leaf.dataset.confidenceLeaf === field);
    if (matches.length !== 1) return "";
    return visibleText(matches[0], root, visibility);
  });
}

function decodeVisibleProjection(
  root: HTMLElement,
  visibility: RenderedVisibilitySession,
): VisibleSemanticProjection {
  const forbiddenPayloadSelector =
    'script[type="application/json"], input[type="hidden"], [data-confidence-payload], [data-testid]';
  if (
    root.matches(forbiddenPayloadSelector) ||
    root.querySelector(forbiddenPayloadSelector) !== null
  ) {
    throw new SemanticDomError(
      "raw, hidden, or test-only payload marker detected",
    );
  }
  const semanticElements = [
    ...root.querySelectorAll<HTMLElement>(
      "[data-confidence-leaf], [data-confidence-list], [data-confidence-section]",
    ),
  ];
  semanticElements.forEach((element) => {
    assertVisible(element, root, visibility);
  });
  const leaves = semanticElements.filter(
    (element) => element.dataset.confidenceLeaf !== undefined,
  );
  const sections = semanticElements
    .filter((element) => element.dataset.confidenceSection !== undefined)
    .map((element) => element.dataset.confidenceSection ?? "");
  const semanticLeaves = leaves.map((leaf) =>
    Object.freeze({
      field: leaf.dataset.confidenceLeaf ?? "",
      value: visibleText(leaf, root, visibility),
    }),
  );
  const semanticLists = semanticElements
    .filter((element) => element.dataset.confidenceList !== undefined)
    .map((list) =>
      Object.freeze({
        field: list.dataset.confidenceList ?? "",
        itemCount: directListItems(list).length,
      }),
    );
  const figures = [...root.querySelectorAll<HTMLElement>("figure")].map(
    (figure): VisibleFigure => {
      assertVisible(figure, root, visibility);
      const readSingle = (field: string): string => {
        const matches = [
          ...figure.querySelectorAll<HTMLElement>("[data-confidence-leaf]"),
        ].filter((leaf) => leaf.dataset.confidenceLeaf === field);
        if (matches.length !== 1) {
          throw new SemanticDomError(`amount figure ${field} is not singular`);
        }
        return visibleText(matches[0], root, visibility);
      };
      return Object.freeze({
        canonicalDecimal: readSingle("canonical-decimal"),
        rationalDisplay: readSingle("rational-display"),
        riders: readSingle("conditionality-riders"),
      });
    },
  );
  const replayPinFields = [
    "artifact_content_hash",
    "projection_hash",
    "projection_rule_version",
    "source_as_of",
    "source_dependency_hash",
  ] as const;
  return Object.freeze({
    actualRefs: decodeOrderedRowField(
      root,
      "actual-rows",
      "actual.instance_ref",
      visibility,
    ),
    actualRoles: decodeOrderedRowField(
      root,
      "actual-rows",
      "actual.certificate_role",
      visibility,
    ),
    classes: decodeOrderedRowField(
      root,
      "class-spend",
      "class.obligation_class",
      visibility,
    ),
    definitions: decodeOrderedRowField(
      root,
      "instrument-definitions",
      "definition.instrument_id",
      visibility,
    ),
    envelopeMayNotUseFor: indexedLeafValues(
      leaves,
      root,
      "posture.envelope_may_not_use_for",
      visibility,
    ),
    figures,
    packetMayNotUseFor: indexedLeafValues(
      leaves,
      root,
      "posture.packet_may_not_use_for",
      visibility,
    ),
    positiveAppointmentState: leafValues(
      leaves,
      root,
      "positive.appointment_sufficiency_state",
      visibility,
    ),
    positivePopulationCount: leafValues(
      leaves,
      root,
      "positive.population_count",
      visibility,
    ),
    positivePopulationState: leafValues(
      leaves,
      root,
      "positive.population_state",
      visibility,
    ),
    promotionBlockers: indexedLeafValues(
      leaves,
      root,
      "positive.promotion_blockers",
      visibility,
    ),
    replayAddress: leafValues(leaves, root, "replay.address", visibility),
    replayPins: Object.freeze(
      Object.fromEntries(
        replayPinFields.map((field) => [
          field,
          leafValues(leaves, root, `replay.${field}`, visibility),
        ]),
      ),
    ),
    routes: decodeOrderedRowField(
      root,
      "certificate-routes",
      "route.certificate_class",
      visibility,
    ),
    semanticLeaves,
    semanticLists,
    sections,
    sourceArtifactHash: leafValues(
      leaves,
      root,
      "source.artifact_content_hash",
      visibility,
    ),
    sourcePath: leafValues(leaves, root, "source.relative_path", visibility),
    sourceProvenance: indexedLeafValues(
      leaves,
      root,
      "source.provenance",
      visibility,
    ),
    sourceValidationStatus: leafValues(
      leaves,
      root,
      "source.validation_status",
      visibility,
    ),
    sourceValidatorId: leafValues(
      leaves,
      root,
      "source.validator_id",
      visibility,
    ),
    sourceValidatorVersion: leafValues(
      leaves,
      root,
      "source.validator_version",
      visibility,
    ),
    workerReceiptHash: leafValues(
      leaves,
      root,
      "source.worker_receipt_hash",
      visibility,
    ),
    workerReceiptRef: leafValues(
      leaves,
      root,
      "source.worker_receipt_ref",
      visibility,
    ),
  });
}

function figureProjection(amount: ConditionalDeltaAmount): VisibleFigure {
  return Object.freeze({
    canonicalDecimal: amount.canonical_decimal,
    rationalDisplay: amount.rational_display,
    riders: `${amount.declared_set_rider} — ${amount.locality_rider}`,
  });
}

function expectedFigureAmounts(
  packet: Extract<
    ConfidenceLedgerRiskSpendPacket,
    { availability: "available" }
  >,
): readonly ConditionalDeltaAmount[] {
  const body = packet.payload;
  return [
    ...orderedConfidenceLedgerActualRows(packet).map((row) => row.spend),
    body.scope_total_risk_spend.allocation,
    body.scope_total_risk_spend.spent,
    body.scope_total_risk_spend.remaining,
    body.scope_total_risk_spend.overspend_amount,
    ...body.obligation_class_risk_spend.flatMap((row) => [
      row.allocation,
      row.spent,
      row.remaining,
      row.overspend_amount,
    ]),
  ];
}

function expectedFigures(
  packet: Extract<
    ConfidenceLedgerRiskSpendPacket,
    { availability: "available" }
  >,
): readonly VisibleFigure[] {
  return expectedFigureAmounts(packet).map(figureProjection);
}

function semanticLeaf(
  field: string,
  value: boolean | number | string | null,
): VisibleSemanticLeaf {
  return Object.freeze({
    field,
    value: value === null ? "null" : String(value),
  });
}

function appendSemanticList(
  leaves: VisibleSemanticLeaf[],
  lists: VisibleSemanticList[],
  field: string,
  values: readonly string[],
): void {
  if (values.length === 0) {
    leaves.push(semanticLeaf(`${field}.count`, 0));
    return;
  }
  lists.push(Object.freeze({ field, itemCount: values.length }));
  values.forEach((value, index) => {
    leaves.push(semanticLeaf(`${field}.${index}`, value));
  });
}

function appendAmountLeaves(
  leaves: VisibleSemanticLeaf[],
  amount: ConditionalDeltaAmount,
): void {
  leaves.push(
    semanticLeaf("rational-display", amount.rational_display),
    semanticLeaf("canonical-decimal", amount.canonical_decimal),
    semanticLeaf(
      "conditionality-riders",
      `${amount.declared_set_rider} — ${amount.locality_rider}`,
    ),
  );
}

function expectedSemanticDom(
  packet: Extract<
    ConfidenceLedgerRiskSpendPacket,
    { availability: "available" }
  >,
): Readonly<{
  leaves: readonly VisibleSemanticLeaf[];
  lists: readonly VisibleSemanticList[];
}> {
  const body = packet.payload;
  const leaves: VisibleSemanticLeaf[] = [];
  const lists: VisibleSemanticList[] = [];
  const actualRows = orderedConfidenceLedgerActualRows(packet);

  lists.push(
    Object.freeze({ field: "actual-rows", itemCount: actualRows.length }),
  );
  actualRows.forEach((row) => {
    leaves.push(
      semanticLeaf("actual.instance_ref", row.instance_ref),
      semanticLeaf("actual.certificate_role", row.certificate_role),
      semanticLeaf("actual.instrument_id", row.instrument_id),
      semanticLeaf("actual.instrument_family", row.instrument_family),
      semanticLeaf("actual.obligation_class", row.obligation_class),
      semanticLeaf("actual.execution_status", row.execution_status),
      semanticLeaf("actual.outcome", row.outcome),
      semanticLeaf("actual.certificate_ref", row.certificate_ref),
      semanticLeaf("actual.certificate_class", row.certificate_class),
      semanticLeaf("actual.certificate_route_ref", row.certificate_route_ref),
      semanticLeaf("actual.anytime_valid", row.anytime_valid),
      semanticLeaf("actual.eligible_for_promotion", row.eligible_for_promotion),
      semanticLeaf("actual.supports_obligation", row.supports_obligation),
      semanticLeaf("actual.blocker", row.blocker),
      semanticLeaf("actual.proof_profile_id", row.proof_profile_id),
      semanticLeaf(
        "actual.raw_runtime_refusal_source",
        row.raw_runtime_refusal_source,
      ),
    );
    appendAmountLeaves(leaves, row.spend);
  });

  leaves.push(semanticLeaf("scope.scope_id", body.scope_id));
  [
    body.scope_total_risk_spend.allocation,
    body.scope_total_risk_spend.spent,
    body.scope_total_risk_spend.remaining,
    body.scope_total_risk_spend.overspend_amount,
  ].forEach((amount) => appendAmountLeaves(leaves, amount));

  lists.push(
    Object.freeze({
      field: "class-spend",
      itemCount: body.obligation_class_risk_spend.length,
    }),
  );
  body.obligation_class_risk_spend.forEach((row) => {
    leaves.push(semanticLeaf("class.obligation_class", row.obligation_class));
    appendSemanticList(leaves, lists, "class.check_refs", row.check_refs);
    appendSemanticList(
      leaves,
      lists,
      "class.good_event_refs",
      row.good_event_refs,
    );
    appendSemanticList(
      leaves,
      lists,
      "class.instrument_refs",
      row.instrument_refs,
    );
    [row.allocation, row.spent, row.remaining, row.overspend_amount].forEach(
      (amount) => appendAmountLeaves(leaves, amount),
    );
  });

  lists.push(
    Object.freeze({
      field: "instrument-definitions",
      itemCount: body.instrument_definitions.length,
    }),
  );
  body.instrument_definitions.forEach((row) => {
    leaves.push(
      semanticLeaf("definition.instrument_id", row.instrument_id),
      semanticLeaf("definition.instrument_family", row.instrument_family),
      semanticLeaf("definition.proof_profile_id", row.proof_profile_id),
      semanticLeaf("definition.proof_kernel_id", row.proof_kernel_id),
      semanticLeaf("definition.guarantee_kind", row.guarantee_kind),
    );
    appendSemanticList(
      leaves,
      lists,
      "definition.certificate_roles",
      row.certificate_roles,
    );
    leaves.push(
      semanticLeaf("definition.anytime_valid", row.anytime_valid),
      semanticLeaf("definition.deterministic", row.deterministic),
      semanticLeaf(
        "definition.permits_obligation_satisfaction",
        row.permits_obligation_satisfaction,
      ),
      semanticLeaf("definition.blocker", row.blocker),
    );
  });

  lists.push(
    Object.freeze({
      field: "certificate-routes",
      itemCount: body.certificate_routes.length,
    }),
  );
  body.certificate_routes.forEach((row) => {
    Object.entries(row).forEach(([field, value]) => {
      leaves.push(
        semanticLeaf(
          `route.${field}`,
          value as boolean | number | string | null,
        ),
      );
    });
  });

  const positive = body.positive_register;
  leaves.push(
    semanticLeaf("positive.population_state", positive.population_state),
    semanticLeaf("positive.population_count", positive.population_count),
    semanticLeaf("positive.authority_posture", positive.authority_posture),
    semanticLeaf(
      "positive.appointment_denominator_state",
      positive.appointment_denominator_state,
    ),
    semanticLeaf(
      "positive.appointment_sufficiency_state",
      positive.appointment_sufficiency_state,
    ),
  );
  appendSemanticList(
    leaves,
    lists,
    "positive.promotion_blockers",
    confidenceLedgerPromotionBlockers(packet),
  );
  appendSemanticList(
    leaves,
    lists,
    "positive.register_blockers",
    positive.blockers.map((row) => `${row.slot}:${row.value}`),
  );
  appendSemanticList(
    leaves,
    lists,
    "positive.would_populate_when",
    positive.would_populate_when,
  );
  appendSemanticList(
    leaves,
    lists,
    "positive.verified_appointment_refs",
    positive.verified_appointment_refs as string[],
  );

  leaves.push(
    semanticLeaf("posture.coverage_assessment", body.coverage_assessment),
    semanticLeaf("posture.budget_posture", body.budget_posture),
    semanticLeaf("posture.appointment_posture", body.appointment_posture),
  );
  appendSemanticList(
    leaves,
    lists,
    "posture.packet_may_not_use_for",
    packet.may_not_use_for ?? [],
  );
  appendSemanticList(
    leaves,
    lists,
    "posture.envelope_may_not_use_for",
    body.coverage_envelope.may_not_use_for,
  );
  leaves.push(
    semanticLeaf(
      "good_event.clause",
      body.good_event_posture.good_event_clause,
    ),
    semanticLeaf(
      "good_event.composition_rule",
      body.good_event_posture.composition_rule,
    ),
    semanticLeaf(
      "good_event.independence_claim",
      body.good_event_posture.independence_claim,
    ),
  );
  appendSemanticList(
    leaves,
    lists,
    "good_event.executed_refs",
    body.good_event_posture.executed_probabilistic_good_event_refs,
  );
  leaves.push(
    semanticLeaf("source.relative_path", packet.source.relative_path),
    semanticLeaf(
      "source.artifact_content_hash",
      packet.source.artifact_content_hash,
    ),
    semanticLeaf("source.validator_id", packet.source.validation.validator_id),
    semanticLeaf(
      "source.validator_version",
      packet.source.validation.validator_version,
    ),
    semanticLeaf("source.validation_status", packet.source.validation.status),
    semanticLeaf(
      "source.worker_receipt_ref",
      packet.worker_validation_receipt_ref,
    ),
    semanticLeaf(
      "source.worker_receipt_hash",
      packet.worker_validation_receipt_hash,
    ),
    semanticLeaf("replay.address", packet.replay_address),
  );
  Object.entries(packet.replay_pins).forEach(([field, value]) => {
    leaves.push(semanticLeaf(`replay.${field}`, value));
  });
  appendSemanticList(
    leaves,
    lists,
    "source.provenance",
    body.source_provenance.map(
      (source) =>
        `${source.source_role}|${source.source_ref}|${source.content_hash}|${source.admission_state}|${source.availability_state}|${source.verifier_ref}`,
    ),
  );

  return Object.freeze({
    leaves: Object.freeze(leaves),
    lists: Object.freeze(lists),
  });
}

function sameSequence(
  observed: readonly unknown[],
  expected: readonly unknown[],
): boolean {
  return JSON.stringify(observed) === JSON.stringify(expected);
}

function visibleSemanticsMatch(
  observed: VisibleSemanticProjection,
  packet: Extract<
    ConfidenceLedgerRiskSpendPacket,
    { availability: "available" }
  >,
): boolean {
  const body = packet.payload;
  const actualRows = orderedConfidenceLedgerActualRows(packet);
  const replayPinFields = Object.keys(packet.replay_pins);
  const expectedDom = expectedSemanticDom(packet);
  return (
    sameSequence(observed.sections, [
      "actual-rows",
      "risk-accounting",
      "instrument-denominators",
      "positive-register",
      "good-event-source-replay",
      "machine-export",
    ]) &&
    sameSequence(observed.semanticLeaves, expectedDom.leaves) &&
    sameSequence(observed.semanticLists, expectedDom.lists) &&
    sameSequence(
      observed.actualRefs,
      actualRows.map((row) => row.instance_ref),
    ) &&
    sameSequence(
      observed.actualRoles,
      actualRows.map((row) => row.certificate_role),
    ) &&
    sameSequence(
      observed.classes,
      body.obligation_class_risk_spend.map((row) => row.obligation_class),
    ) &&
    sameSequence(
      observed.definitions,
      body.instrument_definitions.map((row) => row.instrument_id),
    ) &&
    sameSequence(
      observed.routes,
      body.certificate_routes.map((row) => row.certificate_class),
    ) &&
    sameSequence(observed.figures, expectedFigures(packet)) &&
    sameSequence(observed.positivePopulationState, [
      body.positive_register.population_state,
    ]) &&
    sameSequence(observed.positivePopulationCount, [
      String(body.positive_register.population_count),
    ]) &&
    sameSequence(observed.positiveAppointmentState, [
      body.positive_register.appointment_sufficiency_state,
    ]) &&
    sameSequence(
      observed.promotionBlockers,
      confidenceLedgerPromotionBlockers(packet),
    ) &&
    sameSequence(observed.packetMayNotUseFor, packet.may_not_use_for ?? []) &&
    sameSequence(
      observed.envelopeMayNotUseFor,
      body.coverage_envelope.may_not_use_for,
    ) &&
    sameSequence(observed.sourcePath, [packet.source.relative_path]) &&
    sameSequence(observed.sourceArtifactHash, [
      packet.source.artifact_content_hash,
    ]) &&
    sameSequence(observed.sourceValidatorId, [
      packet.source.validation.validator_id,
    ]) &&
    sameSequence(observed.sourceValidatorVersion, [
      packet.source.validation.validator_version,
    ]) &&
    sameSequence(observed.sourceValidationStatus, [
      packet.source.validation.status,
    ]) &&
    sameSequence(observed.workerReceiptRef, [
      packet.worker_validation_receipt_ref,
    ]) &&
    sameSequence(observed.workerReceiptHash, [
      packet.worker_validation_receipt_hash,
    ]) &&
    sameSequence(observed.replayAddress, [packet.replay_address]) &&
    replayPinFields.every((field) =>
      sameSequence(observed.replayPins[field] ?? [], [
        String(packet.replay_pins[field as keyof typeof packet.replay_pins]),
      ]),
    ) &&
    sameSequence(
      observed.sourceProvenance,
      body.source_provenance.map(
        (source) =>
          `${source.source_role}|${source.source_ref}|${source.content_hash}|${source.admission_state}|${source.availability_state}|${source.verifier_ref}`,
      ),
    )
  );
}

type GovernedText = Readonly<{ marker: string; text: string }>;
type ProductLocale = "en" | "uk";

const CONFIDENCE_LEDGER_DOM_NODE_CAP = 20 * 1000;
const CONFIDENCE_LEDGER_DOM_TEXT_CODE_UNIT_CAP = 80 * 1000;
const CONFIDENCE_LEDGER_DOM_ATTRIBUTE_COUNT_CAP = 20 * 1000;
const CONFIDENCE_LEDGER_DOM_ATTRIBUTE_CODE_UNIT_CAP = 640 * 1000;
const CONFIDENCE_LEDGER_DOM_SINGLE_ATTRIBUTE_CAP = 4 * 1000;
const CONFIDENCE_LEDGER_DOM_WORK_RESERVE = 140 * 1000;

function normalizedText(value: string): string {
  return value
    .replace(/\s+/gu, " ")
    .replace(/\s+([:;,.!?])/gu, "$1")
    .trim();
}

type DomWork = Readonly<{
  attributeCount: number;
  attributeCodeUnits: number;
  nodeCount: number;
  textCodeUnits: number;
  workUnits: number;
}>;

function documentDomWorkWithinCaps(document: Document): DomWork | null {
  const documentElement = document.documentElement;
  if (documentElement === null) return null;
  const showAll = document.defaultView?.NodeFilter.SHOW_ALL ?? 0xffffffff;
  const walker = document.createTreeWalker(documentElement, showAll);
  let nodeCount = 1;
  let textCodeUnits = 0;
  let attributeCount = 0;
  let attributeCodeUnits = 0;
  const countAttributes = (element: Element): boolean => {
    for (const attribute of element.attributes) {
      const size = attribute.name.length + attribute.value.length;
      attributeCount += 1;
      attributeCodeUnits += size;
      if (
        attributeCount > CONFIDENCE_LEDGER_DOM_ATTRIBUTE_COUNT_CAP ||
        attributeCodeUnits > CONFIDENCE_LEDGER_DOM_ATTRIBUTE_CODE_UNIT_CAP ||
        size > CONFIDENCE_LEDGER_DOM_SINGLE_ATTRIBUTE_CAP
      ) {
        return false;
      }
    }
    return true;
  };
  if (!countAttributes(documentElement)) return null;
  let node = walker.nextNode();
  while (node !== null) {
    nodeCount += 1;
    if (node.nodeType === Node.TEXT_NODE) {
      textCodeUnits += node.nodeValue?.length ?? 0;
    }
    if (node instanceof Element) {
      if (!countAttributes(node)) return null;
    }
    if (
      nodeCount > CONFIDENCE_LEDGER_DOM_NODE_CAP ||
      textCodeUnits > CONFIDENCE_LEDGER_DOM_TEXT_CODE_UNIT_CAP
    ) {
      return null;
    }
    node = walker.nextNode();
  }
  return Object.freeze({
    attributeCount,
    attributeCodeUnits,
    nodeCount,
    textCodeUnits,
    workUnits: attributeCount + nodeCount + textCodeUnits,
  });
}

type ExpectedEnvelopeField = Readonly<{
  field: string;
  label: string;
  values: readonly string[];
}>;

function deriveExpectedEnvelopeFields(
  envelope: unknown,
): readonly ExpectedEnvelopeField[] {
  const fields: ExpectedEnvelopeField[] = [];
  const append = (field: string, value: unknown): void => {
    if (Array.isArray(value)) {
      if (value.every((item) => item === null || typeof item !== "object")) {
        fields.push({
          field,
          label: field,
          values: value.map((item) => (item === null ? "null" : String(item))),
        });
        return;
      }
      value.forEach((item, index) => append(`${field}.${index}`, item));
      return;
    }
    if (typeof value === "object" && value !== null) {
      Object.entries(value).forEach(([nestedField, nestedValue]) =>
        append(field ? `${field}.${nestedField}` : nestedField, nestedValue),
      );
      return;
    }
    fields.push({
      field,
      label: field,
      values: [value === null ? "null" : String(value)],
    });
  };
  append("", envelope);
  return Object.freeze(fields);
}

function catalogText(
  locale: ProductLocale,
  path: string,
  variables: Readonly<Record<string, string | number>> = {},
): string {
  let current: unknown = locale === "uk" ? uk : en;
  for (const segment of path.split(".")) {
    if (
      typeof current !== "object" ||
      current === null ||
      !(segment in current)
    ) {
      throw new SemanticDomError(`locale copy is missing ${path}`);
    }
    current = (current as Record<string, unknown>)[segment];
  }
  if (typeof current !== "string") {
    throw new SemanticDomError(`locale copy is not text ${path}`);
  }
  return normalizedText(
    Object.entries(variables).reduce(
      (message, [name, value]) =>
        message.replaceAll(`{${name}}`, String(value)),
      current,
    ),
  );
}

function collectGovernedText(
  boundary: HTMLElement,
  visibility: RenderedVisibilitySession,
): readonly GovernedText[] {
  const forbiddenPayloadSelector =
    'script[type="application/json"], input[type="hidden"], [data-confidence-payload], [data-testid]';
  if (
    boundary.matches(forbiddenPayloadSelector) ||
    boundary.querySelector(forbiddenPayloadSelector) !== null
  ) {
    throw new SemanticDomError("hidden or test-only payload detected");
  }
  const document = boundary.ownerDocument;
  const showText = document.defaultView?.NodeFilter.SHOW_TEXT ?? 4;
  const walker = document.createTreeWalker(boundary, showText);
  const byElement = new Map<HTMLElement, { marker: string; parts: string[] }>();
  let node = walker.nextNode();
  while (node !== null) {
    const text = normalizedText(node.textContent ?? "");
    if (text.length > 0) {
      const parent = node.parentElement;
      if (parent === null)
        throw new SemanticDomError("visible text has no parent");
      const proof = visibility.prove(parent, boundary);
      if (proof === "unproved") {
        throw new VisibilityUnprovedError("visible text is unproved");
      }
      if (proof === "visible") {
        const classified = parent.closest<HTMLElement>(
          "[data-confidence-text]",
        );
        if (classified === null || !boundary.contains(classified)) {
          throw new SemanticDomError(`unclassified visible text: ${text}`);
        }
        const marker = classified.dataset.confidenceText;
        if (marker === undefined || marker.length === 0) {
          throw new SemanticDomError("empty governed text marker");
        }
        const existing = byElement.get(classified);
        if (existing === undefined) {
          byElement.set(classified, { marker, parts: [text] });
        } else {
          existing.parts.push(text);
        }
      }
    }
    node = walker.nextNode();
  }
  const classifiedElements = [
    ...boundary.querySelectorAll<HTMLElement>("[data-confidence-text]"),
  ];
  if (boundary.dataset.confidenceText !== undefined) {
    classifiedElements.unshift(boundary);
  }
  for (const element of classifiedElements) {
    assertVisible(element, boundary, visibility);
    if (!byElement.has(element)) {
      throw new SemanticDomError("governed text marker has no visible text");
    }
  }
  return Object.freeze(
    [...byElement.values()].map(({ marker, parts }) =>
      Object.freeze({ marker, text: normalizedText(parts.join(" ")) }),
    ),
  );
}

function expectedRootText(
  packet: Extract<
    ConfidenceLedgerRiskSpendPacket,
    { availability: "available" }
  >,
  locale: ProductLocale,
): readonly GovernedText[] {
  const result: GovernedText[] = [];
  const body = packet.payload;
  const push = (marker: string, value: boolean | number | string | null) =>
    result.push(
      Object.freeze({
        marker,
        text: normalizedText(value === null ? "null" : String(value)),
      }),
    );
  const semantic = (field: string, value: boolean | number | string | null) =>
    push(`leaf.${field}`, value);
  const detail = (
    label: string,
    field: string,
    value: boolean | number | string | null,
  ) => {
    push(`detail.label.${label}`, label);
    semantic(field, value);
  };
  const list = (label: string, field: string, values: readonly string[]) => {
    push(`detail.label.${label}`, label);
    if (values.length === 0) {
      semantic(`${field}.count`, 0);
    } else {
      values.forEach((value, index) => semantic(`${field}.${index}`, value));
    }
  };
  const figure = (label: string, amount: ConditionalDeltaAmount) => {
    push("figure.caption", label);
    push("figure.rational_display", amount.rational_display);
    push(
      "figure.canonical_decimal_label",
      `${catalogText(locale, "pages.cycleBoard.confidenceLedger.figure.canonicalDecimal")}:`,
    );
    push("figure.canonical_decimal", amount.canonical_decimal);
    push(
      "figure.conditionality_riders",
      `${amount.declared_set_rider} — ${amount.locality_rider}`,
    );
  };
  const section = (name: string, copyPath: string) =>
    push(`section.${name}.title`, catalogText(locale, copyPath));
  const accountingCopy = (name: string) =>
    catalogText(locale, `pages.cycleBoard.confidenceLedger.accounting.${name}`);

  section(
    "actual-rows",
    "pages.cycleBoard.confidenceLedger.sections.actualRows",
  );
  const actualFields = [
    "instance_ref",
    "certificate_role",
    "instrument_id",
    "instrument_family",
    "obligation_class",
    "execution_status",
    "outcome",
    "certificate_ref",
    "certificate_class",
    "certificate_route_ref",
    "anytime_valid",
    "eligible_for_promotion",
    "supports_obligation",
    "blocker",
    "proof_profile_id",
    "raw_runtime_refusal_source",
  ] as const;
  orderedConfidenceLedgerActualRows(packet).forEach((row) => {
    actualFields.forEach((field) =>
      detail(field, `actual.${field}`, row[field] as boolean | string | null),
    );
    figure(`${row.instance_ref} · ${accountingCopy("spent")}`, row.spend);
  });

  section(
    "risk-accounting",
    "pages.cycleBoard.confidenceLedger.sections.riskAccounting",
  );
  semantic("scope.scope_id", body.scope_id);
  const scopePrefix = accountingCopy("scopeTotal");
  (
    [
      ["allocation", body.scope_total_risk_spend.allocation],
      ["spent", body.scope_total_risk_spend.spent],
      ["remaining", body.scope_total_risk_spend.remaining],
      ["overspend", body.scope_total_risk_spend.overspend_amount],
    ] as const
  ).forEach(([name, amount]) =>
    figure(`${scopePrefix} · ${accountingCopy(name)}`, amount),
  );
  body.obligation_class_risk_spend.forEach((row) => {
    semantic("class.obligation_class", row.obligation_class);
    list("check_refs", "class.check_refs", row.check_refs);
    list("good_event_refs", "class.good_event_refs", row.good_event_refs);
    list("instrument_refs", "class.instrument_refs", row.instrument_refs);
    (
      [
        ["allocation", row.allocation],
        ["spent", row.spent],
        ["remaining", row.remaining],
        ["overspend", row.overspend_amount],
      ] as const
    ).forEach(([name, amount]) =>
      figure(`${row.obligation_class} · ${accountingCopy(name)}`, amount),
    );
  });

  section(
    "instrument-denominators",
    "pages.cycleBoard.confidenceLedger.sections.denominators",
  );
  push(
    "denominators.instrument_definitions.title",
    catalogText(
      locale,
      "pages.cycleBoard.confidenceLedger.instrumentDefinitions",
    ),
  );
  body.instrument_definitions.forEach((row) => {
    detail("instrument_id", "definition.instrument_id", row.instrument_id);
    detail(
      "instrument_family",
      "definition.instrument_family",
      row.instrument_family,
    );
    detail(
      "proof_profile_id",
      "definition.proof_profile_id",
      row.proof_profile_id,
    );
    detail(
      "proof_kernel_id",
      "definition.proof_kernel_id",
      row.proof_kernel_id,
    );
    detail("guarantee_kind", "definition.guarantee_kind", row.guarantee_kind);
    list(
      "certificate_roles",
      "definition.certificate_roles",
      row.certificate_roles,
    );
    detail("anytime_valid", "definition.anytime_valid", row.anytime_valid);
    detail("deterministic", "definition.deterministic", row.deterministic);
    detail(
      "permits_obligation_satisfaction",
      "definition.permits_obligation_satisfaction",
      row.permits_obligation_satisfaction,
    );
    detail("blocker", "definition.blocker", row.blocker);
  });
  push(
    "denominators.certificate_routes.title",
    catalogText(locale, "pages.cycleBoard.confidenceLedger.certificateRoutes"),
  );
  body.certificate_routes.forEach((row) => {
    Object.entries(row).forEach(([field, value]) =>
      detail(
        field,
        `route.${field}`,
        value as boolean | number | string | null,
      ),
    );
  });

  section(
    "positive-register",
    "pages.cycleBoard.confidenceLedger.sections.positiveRegister",
  );
  push(
    "positive.empty.title",
    catalogText(
      locale,
      "pages.cycleBoard.confidenceLedger.positiveEmpty.title",
    ),
  );
  push(
    "positive.empty.status",
    catalogText(
      locale,
      "pages.cycleBoard.confidenceLedger.positiveEmpty.status",
      {
        count: body.positive_register.population_count,
      },
    ),
  );
  push(
    "positive.empty.body",
    catalogText(locale, "pages.cycleBoard.confidenceLedger.positiveEmpty.body"),
  );
  detail(
    "population_state",
    "positive.population_state",
    body.positive_register.population_state,
  );
  detail(
    "population_count",
    "positive.population_count",
    body.positive_register.population_count,
  );
  detail(
    "authority_posture",
    "positive.authority_posture",
    body.positive_register.authority_posture,
  );
  detail(
    "appointment_denominator_state",
    "positive.appointment_denominator_state",
    body.positive_register.appointment_denominator_state,
  );
  detail(
    "appointment_sufficiency_state",
    "positive.appointment_sufficiency_state",
    body.positive_register.appointment_sufficiency_state,
  );
  list(
    "promotion_blockers",
    "positive.promotion_blockers",
    confidenceLedgerPromotionBlockers(packet),
  );
  list(
    "register_blockers",
    "positive.register_blockers",
    body.positive_register.blockers.map((row) => `${row.slot}:${row.value}`),
  );
  list(
    "would_populate_when",
    "positive.would_populate_when",
    body.positive_register.would_populate_when,
  );
  list(
    "verified_appointment_refs",
    "positive.verified_appointment_refs",
    body.positive_register.verified_appointment_refs as string[],
  );

  section(
    "good-event-source-replay",
    "pages.cycleBoard.confidenceLedger.sections.goodEventSourceReplay",
  );
  detail(
    "coverage_assessment",
    "posture.coverage_assessment",
    body.coverage_assessment,
  );
  detail("budget_posture", "posture.budget_posture", body.budget_posture);
  detail(
    "appointment_posture",
    "posture.appointment_posture",
    body.appointment_posture,
  );
  list(
    "packet_may_not_use_for",
    "posture.packet_may_not_use_for",
    packet.may_not_use_for,
  );
  list(
    "envelope_may_not_use_for",
    "posture.envelope_may_not_use_for",
    body.coverage_envelope.may_not_use_for,
  );
  detail(
    "good_event_clause",
    "good_event.clause",
    body.good_event_posture.good_event_clause,
  );
  detail(
    "composition_rule",
    "good_event.composition_rule",
    body.good_event_posture.composition_rule,
  );
  detail(
    "independence_claim",
    "good_event.independence_claim",
    body.good_event_posture.independence_claim,
  );
  list(
    "executed_probabilistic_good_event_refs",
    "good_event.executed_refs",
    body.good_event_posture.executed_probabilistic_good_event_refs,
  );
  detail(
    "source.relative_path",
    "source.relative_path",
    packet.source.relative_path,
  );
  detail(
    "source.artifact_content_hash",
    "source.artifact_content_hash",
    packet.source.artifact_content_hash,
  );
  detail(
    "source.validator_id",
    "source.validator_id",
    packet.source.validation.validator_id,
  );
  detail(
    "source.validator_version",
    "source.validator_version",
    packet.source.validation.validator_version,
  );
  detail(
    "source.validation.status",
    "source.validation_status",
    packet.source.validation.status,
  );
  detail(
    "worker_validation_receipt_ref",
    "source.worker_receipt_ref",
    packet.worker_validation_receipt_ref,
  );
  detail(
    "worker_validation_receipt_hash",
    "source.worker_receipt_hash",
    packet.worker_validation_receipt_hash,
  );
  detail("replay_address", "replay.address", packet.replay_address);
  Object.entries(packet.replay_pins).forEach(([field, value]) =>
    detail(`replay_pins.${field}`, `replay.${field}`, value),
  );
  list(
    "source_provenance",
    "source.provenance",
    body.source_provenance.map(
      (source) =>
        `${source.source_role}|${source.source_ref}|${source.content_hash}|${source.admission_state}|${source.availability_state}|${source.verifier_ref}`,
    ),
  );

  section(
    "machine-export",
    "pages.cycleBoard.confidenceLedger.sections.machineExport",
  );
  push(
    "machine.download",
    catalogText(locale, "pages.cycleBoard.confidenceLedger.downloadMachine"),
  );
  return Object.freeze(result);
}

function expectedDialogText(
  packet: Extract<
    ConfidenceLedgerRiskSpendPacket,
    { availability: "available" }
  >,
  locale: ProductLocale,
  figureLabel: string,
): readonly GovernedText[] {
  const result: GovernedText[] = [
    Object.freeze({
      marker: "dialog.title",
      text: `${figureLabel}: ${catalogText(
        locale,
        "pages.cycleBoard.confidenceLedger.figure.dialogTitle",
      )}`,
    }),
    Object.freeze({
      marker: "dialog.description",
      text: catalogText(
        locale,
        "pages.cycleBoard.confidenceLedger.figure.dialogDescription",
      ),
    }),
  ];
  deriveExpectedEnvelopeFields(packet.payload.coverage_envelope).forEach(
    ({ field, label, values }) => {
      result.push(
        Object.freeze({ marker: `dialog.field.${field}.label`, text: label }),
      );
      if (values.length === 0) {
        result.push(
          Object.freeze({ marker: `dialog.field.${field}.empty`, text: "[]" }),
        );
      } else {
        values.forEach((value, index) =>
          result.push(
            Object.freeze({
              marker: `dialog.field.${field}.value.${index}`,
              text: normalizedText(value),
            }),
          ),
        );
      }
    },
  );
  return Object.freeze(result);
}

function uniqueElementById(document: Document, id: string): HTMLElement | null {
  if (id.length === 0) return null;
  const matches = [...document.querySelectorAll<HTMLElement>("[id]")].filter(
    (element) => element.id === id,
  );
  return matches.length === 1 ? matches[0] : null;
}

function singleRelationTarget(
  owner: HTMLElement,
  relation: "aria-describedby" | "aria-labelledby",
): HTMLElement | null {
  const raw = owner.getAttribute(relation)?.trim() ?? "";
  const ids = raw.split(" ").filter((id) => id.length > 0);
  if (ids.length !== 1) return null;
  return uniqueElementById(owner.ownerDocument, ids[0]);
}

function hasExactAriaGrammar(
  element: HTMLElement,
  expectedNames: readonly string[],
): boolean {
  const observedNames = [...element.attributes]
    .map((attribute) => attribute.name)
    .filter((name) => name.startsWith("aria-"))
    .sort();
  return sameSequence(observedNames, [...expectedNames].sort());
}

function amountBindingMatches(
  element: HTMLElement,
  amount: ConditionalDeltaAmount,
): boolean {
  return (
    element.dataset.confidenceAmountHash === amount.amount_hash &&
    element.dataset.confidenceScopeId === amount.scope_id &&
    element.dataset.confidenceEnvelopeRef === amount.coverage_envelope_ref &&
    element.dataset.confidenceDeclaredClassesHash ===
      amount.declared_obligation_classes_hash &&
    element.dataset.confidenceSemanticRole === amount.semantic_role
  );
}

function dialogAmountBindingMatches(
  dialog: HTMLElement,
  amount: ConditionalDeltaAmount,
): boolean {
  return (
    dialog.dataset.confidenceAmountHash === amount.amount_hash &&
    dialog.dataset.confidenceScopeId === amount.scope_id &&
    dialog.dataset.confidenceDialogEnvelopeRef ===
      amount.coverage_envelope_ref &&
    dialog.dataset.confidenceDeclaredClassesHash ===
      amount.declared_obligation_classes_hash &&
    dialog.dataset.confidenceSemanticRole === amount.semantic_role
  );
}

function accessibilityAndPortalBindingMatches(
  root: HTMLElement,
  dialog: HTMLElement,
  packet: Extract<
    ConfidenceLedgerRiskSpendPacket,
    { availability: "available" }
  >,
  locale: ProductLocale,
  visibility: RenderedVisibilitySession,
): Readonly<{ figureLabel: string }> | null {
  const figures = [...root.querySelectorAll<HTMLElement>("figure")];
  const amounts = expectedFigureAmounts(packet);
  const expectedCaptions = expectedRootText(packet, locale)
    .filter((entry) => entry.marker === "figure.caption")
    .map((entry) => entry.text);
  if (
    figures.length !== amounts.length ||
    figures.length !== expectedCaptions.length
  ) {
    return null;
  }
  const triggers: HTMLButtonElement[] = [];
  for (const [index, figure] of figures.entries()) {
    const figureTriggers = [
      ...figure.querySelectorAll<HTMLButtonElement>(
        'button[data-confidence-trigger="conditional-delta"]',
      ),
    ];
    const captions = [...figure.querySelectorAll<HTMLElement>("figcaption")];
    if (figureTriggers.length !== 1 || captions.length !== 1) return null;
    const trigger = figureTriggers[0];
    const amount = amounts[index];
    const caption = expectedCaptions[index];
    const riders = `${amount.declared_set_rider} — ${amount.locality_rider}`;
    if (
      visibleText(captions[0], root, visibility) !== caption ||
      visibleText(trigger, root, visibility) !== riders ||
      !hasExactAriaGrammar(trigger, [
        "aria-controls",
        "aria-expanded",
        "aria-haspopup",
        "aria-label",
      ]) ||
      trigger.getAttribute("aria-label") !== `${caption}: ${riders}` ||
      trigger.getAttribute("aria-haspopup") !== "dialog" ||
      trigger.id.length === 0 ||
      (trigger.getAttribute("aria-expanded") !== "true" &&
        trigger.getAttribute("aria-expanded") !== "false") ||
      (trigger.getAttribute("aria-controls")?.length ?? 0) === 0 ||
      !amountBindingMatches(trigger, amount)
    ) {
      return null;
    }
    triggers.push(trigger);
  }
  const triggerIds = triggers.map((trigger) => trigger.id);
  const controlledIds = triggers.map(
    (trigger) => trigger.getAttribute("aria-controls") ?? "",
  );
  if (
    new Set(triggerIds).size !== triggers.length ||
    new Set(controlledIds).size !== triggers.length
  ) {
    return null;
  }
  const expanded = triggers.filter(
    (trigger) => trigger.getAttribute("aria-expanded") === "true",
  );
  if (expanded.length !== 1) return null;
  const trigger = expanded[0];
  const index = triggers.indexOf(trigger);
  const amount = amounts[index];
  const figureLabel = expectedCaptions[index];
  if (
    trigger.getAttribute("aria-controls") !== dialog.id ||
    uniqueElementById(dialog.ownerDocument, dialog.id) !== dialog ||
    dialog.getAttribute("role") !== "dialog" ||
    !hasExactAriaGrammar(dialog, ["aria-describedby", "aria-labelledby"]) ||
    dialog.dataset.confidenceDialogTriggerId !== trigger.id ||
    !dialogAmountBindingMatches(dialog, amount)
  ) {
    return null;
  }
  const title = singleRelationTarget(dialog, "aria-labelledby");
  const description = singleRelationTarget(dialog, "aria-describedby");
  if (
    title === null ||
    description === null ||
    !dialog.contains(title) ||
    !dialog.contains(description) ||
    !hasExactAriaGrammar(title, []) ||
    !hasExactAriaGrammar(description, []) ||
    visibleText(title, dialog, visibility) !==
      `${figureLabel}: ${catalogText(
        locale,
        "pages.cycleBoard.confidenceLedger.figure.dialogTitle",
      )}` ||
    visibleText(description, dialog, visibility) !==
      catalogText(
        locale,
        "pages.cycleBoard.confidenceLedger.figure.dialogDescription",
      )
  ) {
    return null;
  }
  return Object.freeze({ figureLabel });
}

function answersFromVisibleDom(
  projection: VisibleSemanticProjection,
): Readonly<
  Record<ConfidenceLedgerProtectedQuery, ConfidenceLedgerProtectedAnswer>
> {
  const packetDenials = new Set(projection.packetMayNotUseFor);
  const envelopeDenials = new Set(projection.envelopeMayNotUseFor);
  const allFiguresCarryLocality =
    projection.figures.length > 0 &&
    projection.figures.every(
      (figure) =>
        figure.riders.includes("≤ δ relative to the declared obligation set") &&
        figure.riders.includes(
          "Local accounting for this exact confidence scope; no family or sequence-level claim is asserted.",
        ),
    );
  return Object.freeze({
    promotion_authority:
      packetDenials.has("promotion_authority") &&
      projection.promotionBlockers.length > 0
        ? "denied"
        : "not_established",
    publication_authority: packetDenials.has("publication_authority")
      ? "denied"
      : "not_established",
    public_audience: packetDenials.has("public_audience")
      ? "denied"
      : "not_established",
    bounded_completeness:
      packetDenials.has("bounded_completeness") ||
      envelopeDenials.has("bounded_completeness")
        ? "denied"
        : "not_established",
    world_completeness: envelopeDenials.has("world_completeness")
      ? "denied"
      : "not_established",
    family_level_total: allFiguresCarryLocality ? "denied" : "not_established",
    sequence_level_total: allFiguresCarryLocality
      ? "denied"
      : "not_established",
    cross_scope_total: allFiguresCarryLocality ? "denied" : "not_established",
    narrowed_claim_satisfaction: allFiguresCarryLocality
      ? "denied"
      : "not_established",
  });
}

function isEqualOrMoreConservative(
  observed: Readonly<
    Record<ConfidenceLedgerProtectedQuery, ConfidenceLedgerProtectedAnswer>
  >,
  expected: Readonly<
    Record<ConfidenceLedgerProtectedQuery, ConfidenceLedgerProtectedAnswer>
  >,
): boolean {
  const rank: Record<ConfidenceLedgerProtectedAnswer, number> = {
    denied: 2,
    not_established: 1,
  };
  return CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA.every(
    (query) => rank[observed[query]] >= rank[expected[query]],
  );
}

/** Evaluate the byte/semantic twins with exact PV-K04 and finite-schema PV-K06. */
export async function evaluateConfidenceLedgerRiskSpendTwin({
  evaluationMode,
  packetCandidate,
  rawPacketBytes,
  root,
  stepBudget,
}: EvaluateConfidenceLedgerRiskSpendTwinInput): Promise<ConfidenceLedgerRiskSpendTwinResult> {
  if (
    !Number.isFinite(stepBudget) ||
    !Number.isSafeInteger(stepBudget) ||
    stepBudget <= 0 ||
    stepBudget > CONFIDENCE_LEDGER_LIVE_EVALUATION_BUDGET ||
    stepBudget <= CONFIDENCE_LEDGER_DOM_WORK_RESERVE
  ) {
    return blocked("timeout");
  }
  if (root === null) return blocked("missing_input_or_incomplete_history");

  const preflight = await evaluateConfidenceLedgerProtectedQuery({
    evaluationMode,
    packetCandidate,
    rawPacketBytes,
    stepBudget: stepBudget - CONFIDENCE_LEDGER_DOM_WORK_RESERVE,
  });
  if (preflight.status === "blocked") return blocked(preflight.reason);
  const packet = preflight.packet;
  if (packet.availability !== "available") {
    return blocked("unsupported_or_out_of_model");
  }

  const envelopeRef = packet.payload.coverage_envelope_ref;
  const domWork = documentDomWorkWithinCaps(root.ownerDocument);
  if (!root.ownerDocument.documentElement.contains(root) || domWork === null) {
    return blocked("unsupported_or_out_of_model");
  }
  if (
    root.dataset.confidenceEnvelopeRef !== envelopeRef ||
    (root.dataset.confidenceLocale !== "en" &&
      root.dataset.confidenceLocale !== "uk")
  ) {
    return blocked("model_observation_inconsistent");
  }
  const locale = root.dataset.confidenceLocale;
  const dialogs = [
    ...root.ownerDocument.querySelectorAll<HTMLElement>(
      "[data-confidence-dialog-envelope-ref]",
    ),
  ].filter(
    (dialog) => dialog.dataset.confidenceDialogEnvelopeRef === envelopeRef,
  );
  if (dialogs.length === 0) {
    return blocked("missing_input_or_incomplete_history");
  }
  if (dialogs.length !== 1) return blocked("model_observation_inconsistent");
  const dialog = dialogs[0];

  let visibility: RenderedVisibilitySession;
  try {
    visibility = new RenderedVisibilitySession(
      root.ownerDocument,
      CONFIDENCE_LEDGER_DOM_WORK_RESERVE - domWork.workUnits,
    );
  } catch (error) {
    return blocked(
      error instanceof VisibilityUnprovedError
        ? "unproved_approximation"
        : "parser_or_schema_failure",
    );
  }
  let restored = false;
  let result: ConfidenceLedgerRiskSpendTwinResult;
  try {
    try {
      const binding = accessibilityAndPortalBindingMatches(
        root,
        dialog,
        packet,
        locale,
        visibility,
      );
      if (binding === null) {
        result = blocked("model_observation_inconsistent");
      } else {
        const visible = decodeVisibleProjection(root, visibility);
        const rootText = collectGovernedText(root, visibility);
        const dialogText = collectGovernedText(dialog, visibility);
        const expectedRoot = expectedRootText(packet, locale);
        if (!visibleSemanticsMatch(visible, packet)) {
          result = blocked("model_observation_inconsistent");
        } else if (
          !sameSequence(rootText, expectedRoot) ||
          !sameSequence(
            dialogText,
            expectedDialogText(packet, locale, binding.figureLabel),
          )
        ) {
          result = blocked("model_observation_inconsistent");
        } else {
          const domAnswers = answersFromVisibleDom(visible);
          if (
            !isEqualOrMoreConservative(domAnswers, preflight.protectedQueries)
          ) {
            result = blocked("model_observation_inconsistent");
          } else if (
            !sameSequence(
              Object.keys(preflight.protectedQueries),
              CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA,
            )
          ) {
            result = blocked("unsupported_or_out_of_model");
          } else {
            result = Object.freeze({
              byteTwin: preflight.capturedResponseBytes,
              protectedQueries: preflight.protectedQueries,
              status: "exact" as const,
            });
          }
        }
      }
    } catch (error) {
      result = blocked(
        error instanceof VisibilityUnprovedError
          ? "unproved_approximation"
          : "parser_or_schema_failure",
      );
    }
  } finally {
    restored = visibility.restore();
  }
  return restored ? result : blocked("unproved_approximation");
}
