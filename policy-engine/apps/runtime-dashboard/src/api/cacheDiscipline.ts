declare const cacheObservationBrand: unique symbol;

/** A cache-copy posture issued from the live query observer lifecycle. */
export type CacheObservation =
  | (Readonly<{
      posture: "live" | "cached" | "stale";
      asOf: string;
    }> & {
      readonly [cacheObservationBrand]: true;
    })
  | (Readonly<{
      posture: "unrecognized";
      asOf: null;
    }> & {
      readonly [cacheObservationBrand]: true;
    });

export type CachePosturePresentation = Readonly<{
  ownerAsOf: string | null;
  posture: CacheObservation["posture"];
}>;

type QueryObserverLifecycle = Readonly<{
  data: unknown;
  isFetchedAfterMount: boolean;
  isStale: boolean;
  fetchStatus: string;
}>;

const issuedCacheObservations = new WeakSet();

const UNRECOGNIZED_CACHE_POSTURE: CachePosturePresentation = Object.freeze({
  ownerAsOf: null,
  posture: "unrecognized",
});

const OWNER_AS_OF_PATTERN =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(Z|[+-]\d{2}:\d{2})$/u;

/** Return whether a supplied owner `as_of` has valid calendar and offset fields. */
export function hasOwnerAsOf(value: unknown): value is string {
  if (typeof value !== "string") {
    return false;
  }

  const match = OWNER_AS_OF_PATTERN.exec(value);
  if (!match) {
    return false;
  }

  const [
    ,
    yearText,
    monthText,
    dayText,
    hourText,
    minuteText,
    secondText,
    zone,
  ] = match;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  const hour = Number(hourText);
  const minute = Number(minuteText);
  const second = Number(secondText);
  const maxDay =
    month === 2
      ? year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0)
        ? 29
        : 28
      : month === 4 || month === 6 || month === 9 || month === 11
        ? 30
        : 31;

  if (
    month < 1 ||
    month > 12 ||
    day < 1 ||
    day > maxDay ||
    hour > 23 ||
    minute > 59 ||
    second > 59
  ) {
    return false;
  }

  if (zone === "Z") {
    return true;
  }

  const [offsetHour, offsetMinute] = zone.slice(1).split(":").map(Number);
  return offsetHour <= 23 && offsetMinute <= 59;
}

function issueCacheObservation(
  observation:
    | Readonly<{ posture: "live" | "cached" | "stale"; asOf: string }>
    | Readonly<{ posture: "unrecognized"; asOf: null }>,
): CacheObservation {
  const issued = Object.freeze(observation) as CacheObservation;
  issuedCacheObservations.add(issued);
  return issued;
}

/** Return whether a value was issued by the cache-observer lifecycle owner. */
export function isIssuedCacheObservation(
  value: unknown,
): value is CacheObservation {
  return (
    typeof value === "object" &&
    value !== null &&
    issuedCacheObservations.has(value)
  );
}

/** Project only an owner-issued cache observation into display data. */
export function presentCacheObservation(
  value: unknown,
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
      return Object.freeze({ ownerAsOf: asOf, posture });
    }
  } catch {
    return UNRECOGNIZED_CACHE_POSTURE;
  }

  return UNRECOGNIZED_CACHE_POSTURE;
}

/**
 * Issue the cache posture for one query observer result and owner packet time.
 *
 * Source timestamps are intentionally absent from this contract: cache posture
 * belongs to the query observer lifecycle, while owner `as_of` is preserved
 * only as the packet's supplied reference time.
 */
export function observeCachePosture(
  observer: QueryObserverLifecycle,
  ownerAsOf: unknown,
): CacheObservation {
  if (observer.data == null || !hasOwnerAsOf(ownerAsOf)) {
    return issueCacheObservation({ asOf: null, posture: "unrecognized" });
  }

  if (
    observer.fetchStatus !== "idle" &&
    observer.fetchStatus !== "fetching" &&
    observer.fetchStatus !== "paused"
  ) {
    return issueCacheObservation({ asOf: null, posture: "unrecognized" });
  }

  if (observer.isStale) {
    return issueCacheObservation({ asOf: ownerAsOf, posture: "stale" });
  }

  if (observer.isFetchedAfterMount && observer.fetchStatus === "idle") {
    return issueCacheObservation({ asOf: ownerAsOf, posture: "live" });
  }

  return issueCacheObservation({ asOf: ownerAsOf, posture: "cached" });
}
