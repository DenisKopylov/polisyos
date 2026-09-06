import { createContext, type ReactNode, useContext, useMemo } from "react";
import type { ProjectionFreshness } from "@polisyos/runtime-api-client";

import { useOptionalI18n } from "@/shared/i18n/LocaleProvider";
import {
  epochNonreceipt,
  isEpochSemantics,
  type EpochSemantics,
} from "@/shared/lib/domain/epochSemantics";
import { cn } from "@/shared/lib/utils";

import { presentCacheAgeLabel } from "./cacheAgePresentation";

export {
  epochNonreceipt,
  formatEpochSemanticsSummary,
  isEpochSemantics,
  type EpochProjectionStatus,
  type EpochSemantics,
} from "@/shared/lib/domain/epochSemantics";

const EpochSemanticsContext = createContext<EpochSemantics | null>(null);

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
