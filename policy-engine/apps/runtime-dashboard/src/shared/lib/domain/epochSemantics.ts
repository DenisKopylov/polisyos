export type EpochProjectionStatus =
  | "current"
  | "stale"
  | "revalidation_required"
  | "contested"
  | "not_established";

export type EpochSemantics = Readonly<{
  asOf: string | null;
  asOfReason:
    | "epoch_projection_not_established"
    | "epoch_scope_unresolved"
    | "owner_time_not_established"
    | null;
  currentEpochRef: string | null;
  epochRefs: readonly string[];
  kind: "admitted" | "nonreceipt";
  projectionSemanticHash: string | null;
  revalidationRequired: boolean;
  status: EpochProjectionStatus;
  validityStatus: string | null;
}>;

const EPOCH_REF_PATTERN = /^sha256:[0-9a-f]{64}$/u;

export function epochNonreceipt(): EpochSemantics {
  return Object.freeze({
    asOf: null,
    asOfReason: "epoch_projection_not_established",
    currentEpochRef: null,
    epochRefs: Object.freeze([]),
    kind: "nonreceipt",
    projectionSemanticHash: null,
    revalidationRequired: false,
    status: "not_established",
    validityStatus: null,
  });
}

export function isEpochSemantics(value: unknown): value is EpochSemantics {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  const keys = Object.keys(candidate).sort();
  const expectedKeys = [
    "asOf",
    "asOfReason",
    "currentEpochRef",
    "epochRefs",
    "kind",
    "projectionSemanticHash",
    "revalidationRequired",
    "status",
    "validityStatus",
  ].sort();
  if (keys.join("\0") !== expectedKeys.join("\0")) {
    return false;
  }
  const statusValid = [
    "current",
    "stale",
    "revalidation_required",
    "contested",
    "not_established",
  ].includes(String(candidate.status));
  const reasonValid = [
    null,
    "epoch_projection_not_established",
    "epoch_scope_unresolved",
    "owner_time_not_established",
  ].includes(candidate.asOfReason as null | string);
  const epochRefsValid =
    Array.isArray(candidate.epochRefs) &&
    candidate.epochRefs.every(
      (epochRef) =>
        typeof epochRef === "string" && EPOCH_REF_PATTERN.test(epochRef),
    );
  const currentEpochValid =
    candidate.currentEpochRef === null ||
    (typeof candidate.currentEpochRef === "string" &&
      EPOCH_REF_PATTERN.test(candidate.currentEpochRef));
  const hashValid =
    candidate.projectionSemanticHash === null ||
    (typeof candidate.projectionSemanticHash === "string" &&
      EPOCH_REF_PATTERN.test(candidate.projectionSemanticHash));
  const timeValid =
    candidate.asOf === null ||
    (typeof candidate.asOf === "string" &&
      !Number.isNaN(Date.parse(candidate.asOf)));
  const commonValid =
    statusValid &&
    reasonValid &&
    epochRefsValid &&
    currentEpochValid &&
    hashValid &&
    timeValid &&
    typeof candidate.revalidationRequired === "boolean" &&
    (candidate.validityStatus === null ||
      typeof candidate.validityStatus === "string");
  if (!commonValid) {
    return false;
  }
  if (candidate.kind === "nonreceipt") {
    return (
      candidate.asOf === null &&
      candidate.asOfReason === "epoch_projection_not_established" &&
      candidate.currentEpochRef === null &&
      Array.isArray(candidate.epochRefs) &&
      candidate.epochRefs.length === 0 &&
      candidate.projectionSemanticHash === null &&
      candidate.revalidationRequired === false &&
      candidate.status === "not_established" &&
      candidate.validityStatus === null
    );
  }
  return (
    candidate.kind === "admitted" &&
    typeof candidate.projectionSemanticHash === "string" &&
    (candidate.asOf === null) !== (candidate.asOfReason === null)
  );
}

export function formatEpochSemanticsSummary(epoch: EpochSemantics): string {
  if (epoch.kind === "nonreceipt") {
    return `Epoch not established (${epoch.asOfReason})`;
  }
  const epochRef = epoch.currentEpochRef ?? "epoch not established";
  const asOf = epoch.asOf ?? epoch.asOfReason ?? "as_of not established";
  const validity = epoch.validityStatus ?? "validity not established";
  const revalidation = epoch.revalidationRequired
    ? "; revalidation required"
    : "";
  return `${epochRef}; as of ${asOf}; ${epoch.status}; ${validity}${revalidation}`;
}
