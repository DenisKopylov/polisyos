import type {
  AvailableGovernedProjectionPacket,
  LegacyProvingGroundPayload,
} from "@polisyos/runtime-api-client";

/** Canonical fixture provenance, indexed from the generated HTTP waist. */
export type FixtureAuthority = LegacyProvingGroundPayload["fixture_authority"];

const fixtureProvenanceBrand = Symbol("polisyos.fixture-provenance");
const governedAuthorityPurposeBrand = Symbol(
  "polisyos.governed-authority-purpose",
);
const fixtureProvenanceIssuances = new WeakSet<object>();
const governedAuthorityPurposeIssuances = new WeakMap<
  object,
  Readonly<{
    fixtureAuthority?: FixtureAuthority;
    value: AvailableGovernedProjectionPacket["authoritative_for"][number];
  }>
>();

/** Nominal proof that fixture provenance came through the generated payload. */
export type FixtureProvenance = Readonly<{
  [fixtureProvenanceBrand]: true;
  authority: FixtureAuthority;
}>;

/** Nominal owner-purpose selection from a generated governed packet. */
export type GovernedAuthorityPurpose = Readonly<{
  [governedAuthorityPurposeBrand]: true;
  value: AvailableGovernedProjectionPacket["authoritative_for"][number];
}>;

function exactFixtureAuthority(authority: FixtureAuthority): "fixture_only" {
  return authority;
}

function issueFixtureProvenance(
  authority: FixtureAuthority,
): FixtureProvenance {
  const provenance: FixtureProvenance = {
    [fixtureProvenanceBrand]: true,
    authority,
  };
  fixtureProvenanceIssuances.add(provenance);
  return Object.freeze(provenance);
}

/** Create fixture presentation proof from the complete generated fixture DTO. */
export function createFixtureProvenance(
  payload: LegacyProvingGroundPayload,
): FixtureProvenance {
  const authority = exactFixtureAuthority(payload.fixture_authority);
  if (authority !== "fixture_only") {
    throw new TypeError("generated fixture provenance is required");
  }
  return issueFixtureProvenance(authority);
}

function issueGovernedAuthorityPurpose(
  value: AvailableGovernedProjectionPacket["authoritative_for"][number],
  fixtureAuthority?: FixtureAuthority,
): GovernedAuthorityPurpose {
  const purpose: GovernedAuthorityPurpose = {
    [governedAuthorityPurposeBrand]: true,
    value,
  };
  governedAuthorityPurposeIssuances.set(
    purpose,
    Object.freeze({ fixtureAuthority, value }),
  );
  return Object.freeze(purpose);
}

/** Select a purpose only when the generated owner packet declares it. */
export function createGovernedAuthorityPurpose(
  packet: AvailableGovernedProjectionPacket,
  authorityPurpose: AvailableGovernedProjectionPacket["authoritative_for"][number],
): GovernedAuthorityPurpose {
  if (packet.availability !== "available") {
    throw new TypeError("an available generated owner packet is required");
  }
  if (!packet.authoritative_for.includes(authorityPurpose)) {
    throw new TypeError(
      "authority purpose is not declared by the owner packet",
    );
  }
  const payload =
    typeof packet.payload === "object" && packet.payload !== null
      ? (packet.payload as { fixture_authority?: unknown })
      : null;
  const hasFixtureAuthority =
    payload !== null && Object.hasOwn(payload, "fixture_authority");
  if (
    (hasFixtureAuthority && payload.fixture_authority !== "fixture_only") ||
    (packet.projection_id === "legacy-proving-ground" &&
      payload?.fixture_authority !== "fixture_only")
  ) {
    throw new TypeError("fixture-backed packets require the canonical marker");
  }
  const fixtureAuthority =
    payload?.fixture_authority === "fixture_only"
      ? fixtureAuthorityValue(
          createFixtureProvenance(packet.payload as LegacyProvingGroundPayload),
        )
      : undefined;
  return issueGovernedAuthorityPurpose(authorityPurpose, fixtureAuthority);
}

export function fixtureAuthorityValue(
  provenance: FixtureProvenance,
): FixtureAuthority {
  if (
    typeof provenance !== "object" ||
    provenance === null ||
    provenance[fixtureProvenanceBrand] !== true ||
    !fixtureProvenanceIssuances.has(provenance)
  ) {
    throw new TypeError(
      "fixture provenance must come from the generated payload",
    );
  }
  return provenance.authority;
}

export function governedAuthorityPurposePresentation(
  purpose: GovernedAuthorityPurpose,
): Readonly<{
  fixtureAuthority?: FixtureAuthority;
  value: AvailableGovernedProjectionPacket["authoritative_for"][number];
}> {
  if (
    typeof purpose !== "object" ||
    purpose === null ||
    purpose[governedAuthorityPurposeBrand] !== true
  ) {
    throw new TypeError(
      "authority purpose must come from a generated owner packet",
    );
  }
  const issued = governedAuthorityPurposeIssuances.get(purpose);
  if (!issued) {
    throw new TypeError(
      "authority purpose must come from a generated owner packet",
    );
  }
  return issued;
}
