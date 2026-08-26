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

function visibleText(element: HTMLElement): string {
  if (
    element.hidden ||
    element.getAttribute("aria-hidden") === "true" ||
    element.closest('[aria-hidden="true"], [hidden]')
  ) {
    throw new TypeError("DS11-DOM-PARITY-DRIFT: claim value is hidden");
  }
  return element.textContent ?? "";
}

function nullableValue(element: HTMLElement): NullableText {
  const isNull = element.dataset.null;
  const value = element.dataset.value;
  if ((isNull !== "true" && isNull !== "false") || value === undefined) {
    throw new TypeError(
      "DS11-DOM-PARITY-DRIFT: nullable field encoding is invalid",
    );
  }
  visibleText(element);
  return isNull === "true" ? null : value;
}

function requiredInteger(root: ParentNode, selector: string): number {
  const value = Number(visibleText(requiredElement(root, selector)));
  if (!Number.isInteger(value) || value < 0) {
    throw new TypeError("DS11-DOM-PARITY-DRIFT: coordinate is invalid");
  }
  return value;
}

/** Independently decode the ordered PUBLIC claim projection from visible DOM. */
export function decodeTrustPostureDom(root: ParentNode): TrustPostureTwin {
  const rows = [
    ...root.querySelectorAll<HTMLElement>("[data-trust-claim-row]"),
  ];
  return rows.map((row) => ({
    claimId: row.dataset.claimId ?? "",
    subject: nullableValue(requiredElement(row, "[data-trust-subject]")),
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
    ),
    reviewDue: nullableValue(
      requiredElement(row, "[data-trust-review-due]"),
    ),
    sourceAsOf: nullableValue(
      requiredElement(row, "[data-trust-source-as-of]"),
    ),
    sources: [...row.querySelectorAll<HTMLElement>("[data-trust-source]")].map(
      (source) => ({
        path: visibleText(requiredElement(source, "[data-trust-source-path]")),
        symbol: nullableValue(
          requiredElement(source, "[data-trust-source-symbol]"),
        ),
        line: requiredInteger(source, "[data-trust-source-line]"),
        column: requiredInteger(source, "[data-trust-source-column]"),
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
        ),
        reviewOn: nullableValue(
          requiredElement(source, "[data-trust-source-review-on]"),
        ),
        reviewDue: nullableValue(
          requiredElement(source, "[data-trust-source-review-due]"),
        ),
      }),
    ),
  }));
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
  let actual: TrustPostureTwin;
  try {
    actual = decodeTrustPostureDom(root);
  } catch (error) {
    if (error instanceof Error && error.message.includes("DS11-DOM-PARITY-DRIFT")) {
      throw error;
    }
    throw new TypeError("DS11-DOM-PARITY-DRIFT: DOM decoding failed");
  }
  const expected = expectedTrustPostureTwin(register);
  if (
    actual.length !== expected.length ||
    actual.some((row, index) => !rowTwinsEqual(row, expected[index]!))
  ) {
    throw new TypeError(
      "DS11-DOM-PARITY-DRIFT: DOM differs from the artifact projection",
    );
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
