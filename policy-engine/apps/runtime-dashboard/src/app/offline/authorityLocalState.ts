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

type AuthorityLocalStateFamilyConfig<StoreClass extends string, Value> =
  Readonly<{
    clock: () => Date;
    codec: AuthorityLocalStateCodec<Value>;
    family: StoreClass;
    storage: () => Storage | null;
    ttlMs: number;
    version: number;
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
  raw: string;
  ttlMs: number;
  version: number;
}): ParsedEnvelope<StoreClass> | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(input.raw) as unknown;
  } catch {
    return null;
  }
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
 * Creates one writer-owned local-state family adapter.
 *
 * Family, codec, clock, storage, version, and TTL are fixed at construction;
 * callers supply only verified scope, logical slot, and payload. Invalid bytes
 * are never migrated or rewritten during reads.
 */
export function createAuthorityLocalStateFamily<StoreClass extends string, Value>(
  config: AuthorityLocalStateFamilyConfig<StoreClass, Value>,
): AuthorityLocalStateFamily<StoreClass, Value> {
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
    key,
    read(input) {
      const physicalKey = key(input);
      if (!physicalKey || !isCompleteScope(input.scope)) {
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
      let envelope: ParsedEnvelope<StoreClass> | null;
      try {
        envelope = parseEnvelope({
          expectedFamily: config.family,
          expectedScope: input.scope,
          expectedSlot: input.slot,
          now: config.clock(),
          raw,
          ttlMs: config.ttlMs,
          version: config.version,
        });
      } catch {
        return input.fallback;
      }
      if (!envelope) {
        return input.fallback;
      }
      let decoded: Value | null;
      try {
        decoded = config.codec.decode(envelope.encodedPayload);
      } catch {
        return input.fallback;
      }
      return decoded === null ? input.fallback : freezeRecursively(decoded);
    },
    write(input) {
      const physicalKey = key(input);
      if (!physicalKey || !isCompleteScope(input.scope)) {
        return false;
      }
      let issued: Date;
      let expires: Date;
      let encodedPayload: unknown;
      try {
        issued = config.clock();
        expires = new Date(issued.getTime() + config.ttlMs);
        if (!Number.isFinite(issued.getTime()) || !Number.isFinite(expires.getTime())) {
          return false;
        }
        encodedPayload = copyEncodedPayload(config.codec.encode(input.value));
        if (encodedPayload === null) {
          return false;
        }
      } catch {
        return false;
      }
      const envelope: PersistedEnvelope<StoreClass> = freezeRecursively({
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
      try {
        const storage = config.storage();
        if (!storage) {
          return false;
        }
        storage.setItem(
          physicalKey,
          JSON.stringify({
            encodedPayload: envelope.encodedPayload,
            expiresAt: envelope.expiresAt,
            family: envelope.family,
            issuedAt: envelope.issuedAt,
            slot: envelope.slot,
            tenantId: envelope.tenantId,
            userId: envelope.userId,
            version: envelope.version,
          }),
        );
        return true;
      } catch {
        return false;
      }
    },
  });
}
