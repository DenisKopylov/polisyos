import type { ProjectionFreshness } from "@polisyos/runtime-api-client";

import {
  hasOwnerAsOf,
  isIssuedCacheObservation,
  type CacheObservation,
} from "@/api/cacheDiscipline";
import { cn } from "@/shared/lib/utils";

import { presentCacheAgeLabel } from "./cacheAgePresentation";

type TimeSemanticsLabelProps = {
  cacheAgeLabel?: unknown;
  cacheObservation?: CacheObservation | null;
  className?: string;
  freshness?: ProjectionFreshness | null;
  payloadAsOf?: string | null;
  txAt?: string | null;
  validAt?: string | null;
};

type CachePosturePresentation = Readonly<{
  asOf: string | null;
  posture: CacheObservation["posture"];
}>;

const UNRECOGNIZED_CACHE_POSTURE: CachePosturePresentation = Object.freeze({
  asOf: null,
  posture: "unrecognized",
});

function presentCacheObservation(
  value: CacheObservation | null,
): CachePosturePresentation {
  if (!isIssuedCacheObservation(value)) {
    return UNRECOGNIZED_CACHE_POSTURE;
  }

  try {
    const { asOf, posture } = value;
    if (posture === "unrecognized" && asOf === null) {
      return UNRECOGNIZED_CACHE_POSTURE;
    }
    if (
      (posture === "live" || posture === "cached" || posture === "stale") &&
      hasOwnerAsOf(asOf)
    ) {
      return Object.freeze({ asOf, posture });
    }
  } catch {
    return UNRECOGNIZED_CACHE_POSTURE;
  }

  return UNRECOGNIZED_CACHE_POSTURE;
}

export function TimeSemanticsLabel({
  cacheAgeLabel,
  cacheObservation,
  className,
  freshness,
  payloadAsOf,
  txAt,
  validAt,
}: TimeSemanticsLabelProps) {
  const cacheAge = presentCacheAgeLabel(cacheAgeLabel);
  const cacheAgeValue = cacheAge.ownerLabel ?? "unknown";
  const cachePosture =
    cacheObservation === undefined
      ? null
      : presentCacheObservation(cacheObservation);

  return (
    <dl
      className={cn("text-muted grid gap-1 text-xs", className)}
      data-cache-age-presentation={cacheAge.classification}
      data-cache-posture-presentation={cachePosture?.posture}
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
      {cachePosture ? (
        <>
          <TimeEntry
            label="Cache posture"
            testId="cache-posture"
            value={cachePosture.posture}
          />
          <TimeEntry
            label="Cache owner as of"
            testId="cache-owner-as-of"
            value={cachePosture.asOf}
          />
        </>
      ) : null}
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
