import type { ClaimPostureRegister } from "../domain/posture";

type NullableText = string | null;

type TrustPostureTwinSource = Readonly<{
  path: string;
  symbol: NullableText;
  line: number;
  column: number;
  fieldName: string;
  useKind: string;
  resolution: string;
  sourceState: string;
  subject: NullableText;
  reviewOn: NullableText;
  reviewDue: NullableText;
}>;

type TrustPostureTwinRow = Readonly<{
  claimId: string;
  subject: NullableText;
  effectiveState: string;
  limitations: readonly string[];
  blockerCodes: readonly string[];
  reviewOn: NullableText;
  reviewDue: NullableText;
  sourceAsOf: NullableText;
  sources: readonly TrustPostureTwinSource[];
}>;

export type TrustPostureTwin = readonly TrustPostureTwinRow[];

/** Derive the expected ordered PUBLIC projection directly from the artifact. */
export function expectedTrustPostureTwin(
  register: ClaimPostureRegister,
): TrustPostureTwin {
  return register.claims
    .filter((claim) => claim.audiences.includes("PUBLIC"))
    .map((claim) => ({
      claimId: claim.claim_id,
      subject: claim.subject,
      effectiveState: claim.effective_state,
      limitations: [...claim.limitations],
      blockerCodes: [...claim.blocker_codes],
      reviewOn: claim.review_on,
      reviewDue: claim.review_due,
      sourceAsOf: claim.source_as_of,
      sources: claim.source_bindings.map((binding) => ({
        path: binding.coordinate.path,
        symbol: binding.coordinate.symbol,
        line: binding.coordinate.line,
        column: binding.coordinate.column,
        fieldName: binding.coordinate.field_name,
        useKind: binding.coordinate.use_kind,
        resolution: binding.resolution,
        sourceState: binding.source_state,
        subject: binding.subject,
        reviewOn: binding.review_on,
        reviewDue: binding.review_due,
      })),
    }));
}

function requiredElement<T extends HTMLElement>(
  root: ParentNode,
  selector: string,
): T {
  const element = root.querySelector<T>(selector);
  if (!element) {
    throw new TypeError(`DS11-DOM-PARITY-DRIFT: missing ${selector}`);
  }
  return element;
}

type VisibleText = (element: HTMLElement) => string;

function createVisibleText(): VisibleText {
  const displayed = new WeakMap<HTMLElement, boolean>();
  const isDisplayed = (element: HTMLElement): boolean => {
    const cached = displayed.get(element);
    if (cached !== undefined) return cached;
    const parentDisplayed =
      element.parentElement === null || isDisplayed(element.parentElement);
    const style = element.ownerDocument.defaultView?.getComputedStyle(element);
    const value =
      parentDisplayed &&
      !element.hidden &&
      element.getAttribute("aria-hidden") !== "true" &&
      style?.display !== "none" &&
      style?.visibility !== "hidden" &&
      style?.visibility !== "collapse";
    displayed.set(element, value);
    return value;
  };
  return (element) => {
    if (!isDisplayed(element)) {
      throw new TypeError("DS11-DOM-PARITY-DRIFT: claim value is hidden");
    }
    return (element.textContent ?? "").trim();
  };
}

function nullableValue(
  element: HTMLElement,
  visibleText: VisibleText,
): NullableText {
  const isNull = element.dataset.null;
  if (isNull !== "true" && isNull !== "false") {
    throw new TypeError(
      "DS11-DOM-PARITY-DRIFT: nullable field encoding is invalid",
    );
  }
  const value = visibleText(element);
  return isNull === "true" ? null : value;
}

function requiredInteger(
  root: ParentNode,
  selector: string,
  visibleText: VisibleText,
): number {
  const value = Number(visibleText(requiredElement(root, selector)));
  if (!Number.isInteger(value) || value < 0) {
    throw new TypeError("DS11-DOM-PARITY-DRIFT: coordinate is invalid");
  }
  return value;
}

function decodeTrustPostureRow(
  row: HTMLElement,
  visibleText: VisibleText,
): TrustPostureTwinRow {
  return {
    claimId: visibleText(requiredElement(row, "[data-trust-claim-id]")),
    subject: nullableValue(
      requiredElement(row, "[data-trust-subject]"),
      visibleText,
    ),
    effectiveState: visibleText(
      requiredElement(row, "[data-trust-effective-state]"),
    ),
    limitations: [
      ...row.querySelectorAll<HTMLElement>("[data-trust-limitation]"),
    ].map(visibleText),
    blockerCodes: [
      ...row.querySelectorAll<HTMLElement>("[data-trust-blocker]"),
    ].map(visibleText),
    reviewOn: nullableValue(
      requiredElement(row, "[data-trust-review-on]"),
      visibleText,
    ),
    reviewDue: nullableValue(
      requiredElement(row, "[data-trust-review-due]"),
      visibleText,
    ),
    sourceAsOf: nullableValue(
      requiredElement(row, "[data-trust-source-as-of]"),
      visibleText,
    ),
    sources: [...row.querySelectorAll<HTMLElement>("[data-trust-source]")].map(
      (source) => ({
        path: visibleText(requiredElement(source, "[data-trust-source-path]")),
        symbol: nullableValue(
          requiredElement(source, "[data-trust-source-symbol]"),
          visibleText,
        ),
        line: requiredInteger(source, "[data-trust-source-line]", visibleText),
        column: requiredInteger(
          source,
          "[data-trust-source-column]",
          visibleText,
        ),
        fieldName: visibleText(
          requiredElement(source, "[data-trust-source-field]"),
        ),
        useKind: visibleText(
          requiredElement(source, "[data-trust-source-use]"),
        ),
        resolution: visibleText(
          requiredElement(source, "[data-trust-source-resolution]"),
        ),
        sourceState: visibleText(
          requiredElement(source, "[data-trust-source-state]"),
        ),
        subject: nullableValue(
          requiredElement(source, "[data-trust-source-subject]"),
          visibleText,
        ),
        reviewOn: nullableValue(
          requiredElement(source, "[data-trust-source-review-on]"),
          visibleText,
        ),
        reviewDue: nullableValue(
          requiredElement(source, "[data-trust-source-review-due]"),
          visibleText,
        ),
      }),
    ),
  };
}

/** Independently decode the ordered PUBLIC claim projection from visible DOM. */
export function decodeTrustPostureDom(root: ParentNode): TrustPostureTwin {
  const visibleText = createVisibleText();
  return [...root.querySelectorAll<HTMLElement>("[data-trust-claim-row]")].map(
    (row) => decodeTrustPostureRow(row, visibleText),
  );
}

function stringsEqual(
  left: readonly string[],
  right: readonly string[],
): boolean {
  return (
    left.length === right.length &&
    left.every((value, index) => value === right[index])
  );
}

function sourceTwinsEqual(
  left: TrustPostureTwinSource,
  right: TrustPostureTwinSource,
): boolean {
  return (
    left.path === right.path &&
    left.symbol === right.symbol &&
    left.line === right.line &&
    left.column === right.column &&
    left.fieldName === right.fieldName &&
    left.useKind === right.useKind &&
    left.resolution === right.resolution &&
    left.sourceState === right.sourceState &&
    left.subject === right.subject &&
    left.reviewOn === right.reviewOn &&
    left.reviewDue === right.reviewDue
  );
}

function rowTwinsEqual(
  left: TrustPostureTwinRow,
  right: TrustPostureTwinRow,
): boolean {
  return (
    left.claimId === right.claimId &&
    left.subject === right.subject &&
    left.effectiveState === right.effectiveState &&
    stringsEqual(left.limitations, right.limitations) &&
    stringsEqual(left.blockerCodes, right.blockerCodes) &&
    left.reviewOn === right.reviewOn &&
    left.reviewDue === right.reviewDue &&
    left.sourceAsOf === right.sourceAsOf &&
    left.sources.length === right.sources.length &&
    left.sources.every((source, index) =>
      sourceTwinsEqual(source, right.sources[index]!),
    )
  );
}

/** Fail when the DOM projection differs from its independent artifact twin. */
export function assertTrustPostureDomParity(
  root: ParentNode,
  register: ClaimPostureRegister,
): void {
  try {
    const rows = [
      ...root.querySelectorAll<HTMLElement>("[data-trust-claim-row]"),
    ];
    const expected = expectedTrustPostureTwin(register);
    if (rows.length !== expected.length) {
      throw new TypeError(
        "DS11-DOM-PARITY-DRIFT: DOM differs from the artifact projection",
      );
    }
    const visibleText = createVisibleText();
    for (const [index, row] of rows.entries()) {
      if (
        !rowTwinsEqual(
          decodeTrustPostureRow(row, visibleText),
          expected[index]!,
        )
      ) {
        throw new TypeError(
          "DS11-DOM-PARITY-DRIFT: DOM differs from the artifact projection",
        );
      }
    }
  } catch (error) {
    if (
      error instanceof Error &&
      error.message.includes("DS11-DOM-PARITY-DRIFT")
    ) {
      throw error;
    }
    throw new TypeError("DS11-DOM-PARITY-DRIFT: DOM decoding failed");
  }
}

/** Download a defensive copy of the captured response bytes. */
export function downloadTrustPostureMachine(rawBytes: Uint8Array): void {
  const exactBytes = rawBytes.slice();
  const blob = new Blob([exactBytes], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "trust-claim-posture.v1.json";
  anchor.click();
  URL.revokeObjectURL(url);
}
