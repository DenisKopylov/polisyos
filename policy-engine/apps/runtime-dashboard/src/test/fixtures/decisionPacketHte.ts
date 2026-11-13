import actualR4Interval from "./decisionPacketHte-wire/runtime-r4-interval.json";
import actualR4Point from "./decisionPacketHte-wire/runtime-r4-point.json";
import actualR4Refusal from "./decisionPacketHte-wire/runtime-r4-refusal.json";
import actualR5OwnerPoint from "./decisionPacketHte-wire/runtime-r5-point-owner-builder.json";
import actualR5DualPoint from "./decisionPacketHte-wire/runtime-r5-dual-observation-point.json";
import actualLegacyWire from "./decisionPacketHte-wire/legacy-builder-wire.json";
import actualLegacyLimited from "./decisionPacketHte-wire/legacy-limited-preview.json";
import actualLegacyUnavailable from "./decisionPacketHte-wire/legacy-unavailable-preview.json";

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
