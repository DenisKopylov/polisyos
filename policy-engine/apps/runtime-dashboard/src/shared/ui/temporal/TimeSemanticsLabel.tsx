import { createContext, type ReactNode, useContext, useMemo } from "react";
import type { ProjectionFreshness } from "@polisyos/runtime-api-client";

import { useOptionalI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";

import { presentCacheAgeLabel } from "./cacheAgePresentation";

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
const EpochSemanticsContext = createContext<EpochSemantics | null>(null);

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

export function EpochSemanticsProvider({
  children,
  value,
}: {
  children: ReactNode;
  value: EpochSemantics;
}) {
  if (!isEpochSemantics(value)) {
    throw new TypeError("epoch semantics provider requires admitted semantics");
  }
  return (
    <EpochSemanticsContext.Provider value={value}>
      {children}
    </EpochSemanticsContext.Provider>
  );
}

export function useEpochSemantics(): EpochSemantics {
  return useContext(EpochSemanticsContext) ?? epochNonreceipt();
}

export type TimeSemanticsLabelProps = {
  cacheAgeLabel?: unknown;
  children?: ReactNode;
  className?: string;
  epochSemantics?: EpochSemantics | null;
  freshness?: ProjectionFreshness | null;
  payloadAsOf?: string | null;
  txAt?: string | null;
  validAt?: string | null;
};

export function TimeSemanticsLabel({
  cacheAgeLabel,
  children,
  className,
  epochSemantics,
  freshness,
  payloadAsOf,
  txAt,
  validAt,
}: TimeSemanticsLabelProps) {
  const { t } = useOptionalI18n();
  const inheritedEpochSemantics = useEpochSemantics();
  const epoch = useMemo(
    () => epochSemantics ?? inheritedEpochSemantics,
    [epochSemantics, inheritedEpochSemantics],
  );
  const cacheAge = presentCacheAgeLabel(cacheAgeLabel);
  const cacheAgeValue = cacheAge.ownerLabel ?? "unknown";
  const epochStatus = t(`epochChrome.status.${epoch.status}`);

  return (
    <dl
      className={cn(
        "text-muted grid gap-1 border-l-2 pl-2 text-xs",
        epoch.status === "current"
          ? "border-[var(--color-status-approved)]"
          : "border-[var(--color-status-warning)] bg-[color-mix(in_srgb,var(--color-status-warning)_8%,transparent)]",
        className,
      )}
      data-cache-age-presentation={cacheAge.classification}
      data-epoch-presentation={epoch.kind}
      data-epoch-status={epoch.status}
    >
      <TimeEntry
        label={t("epochChrome.validAt")}
        testId="valid-at"
        value={validAt}
      />
      <TimeEntry label={t("epochChrome.txAt")} testId="tx-at" value={txAt} />
      <TimeEntry
        label={t("epochChrome.payloadAsOf")}
        testId="payload-as-of"
        value={payloadAsOf}
      />
      <TimeEntry
        label={t("epochChrome.sourceAsOf")}
        testId="source-as-of"
        value={freshness?.source_as_of}
      />
      <TimeEntry
        label={t("epochChrome.observedAt")}
        testId="observed-at"
        value={freshness?.observed_at}
      />
      <TimeEntry
        label={t("epochChrome.sourceState")}
        testId="source-state"
        value={freshness?.state}
      />
      <TimeEntry
        label={t("epochChrome.asOf")}
        testId="as-of"
        value={epoch.asOf ?? epoch.asOfReason}
      />
      <TimeEntry
        label={t("epochChrome.epoch")}
        testId="epoch"
        value={epoch.currentEpochRef ?? t("epochChrome.notEstablished")}
      />
      <TimeEntry
        label={t("epochChrome.epochStatus")}
        testId="epoch-status"
        value={epochStatus}
      />
      <TimeEntry
        label={t("epochChrome.validity")}
        testId="validity"
        value={epoch.validityStatus ?? t("epochChrome.status.not_established")}
      />
      <TimeEntry
        label={t("epochChrome.revalidation")}
        testId="revalidation"
        value={t(
          epoch.revalidationRequired
            ? "epochChrome.required"
            : "epochChrome.notRequired",
        )}
      />
      {children}
      <TimeEntry
        label={t("epochChrome.cacheAge")}
        testId="cache-age"
        value={`${cacheAgeValue} (${cacheAge.classification})`}
      />
    </dl>
  );
}

function TimeEntry({
  label,
  testId,
  value,
}: {
  label: string;
  testId: string;
  value: string | null | undefined;
}) {
  return (
    <div
      className="flex flex-wrap gap-1"
      data-testid={`time-semantics-${testId}`}
    >
      <dt className="font-semibold">{label}:</dt>
      <dd className="font-mono">{value || "unknown"}</dd>
    </div>
  );
}
