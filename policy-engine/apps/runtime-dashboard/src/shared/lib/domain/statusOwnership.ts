const interactionStateBrand = Symbol("polisyos.interaction-state");
declare const generatedAuthorityBrand: unique symbol;

export type InteractionAuthorityPurpose =
  | "candidate_display"
  | "diagnostic_display"
  | "loading"
  | "playback"
  | "progress"
  | "telemetry"
  | "transport";

export type InteractionState<Label extends string = string> = Readonly<{
  [interactionStateBrand]: true;
  label: Label;
  purpose: "interaction_only";
  authorityPurpose: InteractionAuthorityPurpose;
}>;

/** A value whose type originates at a generated indexed authority field. */
export type GeneratedAuthorityValue<Label extends string = string> = Label & {
  readonly [generatedAuthorityBrand]: "generated_indexed";
};

type StatusOwnerDescriptor =
  | Readonly<{
      kind: "generated_indexed";
      module: "@polisyos/runtime-api-client";
      query: string;
    }>
  | Readonly<{
      kind: "interaction_wrapper";
      module: "@/shared/lib/domain/statusOwnership";
      query: "InteractionState";
    }>
  | Readonly<{
      kind: "none";
      module?: never;
      query?: never;
    }>;

export function createInteractionState<const Label extends string>(
  label: Label,
  authorityPurpose: InteractionAuthorityPurpose,
): InteractionState<Label> {
  return Object.freeze({
    [interactionStateBrand]: true as const,
    label,
    purpose: "interaction_only" as const,
    authorityPurpose,
  });
}

export function isInteractionState(value: unknown): value is InteractionState {
  return (
    typeof value === "object" &&
    value !== null &&
    interactionStateBrand in value &&
    (value as { [interactionStateBrand]?: unknown })[interactionStateBrand] ===
      true
  );
}

/** Validate metadata used by inventory consumers; local authority owners fail closed. */
export function inspectStatusOwner(owner: unknown): StatusOwnerDescriptor {
  if (typeof owner !== "object" || owner === null || !("kind" in owner)) {
    throw new TypeError("status owner metadata is invalid");
  }
  const candidate = owner as {
    kind?: unknown;
    module?: unknown;
    query?: unknown;
  };
  if (candidate.kind === "local_union") {
    throw new TypeError("UI-local authority vocabularies are forbidden");
  }
  if (
    candidate.kind === "generated_indexed" &&
    candidate.module === "@polisyos/runtime-api-client" &&
    typeof candidate.query === "string"
  ) {
    return candidate as StatusOwnerDescriptor;
  }
  if (
    candidate.kind === "interaction_wrapper" &&
    candidate.module === "@/shared/lib/domain/statusOwnership" &&
    candidate.query === "InteractionState"
  ) {
    return candidate as StatusOwnerDescriptor;
  }
  if (candidate.kind === "none") {
    return { kind: "none" };
  }
  throw new TypeError("status owner metadata is invalid");
}

/** Authority-bearing render slots accept generated values and reject interaction state. */
export function presentAuthority<Label extends string>(
  value: GeneratedAuthorityValue<Label>,
): GeneratedAuthorityValue<Label> {
  if (isInteractionState(value)) {
    throw new TypeError("interaction state cannot enter an authority slot");
  }
  return value;
}
