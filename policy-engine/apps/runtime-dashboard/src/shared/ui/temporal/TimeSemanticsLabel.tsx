import type { ProjectionFreshness } from "@polisyos/runtime-api-client";

import { cn } from "@/shared/lib/utils";

import { presentCacheAgeLabel } from "./cacheAgePresentation";

type TimeSemanticsLabelProps = {
  cacheAgeLabel?: unknown;
  className?: string;
  freshness?: ProjectionFreshness | null;
  payloadAsOf?: string | null;
  txAt?: string | null;
  validAt?: string | null;
};

export function TimeSemanticsLabel({
  cacheAgeLabel,
  className,
  freshness,
  payloadAsOf,
  txAt,
  validAt,
}: TimeSemanticsLabelProps) {
  const cacheAge = presentCacheAgeLabel(cacheAgeLabel);
  const cacheAgeValue = cacheAge.ownerLabel ?? "unknown";

  return (
    <dl
      className={cn("text-muted grid gap-1 text-xs", className)}
      data-cache-age-presentation={cacheAge.classification}
    >
      <TimeEntry label="Policy valid at" testId="valid-at" value={validAt} />
      <TimeEntry label="Knowledge tx at" testId="tx-at" value={txAt} />
      <TimeEntry
        label="Payload as of"
        testId="payload-as-of"
        value={payloadAsOf}
      />
      <TimeEntry
        label="Source as of"
        testId="source-as-of"
        value={freshness?.source_as_of}
      />
      <TimeEntry
        label="Observed at"
        testId="observed-at"
        value={freshness?.observed_at}
      />
      <TimeEntry
        label="Source state"
        testId="source-state"
        value={freshness?.state}
      />
      <TimeEntry
        label="Cache age"
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
