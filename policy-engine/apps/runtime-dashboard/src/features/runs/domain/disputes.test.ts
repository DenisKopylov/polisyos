import { afterEach, describe, expect, it, vi } from "vitest";

import { isInteractionState } from "@/shared/lib/domain/statusOwnership";

import {
  createDisputePersistence,
  createDisputeStatus,
  type DisputeRecord,
  issueToDispute,
} from "./disputes";

const NOW = new Date("2026-08-16T12:00:00.000Z");
const DAY_MS = 24 * 60 * 60 * 1_000;
const SCOPE_A = { tenantId: "tenant-a", userId: "user-a" };
const SCOPE_B = { tenantId: "tenant-b", userId: "user-b" };

class MemoryStorage {
  readonly calls: string[] = [];
  readonly values = new Map<string, string>();

  getItem(key: string) {
    this.calls.push(`get:${key}`);
    return this.values.get(key) ?? null;
  }

  removeItem(key: string) {
    this.calls.push(`remove:${key}`);
    this.values.delete(key);
  }

  setItem(key: string, value: string) {
    this.calls.push(`set:${key}`);
    this.values.set(key, value);
  }
}

function dispute(overrides: Partial<DisputeRecord> = {}): DisputeRecord {
  return {
    actor: "reviewer",
    basis: "legal",
    id: "local:run-a:appeal",
    openedAt: "2026-08-16T11:00:00.000Z",
    status: createDisputeStatus("open"),
    target: "decision",
    title: "Appeal remains open",
    ...overrides,
  };
}

function changingScope() {
  let tenantReads = 0;
  let userReads = 0;
  return {
    reads: () => ({ tenant: tenantReads, user: userReads }),
    scope: {
      get tenantId() {
        tenantReads += 1;
        return tenantReads === 1 ? SCOPE_A.tenantId : SCOPE_B.tenantId;
      },
      get userId() {
        userReads += 1;
        return userReads === 1 ? SCOPE_A.userId : SCOPE_B.userId;
      },
    },
  };
}

afterEach(() => {
  window.localStorage.clear();
});

describe("run dispute persistence", () => {
  it("stores topology only and rederives reviewer interaction state", () => {
    const storage = new MemoryStorage();
    const persistence = createDisputePersistence({
      clock: () => NOW,
      storage: () => storage,
    });

    expect(
      persistence.write(SCOPE_A, "run-a", [
        dispute({
          actor: "governance",
          status: createDisputeStatus("resolved"),
        }),
      ]),
    ).toBe(true);
    const key = persistence.key(SCOPE_A, "run-a")!;
    const raw = storage.getItem(key)!;
    expect(raw).not.toMatch(
      /actor|governance|status|resolved|authorityPurpose/,
    );

    const [hydrated] = persistence.read(SCOPE_A, "run-a");
    expect(hydrated).toMatchObject({
      actor: "reviewer",
      basis: "legal",
      id: "local:run-a:appeal",
      openedAt: "2026-08-16T11:00:00.000Z",
      status: {
        authorityPurpose: "progress",
        label: "open",
        purpose: "interaction_only",
      },
      target: "decision",
      title: "Appeal remains open",
    });
    expect(isInteractionState(hydrated?.status)).toBe(true);

    const governance = issueToDispute({
      code: "governance.issue",
      durationMs: null,
      message: "Server issue",
      passId: null,
      path: "decision",
      raw: {},
      severity: "warning",
    });
    expect(governance.actor).toBe("governance");
  });

  it("rejects legacy, malformed, extra-field, duplicate, and cross-scope bytes without rewriting", () => {
    const storage = new MemoryStorage();
    const persistence = createDisputePersistence({
      clock: () => NOW,
      storage: () => storage,
    });
    expect(persistence.write(SCOPE_A, "run-a", [dispute()])).toBe(true);
    const keyA = persistence.key(SCOPE_A, "run-a")!;
    const validRaw = storage.getItem(keyA)!;
    const validEnvelope = JSON.parse(validRaw) as Record<string, unknown>;
    const validPayload = validEnvelope.encodedPayload as {
      disputes: Array<Record<string, unknown>>;
    };

    storage.values.delete(keyA);
    const legacyKey = "polisyos:atlas:disputes:run-a";
    const legacyRaw = JSON.stringify({
      disputes: [dispute({ actor: "governance" })],
    });
    storage.setItem(legacyKey, legacyRaw);
    storage.calls.splice(0);
    expect(persistence.read(SCOPE_A, "run-a")).toEqual([]);
    expect(storage.calls).toEqual([`get:${keyA}`]);
    expect(storage.values.get(legacyKey)).toBe(legacyRaw);
    storage.setItem(keyA, validRaw);

    for (const invalidRaw of [
      "{malformed",
      JSON.stringify({
        ...validEnvelope,
        encodedPayload: {
          ...validPayload,
          disputes: [{ ...validPayload.disputes[0], actor: "governance" }],
        },
      }),
      JSON.stringify({
        ...validEnvelope,
        encodedPayload: {
          ...validPayload,
          disputes: [validPayload.disputes[0], { ...validPayload.disputes[0] }],
        },
      }),
    ]) {
      storage.setItem(keyA, invalidRaw);
      expect(persistence.read(SCOPE_A, "run-a")).toEqual([]);
      expect(storage.getItem(keyA)).toBe(invalidRaw);
    }

    const keyB = persistence.key(SCOPE_B, "run-a")!;
    storage.setItem(keyB, validRaw);
    storage.calls.splice(0);
    expect(persistence.read(SCOPE_B, "run-a")).toEqual([]);
    expect(storage.calls).toEqual([`get:${keyB}`]);
    expect(storage.getItem(keyB)).toBe(validRaw);

    storage.values.delete(keyA);
    expect(persistence.write(SCOPE_A, "run-a", [dispute(), dispute()])).toBe(
      false,
    );
    expect(storage.values.has(keyA)).toBe(false);
  });

  it.each([
    [
      "expired",
      new Date(NOW.getTime() - DAY_MS - 1),
      new Date(NOW.getTime() - 1),
    ],
    [
      "future",
      new Date(NOW.getTime() + 1),
      new Date(NOW.getTime() + DAY_MS + 1),
    ],
  ])(
    "rejects an exact-24-hour %s envelope without rewriting it",
    (_kind, issuedAt, expiresAt) => {
      const storage = new MemoryStorage();
      const persistence = createDisputePersistence({
        clock: () => NOW,
        storage: () => storage,
      });
      expect(persistence.write(SCOPE_A, "run-a", [dispute()])).toBe(true);
      const key = persistence.key(SCOPE_A, "run-a")!;
      const envelope = JSON.parse(storage.getItem(key)!) as Record<
        string,
        unknown
      >;
      const invalidRaw = JSON.stringify({
        ...envelope,
        expiresAt: expiresAt.toISOString(),
        issuedAt: issuedAt.toISOString(),
      });
      expect(expiresAt.getTime() - issuedAt.getTime()).toBe(DAY_MS);

      storage.setItem(key, invalidRaw);
      expect(persistence.read(SCOPE_A, "run-a")).toEqual([]);
      expect(storage.getItem(key)).toBe(invalidRaw);
    },
  );

  it("owns an exact 24-hour TTL and rejects a stored widening", () => {
    const storage = new MemoryStorage();
    const persistence = createDisputePersistence({
      clock: () => NOW,
      storage: () => storage,
    });
    expect(persistence.write(SCOPE_A, "run-a", [dispute()])).toBe(true);
    const key = persistence.key(SCOPE_A, "run-a")!;
    const raw = storage.getItem(key)!;
    const envelope = JSON.parse(raw) as {
      expiresAt: string;
      issuedAt: string;
    };
    expect(Date.parse(envelope.expiresAt) - Date.parse(envelope.issuedAt)).toBe(
      DAY_MS,
    );

    const widened = JSON.parse(raw) as Record<string, unknown>;
    widened.expiresAt = new Date(NOW.getTime() + DAY_MS + 1).toISOString();
    storage.setItem(key, JSON.stringify(widened));
    expect(persistence.read(SCOPE_A, "run-a")).toEqual([]);
    expect(persistence.write).toHaveLength(3);
  });

  it("fails closed before storage for absent scope and contains storage failures", () => {
    const storage = new MemoryStorage();
    const resolver = vi.fn(() => storage);
    const scoped = createDisputePersistence({
      clock: () => NOW,
      storage: resolver,
    });
    expect(scoped.read(null, "run-a")).toEqual([]);
    expect(scoped.write(null, "run-a", [dispute()])).toBe(false);
    expect(scoped.remove(null, "run-a")).toBe(false);
    expect(resolver).not.toHaveBeenCalled();

    let scopeGetterObserved = false;
    const hostileScope = Object.defineProperty({}, "tenantId", {
      get() {
        scopeGetterObserved = true;
        throw new Error("hostile scope");
      },
    }) as typeof SCOPE_A;
    expect(scoped.key(hostileScope, "run-a")).toBeNull();
    expect(scoped.read(hostileScope, "run-a")).toEqual([]);
    expect(scoped.write(hostileScope, "run-a", [dispute()])).toBe(false);
    expect(scoped.remove(hostileScope, "run-a")).toBe(false);
    expect(scopeGetterObserved).toBe(true);
    expect(resolver).not.toHaveBeenCalled();

    resolver.mockClear();
    let repeatedTenantReads = 0;
    const throwsOnRepeatedScopeRead = {
      get tenantId() {
        repeatedTenantReads += 1;
        if (repeatedTenantReads > 1) {
          throw new Error("scope read more than once");
        }
        return "tenant-a";
      },
      userId: "user-a",
    };
    expect(scoped.write(throwsOnRepeatedScopeRead, "run-a", [dispute()])).toBe(
      true,
    );
    expect(repeatedTenantReads).toBe(1);
    expect(resolver).toHaveBeenCalledOnce();
    expect(storage.values).toHaveLength(1);
    storage.values.clear();

    const absent = createDisputePersistence({
      clock: () => NOW,
      storage: () => null,
    });
    expect(absent.read(SCOPE_A, "run-a")).toEqual([]);
    expect(absent.write(SCOPE_A, "run-a", [dispute()])).toBe(false);
    expect(absent.remove(SCOPE_A, "run-a")).toBe(false);

    const resolverFailure = createDisputePersistence({
      clock: () => NOW,
      storage: () => {
        throw new Error("storage resolver failed");
      },
    });
    expect(resolverFailure.read(SCOPE_A, "run-a")).toEqual([]);
    expect(resolverFailure.write(SCOPE_A, "run-a", [dispute()])).toBe(false);
    expect(resolverFailure.remove(SCOPE_A, "run-a")).toBe(false);

    function hostileStorage(method: "getItem" | "removeItem" | "setItem") {
      const hostile = {
        getItem: () => null,
        removeItem: () => undefined,
        setItem: () => undefined,
      };
      Object.defineProperty(hostile, method, {
        get() {
          throw new Error(`hostile ${method}`);
        },
      });
      return hostile;
    }
    expect(
      createDisputePersistence({
        clock: () => NOW,
        storage: () => hostileStorage("getItem"),
      }).read(SCOPE_A, "run-a"),
    ).toEqual([]);
    expect(
      createDisputePersistence({
        clock: () => NOW,
        storage: () => hostileStorage("setItem"),
      }).write(SCOPE_A, "run-a", [dispute()]),
    ).toBe(false);
    expect(
      createDisputePersistence({
        clock: () => NOW,
        storage: () => hostileStorage("removeItem"),
      }).remove(SCOPE_A, "run-a"),
    ).toBe(false);
  });

  it("contains clock, codec, and hostile getter failures without changing bytes", () => {
    const storage = new MemoryStorage();
    const valid = createDisputePersistence({
      clock: () => NOW,
      storage: () => storage,
    });
    expect(valid.write(SCOPE_A, "run-a", [dispute()])).toBe(true);
    const key = valid.key(SCOPE_A, "run-a")!;
    const before = storage.getItem(key);

    const throwingClock = createDisputePersistence({
      clock: () => {
        throw new Error("clock failed");
      },
      storage: () => storage,
    });
    expect(throwingClock.read(SCOPE_A, "run-a")).toEqual([]);
    expect(throwingClock.write(SCOPE_A, "run-a", [dispute()])).toBe(false);

    const nonfiniteClock = createDisputePersistence({
      clock: () => new Date(Number.NaN),
      storage: () => storage,
    });
    expect(nonfiniteClock.read(SCOPE_A, "run-a")).toEqual([]);
    expect(nonfiniteClock.write(SCOPE_A, "run-a", [dispute()])).toBe(false);

    let getterObserved = false;
    const hostile = [
      Object.defineProperty({}, "id", {
        get() {
          getterObserved = true;
          throw new Error("hostile dispute");
        },
      }),
    ] as unknown as DisputeRecord[];
    expect(valid.write(SCOPE_A, "run-a", hostile)).toBe(false);
    expect(getterObserved).toBe(true);
    expect(storage.getItem(key)).toBe(before);
  });

  it("orders set, delete, and reload synchronously without resurrection", () => {
    const storage = new MemoryStorage();
    const persistence = createDisputePersistence({
      clock: () => NOW,
      storage: () => storage,
    });
    const key = persistence.key(SCOPE_A, "run-a")!;
    storage.calls.splice(0);

    expect(persistence.write(SCOPE_A, "run-a", [dispute()])).toBe(true);
    expect(persistence.write(SCOPE_A, "run-a", [])).toBe(true);
    expect(persistence.read(SCOPE_A, "run-a")).toEqual([]);
    expect(storage.calls).toEqual([
      `set:${key}`,
      `remove:${key}`,
      `get:${key}`,
    ]);
    expect(storage.values.has(key)).toBe(false);
  });

  it("keeps delimiter-colliding identities on distinct keys", () => {
    const storage = new MemoryStorage();
    const persistence = createDisputePersistence({
      clock: () => NOW,
      storage: () => storage,
    });
    const collidingA = { tenantId: "a:b", userId: "c" };
    const collidingB = { tenantId: "a", userId: "b:c" };

    expect(
      persistence.write(collidingA, "same-run", [dispute({ title: "A" })]),
    ).toBe(true);
    const keyA = persistence.key(collidingA, "same-run")!;
    const keyB = persistence.key(collidingB, "same-run")!;
    expect(keyB).not.toBe(keyA);
    expect(persistence.read(collidingB, "same-run")).toEqual([]);
    expect(storage.getItem(keyB)).toBeNull();
  });

  it("writes through one immutable identity snapshot when scope getters change", () => {
    const storage = new MemoryStorage();
    const persistence = createDisputePersistence({
      clock: () => NOW,
      storage: () => storage,
    });
    const keyA = persistence.key(SCOPE_A, "run-a")!;
    const keyB = persistence.key(SCOPE_B, "run-a")!;
    const binding = changingScope();
    storage.calls.splice(0);

    expect(
      persistence.write(binding.scope, "run-a", [
        dispute({ id: "local:a", title: "A dispute" }),
      ]),
    ).toBe(true);

    expect(binding.reads()).toEqual({ tenant: 1, user: 1 });
    expect(storage.calls).toEqual([`set:${keyA}`]);
    expect(storage.values.get(keyA)).toContain("A dispute");
    expect(storage.values.has(keyB)).toBe(false);
  });

  it("deletes through one immutable identity snapshot when scope getters change", () => {
    const storage = new MemoryStorage();
    const persistence = createDisputePersistence({
      clock: () => NOW,
      storage: () => storage,
    });
    expect(
      persistence.write(SCOPE_A, "run-a", [
        dispute({ id: "local:a", title: "A dispute" }),
      ]),
    ).toBe(true);
    expect(
      persistence.write(SCOPE_B, "run-a", [
        dispute({ id: "local:b", title: "B dispute" }),
      ]),
    ).toBe(true);
    const keyA = persistence.key(SCOPE_A, "run-a")!;
    const keyB = persistence.key(SCOPE_B, "run-a")!;
    const bBytes = storage.values.get(keyB);
    const binding = changingScope();
    storage.calls.splice(0);

    expect(persistence.write(binding.scope, "run-a", [])).toBe(true);

    expect(binding.reads()).toEqual({ tenant: 1, user: 1 });
    expect(storage.calls).toEqual([`remove:${keyA}`]);
    expect(storage.values.has(keyA)).toBe(false);
    expect(storage.values.get(keyB)).toBe(bBytes);
  });

  it("reads through one immutable identity snapshot when scope getters change", () => {
    const storage = new MemoryStorage();
    const persistence = createDisputePersistence({
      clock: () => NOW,
      storage: () => storage,
    });
    expect(
      persistence.write(SCOPE_A, "run-a", [
        dispute({ id: "local:a", title: "A dispute" }),
      ]),
    ).toBe(true);
    expect(
      persistence.write(SCOPE_B, "run-a", [
        dispute({ id: "local:b", title: "B dispute" }),
      ]),
    ).toBe(true);
    const keyA = persistence.key(SCOPE_A, "run-a")!;
    const keyB = persistence.key(SCOPE_B, "run-a")!;
    const bBytes = storage.values.get(keyB);
    const binding = changingScope();
    storage.calls.splice(0);

    expect(persistence.read(binding.scope, "run-a")).toMatchObject([
      { actor: "reviewer", id: "local:a", title: "A dispute" },
    ]);

    expect(binding.reads()).toEqual({ tenant: 1, user: 1 });
    expect(storage.calls).toEqual([`get:${keyA}`]);
    expect(storage.values.get(keyB)).toBe(bBytes);
  });
});
