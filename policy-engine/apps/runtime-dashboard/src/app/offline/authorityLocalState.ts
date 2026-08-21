/**
 * Owns fail-closed, identity-scoped persistence for non-authority local state.
 *
 * The adapter is deliberately limited to encoding and hydrating bytes. It does
 * not confer authority and must not be used for server, epoch, or rule
 * revalidation.
 */

const persistedEnvelopeIssuerBrand: unique symbol = Symbol(
  "polisyos.persisted-local-state-envelope",
);

const ENVELOPE_FIELDS = [
  "encodedPayload",
  "expiresAt",
  "family",
  "issuedAt",
  "slot",
  "tenantId",
  "userId",
  "version",
] as const;

const LOCAL_STATE_KEY_PREFIX = "polisyos.authority-local-state.v1";

export type AuthorityLocalScope = Readonly<{
  tenantId: string;
  userId: string;
}>;

/**
 * Represents an envelope issued only by this module.
 *
 * The module-private unique-symbol property makes the type nominal: callers
 * can observe a hydrated envelope only through the adapter and cannot issue a
 * structurally equivalent value.
 */
export type PersistedEnvelope<StoreClass extends string> = Readonly<{
  readonly [persistedEnvelopeIssuerBrand]: StoreClass;
  readonly encodedPayload: unknown;
  readonly expiresAt: string;
  readonly family: StoreClass;
  readonly issuedAt: string;
  readonly slot: string;
  readonly tenantId: string;
  readonly userId: string;
  readonly version: number;
}>;

export type AuthorityLocalStateCodec<Value> = Readonly<{
  decode: (encoded: unknown) => Value | null;
  encode: (value: Value) => unknown;
}>;

export type AuthorityLocalStateFamily<StoreClass extends string, Value> =
  Readonly<{
    key: (input: {
      scope: AuthorityLocalScope | null | undefined;
      slot: string;
    }) => string | null;
    read: (input: {
      fallback: Value;
      scope: AuthorityLocalScope | null | undefined;
      slot: string;
    }) => Value;
    write: (input: {
      scope: AuthorityLocalScope | null | undefined;
      slot: string;
      value: Value;
    }) => boolean;
  }>;

export type AuthorityLocalStateEnvelopeFamily<StoreClass extends string, Value> =
  Readonly<{
    decode: <Fallback extends Value | null>(input: {
      envelope: unknown;
      fallback: Fallback;
      scope: AuthorityLocalScope | null | undefined;
      slot: string;
    }) => Value | Fallback;
    encode: (input: {
      scope: AuthorityLocalScope | null | undefined;
      slot: string;
      value: Value;
    }) => Readonly<{
      envelope: Omit<
        PersistedEnvelope<StoreClass>,
        typeof persistedEnvelopeIssuerBrand
      >;
      key: string;
    }> | null;
    key: (input: {
      scope: AuthorityLocalScope | null | undefined;
      slot: string;
    }) => string | null;
  }>;

export type AuthorityLocalStateEnvelopeFamilyConfig<
  StoreClass extends string,
  Value,
> =
  Readonly<{
    clock: () => Date;
    codec: AuthorityLocalStateCodec<Value>;
    family: StoreClass;
    ttlMs: number;
    version: number;
  }>;

type AuthorityLocalStateFamilyConfig<StoreClass extends string, Value> =
  AuthorityLocalStateEnvelopeFamilyConfig<StoreClass, Value> &
    Readonly<{
      storage: () => Storage | null;
    }>;

type ParsedEnvelope<StoreClass extends string> = Omit<
  PersistedEnvelope<StoreClass>,
  typeof persistedEnvelopeIssuerBrand
>;

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isCompleteScope(
  scope: AuthorityLocalScope | null | undefined,
): scope is AuthorityLocalScope {
  return (
    scope !== null &&
    scope !== undefined &&
    isNonEmptyString(scope.tenantId) &&
    isNonEmptyString(scope.userId)
  );
}

function isCanonicalTimestamp(value: unknown): value is string {
  if (typeof value !== "string") {
    return false;
  }
  const milliseconds = Date.parse(value);
  return Number.isFinite(milliseconds) && new Date(milliseconds).toISOString() === value;
}

function freezeRecursively<Value>(value: Value): Value {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) {
    return value;
  }
  for (const nested of Object.values(value)) {
    freezeRecursively(nested);
  }
  return Object.freeze(value);
}

function copyEncodedPayload(value: unknown): unknown {
  try {
    const serialized = JSON.stringify(value);
    if (typeof serialized !== "string") {
      return null;
    }
    return JSON.parse(serialized) as unknown;
  } catch {
    return null;
  }
}

function scopedKey(input: {
  family: string;
  scope: AuthorityLocalScope;
  slot: string;
}): string {
  return [
    LOCAL_STATE_KEY_PREFIX,
    input.family,
    input.scope.tenantId,
    input.scope.userId,
    input.slot,
  ]
    .map((part) => encodeURIComponent(part))
    .join(":");
}

function parseEnvelope<StoreClass extends string>(input: {
  expectedFamily: StoreClass;
  expectedScope: AuthorityLocalScope;
  expectedSlot: string;
  now: Date;
  raw: unknown;
  ttlMs: number;
  version: number;
}): ParsedEnvelope<StoreClass> | null {
  const parsed = input.raw;
  if (!isRecord(parsed)) {
    return null;
  }
  const fields = Object.keys(parsed).sort();
  if (
    fields.length !== ENVELOPE_FIELDS.length ||
    fields.some((field, index) => field !== ENVELOPE_FIELDS[index])
  ) {
    return null;
  }
  if (
    parsed.family !== input.expectedFamily ||
    parsed.tenantId !== input.expectedScope.tenantId ||
    parsed.userId !== input.expectedScope.userId ||
    parsed.slot !== input.expectedSlot ||
    parsed.version !== input.version ||
    !isCanonicalTimestamp(parsed.issuedAt) ||
    !isCanonicalTimestamp(parsed.expiresAt)
  ) {
    return null;
  }
  const issuedAt = Date.parse(parsed.issuedAt);
  const expiresAt = Date.parse(parsed.expiresAt);
  const now = input.now.getTime();
  if (
    !Number.isFinite(now) ||
    issuedAt > now ||
    expiresAt <= now ||
    expiresAt - issuedAt !== input.ttlMs
  ) {
    return null;
  }
  return parsed as ParsedEnvelope<StoreClass>;
}

/**
 * Creates the canonical local-state envelope seam without choosing a storage
 * transport. Storage adapters delegate here for keys, TTL, clock, validation,
 * and codec handling.
 */
export function createAuthorityLocalStateEnvelopeFamily<
  StoreClass extends string,
  Value,
>(
  config: AuthorityLocalStateEnvelopeFamilyConfig<StoreClass, Value>,
): AuthorityLocalStateEnvelopeFamily<StoreClass, Value> {
  if (!isNonEmptyString(config.family) || !Number.isInteger(config.version) || config.version < 1) {
    throw new Error("Authority local-state family configuration is invalid.");
  }
  if (!Number.isFinite(config.ttlMs) || config.ttlMs <= 0) {
    throw new Error("Authority local-state family TTL must be positive.");
  }

  function key(input: {
    scope: AuthorityLocalScope | null | undefined;
    slot: string;
  }): string | null {
    if (!isCompleteScope(input.scope) || !isNonEmptyString(input.slot)) {
      return null;
    }
    return scopedKey({ family: config.family, scope: input.scope, slot: input.slot });
  }

  return Object.freeze({
    decode<Fallback extends Value | null>(input: {
      envelope: unknown;
      fallback: Fallback;
      scope: AuthorityLocalScope | null | undefined;
      slot: string;
    }): Value | Fallback {
      if (!isCompleteScope(input.scope) || !isNonEmptyString(input.slot)) {
        return input.fallback;
      }
      let envelope: ParsedEnvelope<StoreClass> | null;
      try {
        envelope = parseEnvelope({
          expectedFamily: config.family,
          expectedScope: input.scope,
          expectedSlot: input.slot,
          now: config.clock(),
          raw: input.envelope,
          ttlMs: config.ttlMs,
          version: config.version,
        });
      } catch {
        return input.fallback;
      }
      if (!envelope) {
        return input.fallback;
      }
      try {
        const decoded = config.codec.decode(envelope.encodedPayload);
        return decoded === null ? input.fallback : freezeRecursively(decoded);
      } catch {
        return input.fallback;
      }
    },
    encode(input) {
      const physicalKey = key(input);
      if (!physicalKey || !isCompleteScope(input.scope)) {
        return null;
      }
      let issued: Date;
      let expires: Date;
      let encodedPayload: unknown;
      try {
        issued = config.clock();
        expires = new Date(issued.getTime() + config.ttlMs);
        if (!Number.isFinite(issued.getTime()) || !Number.isFinite(expires.getTime())) {
          return null;
        }
        encodedPayload = copyEncodedPayload(config.codec.encode(input.value));
        if (encodedPayload === null) {
          return null;
        }
      } catch {
        return null;
      }
      const issuedEnvelope: PersistedEnvelope<StoreClass> = freezeRecursively({
        [persistedEnvelopeIssuerBrand]: config.family,
        encodedPayload,
        expiresAt: expires.toISOString(),
        family: config.family,
        issuedAt: issued.toISOString(),
        slot: input.slot,
        tenantId: input.scope.tenantId,
        userId: input.scope.userId,
        version: config.version,
      });
      return Object.freeze({
        envelope: Object.freeze({
          encodedPayload: issuedEnvelope.encodedPayload,
          expiresAt: issuedEnvelope.expiresAt,
          family: issuedEnvelope.family,
          issuedAt: issuedEnvelope.issuedAt,
          slot: issuedEnvelope.slot,
          tenantId: issuedEnvelope.tenantId,
          userId: issuedEnvelope.userId,
          version: issuedEnvelope.version,
        }),
        key: physicalKey,
      });
    },
    key,
  });
}

/**
 * Creates one writer-owned local-state family adapter.
 *
 * Family, codec, clock, storage, version, and TTL are fixed at construction;
 * callers supply only verified scope, logical slot, and payload. Invalid bytes
 * are never migrated or rewritten during reads.
 */
export function createAuthorityLocalStateFamily<StoreClass extends string, Value>(
  config: AuthorityLocalStateFamilyConfig<StoreClass, Value>,
): AuthorityLocalStateFamily<StoreClass, Value> {
  const owner = createAuthorityLocalStateEnvelopeFamily(config);

  return Object.freeze({
    key: owner.key,
    read(input) {
      const physicalKey = owner.key(input);
      if (!physicalKey) {
        return input.fallback;
      }
      let raw: string | null;
      try {
        raw = config.storage()?.getItem(physicalKey) ?? null;
      } catch {
        return input.fallback;
      }
      if (!raw) {
        return input.fallback;
      }
      try {
        return owner.decode({
          envelope: JSON.parse(raw) as unknown,
          fallback: input.fallback,
          scope: input.scope,
          slot: input.slot,
        });
      } catch {
        return input.fallback;
      }
    },
    write(input) {
      const issued = owner.encode(input);
      if (!issued) {
        return false;
      }
      try {
        const storage = config.storage();
        if (!storage) {
          return false;
        }
        storage.setItem(
          issued.key,
          JSON.stringify(issued.envelope),
        );
        return true;
      } catch {
        return false;
      }
    },
  });
}
