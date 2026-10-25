import actualR4Interval from "./wire/runtime-r4-interval.json";
import actualR4Point from "./wire/runtime-r4-point.json";
import actualR4Refusal from "./wire/runtime-r4-refusal.json";
import actualR5OwnerPoint from "./wire/runtime-r5-point-owner-builder.json";
import actualR5DualPoint from "./wire/runtime-r5-dual-observation-point.json";
import actualLegacyWire from "./wire/legacy-builder-wire.json";
import actualLegacyLimited from "./wire/legacy-limited-preview.json";
import actualLegacyUnavailable from "./wire/legacy-unavailable-preview.json";

export type HTEWire = Record<string, unknown>;

function clone<T>(value: T): T {
  return structuredClone(value);
}

export function hteRef(char: string, kind: string) {
  return {
    artifact_id: `sha256:${char.repeat(64)}`,
    kind,
    media_type: "application/json",
    manifest_profile_sha256: `sha256:${"a".repeat(64)}`,
  };
}

export function pointSummary(): HTEWire {
  return clone(actualR5OwnerPoint as HTEWire);
}

export function intervalSummary(): HTEWire {
  return clone(actualR4Interval as HTEWire);
}

export function r4PointSummary(): HTEWire {
  return clone(actualR4Point as HTEWire);
}

export function refusalSummary(): HTEWire {
  return clone(actualR4Refusal as HTEWire);
}

export function r5OwnerPointSummary(): HTEWire {
  return clone(actualR5OwnerPoint as HTEWire);
}

export function r5DualObservationSummary(): HTEWire {
  return clone(actualR5DualPoint as HTEWire);
}

export function legacyBuilderWire(): HTEWire {
  return clone(actualLegacyWire as HTEWire);
}

export function legacyLimitedProjection(): HTEWire {
  return clone(actualLegacyLimited as HTEWire);
}

export function legacyUnavailableProjection(): HTEWire {
  return clone(actualLegacyUnavailable as HTEWire);
}
