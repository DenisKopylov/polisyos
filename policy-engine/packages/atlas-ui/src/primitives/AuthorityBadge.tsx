import type {
  OperatorDiagnostic,
  OperatorProjectionStateLabel,
  RunOperatorDiagnostic,
  RunOperatorProjectionStateLabel,
} from "@polisyos/runtime-api-client";

import { Badge, type BadgeTone } from "./Badge";
import type { FixtureAuthority } from "./evidenceTypes";

type OperatorDiagnosticOwner = OperatorDiagnostic | RunOperatorDiagnostic;
type OperatorProjectionLabel =
  | OperatorProjectionStateLabel
  | RunOperatorProjectionStateLabel;

type IsExact<Left, Right> =
  (<Value>() => Value extends Left ? 1 : 2) extends <
    Value,
  >() => Value extends Right ? 1 : 2
    ? (<Value>() => Value extends Right ? 1 : 2) extends <
        Value,
      >() => Value extends Left ? 1 : 2
      ? true
      : false
    : false;

function assertProjectionVocabularyParity(
  _state: IsExact<
    OperatorProjectionStateLabel["state"],
    RunOperatorProjectionStateLabel["state"]
  > extends true
    ? true
    : never,
  _authority: IsExact<
    OperatorProjectionStateLabel["authority"],
    RunOperatorProjectionStateLabel["authority"]
  > extends true
    ? true
    : never,
): void {}

assertProjectionVocabularyParity(true, true);

const authorityPresentationBrand = Symbol("polisyos.authority-presentation");
const authorityPresentationIssuances = new WeakSet<object>();

export type AuthorityPresentation = Readonly<{
  [authorityPresentationBrand]: true;
  authority: string;
  ownerAuthority?: string;
  presentation: "recognized" | "unrecognized";
  source:
    | "opaque_extension"
    | "operator_blocking_cause"
    | "operator_projection_label";
  state?: string;
  suppressedByBlocker?: boolean;
  tone: BadgeTone;
}>;

export type AuthorityBadgeProps = {
  id?: string;
  /** Branded presentation derived from an owner DTO, never caller-selected tone. */
  presentation: AuthorityPresentation;
  title?: string;
};

const projectionStateTones = {
  approved: "ok",
  blocked: "fail",
  contested: "warn",
  draft: "neutral",
  projected: "neutral",
  projection_only: "neutral",
  publishable: "ok",
  published_blocked: "fail",
  readiness_closed: "fail",
  redacted: "neutral",
  rejected: "fail",
  stale: "warn",
} satisfies Record<OperatorProjectionLabel["state"], BadgeTone>;

function assertNotFixtureAuthority(authority: string) {
  if (authority === ("fixture_only" satisfies FixtureAuthority)) {
    throw new TypeError("fixture provenance cannot enter an authority slot");
  }
}

function createPresentation(
  presentation: Omit<AuthorityPresentation, typeof authorityPresentationBrand>,
): AuthorityPresentation {
  assertNotFixtureAuthority(presentation.authority);
  if (presentation.ownerAuthority !== undefined) {
    assertNotFixtureAuthority(presentation.ownerAuthority);
  }
  const issued: AuthorityPresentation = {
    [authorityPresentationBrand]: true as const,
    ...presentation,
  };
  authorityPresentationIssuances.add(issued);
  return Object.freeze(issued);
}

/** Preserve an open owner extension verbatim in the only safe neutral posture. */
export function createOpaqueAuthorityPresentation(
  authority: string,
): AuthorityPresentation {
  return createPresentation({
    authority,
    presentation: "unrecognized",
    source: "opaque_extension",
    tone: "neutral",
  });
}

/** Derive blocker clothing from the generated diagnostic field, not its label. */
export function createOperatorBlockingCausePresentation(
  diagnostic: OperatorDiagnosticOwner,
): AuthorityPresentation {
  return createPresentation({
    authority: diagnostic.first_blocking_cause,
    presentation: "recognized",
    source: "operator_blocking_cause",
    tone: "fail",
  });
}

/**
 * Derive projection clothing from the generated state and authority fields.
 * Positive projection labels are neutral while the owner reports a blocker.
 */
export function createOperatorProjectionPresentation(
  diagnostic: OperatorDiagnosticOwner,
  item: OperatorProjectionLabel,
): AuthorityPresentation {
  const ownerLabels = diagnostic.projection_labels as
    | readonly unknown[]
    | undefined;
  if (!ownerLabels?.includes(item)) {
    throw new TypeError(
      "projection label must be a member of the generated owner diagnostic",
    );
  }
  const runtimeItem = item as {
    authority?: unknown;
    label?: unknown;
    state?: unknown;
  };
  const authority =
    typeof runtimeItem.label === "string"
      ? runtimeItem.label
      : String(runtimeItem.label);
  const ownerAuthority = runtimeItem.authority;
  const state = runtimeItem.state;

  if (
    (ownerAuthority !== "runtime_authority" &&
      ownerAuthority !== "projection_only") ||
    typeof state !== "string" ||
    !Object.hasOwn(projectionStateTones, state)
  ) {
    return createPresentation({
      authority,
      ownerAuthority:
        typeof ownerAuthority === "string" ? ownerAuthority : undefined,
      presentation: "unrecognized",
      source: "operator_projection_label",
      state: typeof state === "string" ? state : undefined,
      tone: "neutral",
    });
  }

  const ownerTone =
    projectionStateTones[state as keyof typeof projectionStateTones];
  const suppressedByBlocker =
    ownerTone === "ok" && diagnostic.first_blocking_cause.length > 0;
  const tone =
    ownerAuthority === "projection_only" || suppressedByBlocker
      ? "neutral"
      : ownerTone;

  return createPresentation({
    authority,
    ownerAuthority,
    presentation: "recognized",
    source: "operator_projection_label",
    state,
    suppressedByBlocker,
    tone,
  });
}

function assertAuthorityPresentation(
  presentation: AuthorityPresentation,
): void {
  if (
    typeof presentation !== "object" ||
    presentation === null ||
    presentation[authorityPresentationBrand] !== true ||
    !authorityPresentationIssuances.has(presentation)
  ) {
    throw new TypeError("authority presentation must be owner-derived");
  }
  assertNotFixtureAuthority(presentation.authority);
  if (presentation.ownerAuthority !== undefined) {
    assertNotFixtureAuthority(presentation.ownerAuthority);
  }
}

/**
 * Displays an owner-supplied authority value without owning its vocabulary.
 * Unrecognized extensions are always neutral and remain visible verbatim.
 */
export function AuthorityBadge({
  id,
  presentation,
  title,
}: AuthorityBadgeProps) {
  assertAuthorityPresentation(presentation);

  return (
    <Badge
      data-authority-recognition={presentation.presentation}
      data-authority-source={presentation.source}
      data-authority-state={presentation.state}
      data-owner-authority={presentation.ownerAuthority}
      data-presentation-tone={presentation.tone}
      data-suppressed-by-blocker={
        presentation.suppressedByBlocker ? "true" : undefined
      }
      kind={presentation.tone}
      id={id}
      title={title}
    >
      {presentation.authority}
    </Badge>
  );
}
