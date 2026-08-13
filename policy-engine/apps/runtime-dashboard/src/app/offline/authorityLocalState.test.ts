import {
  createAuthorityLocalStateFamily,
  type AuthorityLocalStateCodec,
} from "./authorityLocalState";

type StoredValue = {
  label: string;
  revision: number;
};

const FAMILY_NAMES = [
  "operator-craft.threshold",
  "operator-craft.annotations",
  "operator-craft.evidence-wallet",
  "operator-craft.onboarding",
] as const;

type OperatorCraftFamily = (typeof FAMILY_NAMES)[number];

const scope = {
  tenantId: "tenant-a",
  userId: "reviewer-a",
};

const codec: AuthorityLocalStateCodec<StoredValue> = {
  decode(value) {
    if (
      !value ||
      typeof value !== "object" ||
      Array.isArray(value)
    ) {
      return null;
    }
    const candidate = value as Partial<StoredValue>;
    if (
      typeof candidate.label !== "string" ||
      typeof candidate.revision !== "number" ||
      Object.keys(value).length !== 2
    ) {
      return null;
    }
    return { label: candidate.label, revision: candidate.revision };
  },
  encode(value) {
    return { label: value.label, revision: value.revision };
  },
};

function makeFamily(
  family: OperatorCraftFamily,
  now: () => Date,
  storage: () => Storage | null = () => window.localStorage,
) {
  return createAuthorityLocalStateFamily({
    clock: now,
    codec,
    family,
    storage,
    ttlMs: 1_000,
    version: 1,
  });
}

describe("authority local state", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("binds the physical key and strict envelope to the verified scope and logical slot", () => {
    const family = makeFamily("operator-craft.threshold", () => new Date("2026-08-13T10:00:00.000Z"));
    const value = { label: "threshold", revision: 1 };

    expect(family.write({ scope, slot: "profile", value })).toBe(true);

    const key = family.key({ scope, slot: "profile" });
    const raw = window.localStorage.getItem(key!);
    expect(key).toContain("operator-craft.threshold");
    expect(key).toContain("tenant-a");
    expect(key).toContain("reviewer-a");
    expect(key).toContain("profile");
    expect(JSON.parse(raw!)).toEqual({
      encodedPayload: value,
      expiresAt: "2026-08-13T10:00:01.000Z",
      family: "operator-craft.threshold",
      issuedAt: "2026-08-13T10:00:00.000Z",
      slot: "profile",
      tenantId: "tenant-a",
      userId: "reviewer-a",
      version: 1,
    });

    const hydrated = family.read({
      fallback: { label: "fallback", revision: 0 },
      scope,
      slot: "profile",
    });
    expect(hydrated).toEqual(value);
    expect(Object.isFrozen(hydrated)).toBe(true);
  });

  it("fails closed for invalid, expired, copied, foreign, and runtime-novel envelopes across every operator family", () => {
    const now = () => new Date("2026-08-13T10:00:00.000Z");
    const families = FAMILY_NAMES;
    const fallback = { label: "fallback", revision: 0 };

    for (const familyName of families) {
      const family = makeFamily(familyName, now);
      const key = family.key({ scope, slot: "run-36" });
      expect(key).not.toBeNull();
      const valid = {
        encodedPayload: { label: familyName, revision: 1 },
        expiresAt: "2026-08-13T10:00:01.000Z",
        family: familyName,
        issuedAt: "2026-08-13T10:00:00.000Z",
        slot: "run-36",
        tenantId: "tenant-a",
        userId: "reviewer-a",
        version: 1,
      };
      const cases: Array<[string, unknown]> = [
        ["legacy payload", valid.encodedPayload],
        ["malformed JSON", "{"],
        ["expired envelope", { ...valid, expiresAt: "2026-08-13T09:59:59.999Z" }],
        ["prior tenant", { ...valid, tenantId: "tenant-prior" }],
        ["prior user", { ...valid, userId: "reviewer-prior" }],
        ["copied slot", { ...valid, slot: "run-37" }],
        [
          "other known family",
          {
            ...valid,
            family:
              familyName === "operator-craft.threshold"
                ? "operator-craft.annotations"
                : "operator-craft.threshold",
          },
        ],
        ["runtime novel family", { ...valid, family: "operator-craft.runtime-novel" }],
        ["extra envelope field", { ...valid, extra: true }],
      ];

      for (const [label, raw] of cases) {
        window.localStorage.setItem(key!, typeof raw === "string" ? raw : JSON.stringify(raw));
        expect(
          family.read({ fallback, scope, slot: "run-36" }),
          `${familyName}: ${label}`,
        ).toEqual(fallback);
        expect(window.localStorage.getItem(key!)).toBe(
          typeof raw === "string" ? raw : JSON.stringify(raw),
        );
      }
    }
  });

  it("uses the owner clock and fixed TTL, never writes without complete scope, and leaves preferences alone", () => {
    let instant = "2026-08-13T10:00:00.000Z";
    const family = makeFamily("operator-craft.onboarding", () => new Date(instant));
    const key = family.key({ scope, slot: "run-36" });
    const fallback = { label: "fallback", revision: 0 };
    window.localStorage.setItem("polisyos.runtime.theme", "dark");

    expect(
      family.write({
        scope: { tenantId: "", userId: scope.userId },
        slot: "run-36",
        value: { label: "not-written", revision: 1 },
      }),
    ).toBe(false);
    expect(window.localStorage.getItem(key!)).toBeNull();

    expect(family.write({ scope, slot: "run-36", value: { label: "saved", revision: 1 } })).toBe(true);
    instant = "2026-08-13T10:00:01.000Z";
    expect(family.read({ fallback, scope, slot: "run-36" })).toEqual(fallback);
    expect(window.localStorage.getItem("polisyos.runtime.theme")).toBe("dark");
  });

  it("fails closed when its storage dependency is unavailable", () => {
    const family = makeFamily(
      "operator-craft.threshold",
      () => new Date("2026-08-13T10:00:00.000Z"),
      () => null,
    );

    expect(
      family.write({
        scope,
        slot: "profile",
        value: { label: "threshold", revision: 1 },
      }),
    ).toBe(false);
    expect(window.localStorage.length).toBe(0);
  });

  it("rejects tampered writer time and fails closed on clock or codec faults", () => {
    const now = () => new Date("2026-08-13T10:00:00.000Z");
    const family = makeFamily("operator-craft.threshold", now);
    const key = family.key({ scope, slot: "profile" });
    const fallback = { label: "fallback", revision: 0 };
    const valid = {
      encodedPayload: { label: "threshold", revision: 1 },
      expiresAt: "2026-08-13T10:00:01.000Z",
      family: "operator-craft.threshold",
      issuedAt: "2026-08-13T10:00:00.000Z",
      slot: "profile",
      tenantId: "tenant-a",
      userId: "reviewer-a",
      version: 1,
    };

    for (const tampered of [
      { ...valid, expiresAt: "2026-08-13T10:00:02.000Z" },
      {
        ...valid,
        issuedAt: "2026-08-13T10:00:01.000Z",
        expiresAt: "2026-08-13T10:00:02.000Z",
      },
    ]) {
      window.localStorage.setItem(key!, JSON.stringify(tampered));
      expect(family.read({ fallback, scope, slot: "profile" })).toEqual(fallback);
    }

    const throwingClock = makeFamily(
      "operator-craft.threshold",
      () => {
        throw new Error("clock unavailable");
      },
    );
    expect(
      throwingClock.read({ fallback, scope, slot: "profile" }),
    ).toEqual(fallback);
    expect(
      throwingClock.write({
        scope,
        slot: "profile",
        value: { label: "threshold", revision: 1 },
      }),
    ).toBe(false);

    const throwingCodec: AuthorityLocalStateCodec<StoredValue> = {
      decode() {
        throw new Error("decode unavailable");
      },
      encode() {
        throw new Error("encode unavailable");
      },
    };
    const codecFamily = createAuthorityLocalStateFamily({
      clock: now,
      codec: throwingCodec,
      family: "operator-craft.threshold" as const,
      storage: () => window.localStorage,
      ttlMs: 1_000,
      version: 1,
    });
    window.localStorage.setItem(key!, JSON.stringify(valid));
    expect(codecFamily.read({ fallback, scope, slot: "profile" })).toEqual(
      fallback,
    );
    expect(
      codecFamily.write({
        scope,
        slot: "profile",
        value: { label: "threshold", revision: 1 },
      }),
    ).toBe(false);
    expect(window.localStorage.getItem(key!)).toBe(JSON.stringify(valid));
  });

  it("accepts reordered fields because field content, not JSON formatting, establishes identity", () => {
    const family = makeFamily("operator-craft.evidence-wallet", () => new Date("2026-08-13T10:00:00.000Z"));
    const key = family.key({ scope, slot: "wallet" });
    window.localStorage.setItem(
      key!,
      '{"version":1,"userId":"reviewer-a","tenantId":"tenant-a","slot":"wallet","issuedAt":"2026-08-13T10:00:00.000Z","family":"operator-craft.evidence-wallet","expiresAt":"2026-08-13T10:00:01.000Z","encodedPayload":{"revision":1,"label":"wallet"}}',
    );

    expect(
      family.read({
        fallback: { label: "fallback", revision: 0 },
        scope,
        slot: "wallet",
      }),
    ).toEqual({ label: "wallet", revision: 1 });
  });
});
