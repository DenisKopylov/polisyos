import type { GovernanceIssueView } from "@/shared/lib/domain/governance";
import {
  createAuthorityLocalStateEnvelopeFamily,
  type AuthorityLocalScope,
} from "@/app/offline/authorityLocalState";
import {
  createInteractionState,
  type InteractionState,
} from "@/shared/lib/domain/statusOwnership";

export type DisputeRecord = {
  actor: "governance" | "reviewer";
  authorityPurpose: "governance_projection" | "case_management_note";
  basis: string;
  id: string;
  openedAt: string;
  status: InteractionState;
  target: string;
  title: string;
};

type StoredDisputeRecord = Readonly<{
  basis: string;
  id: string;
  openedAt: string;
  target: string;
  title: string;
}>;

type StoredDisputes = Readonly<{
  disputes: StoredDisputeRecord[];
}>;

type DisputeStorage = Readonly<{
  getItem: (key: string) => string | null;
  removeItem: (key: string) => void;
  setItem: (key: string, value: string) => void;
}>;

const DISPUTE_FAMILY = "run-disputes" as const;
const DISPUTE_TTL_MS = 24 * 60 * 60 * 1_000;

export function issueToDispute(issue: GovernanceIssueView): DisputeRecord {
  const raw = issue.raw ?? {};
  const openedAt =
    typeof raw.timestamp === "string"
      ? raw.timestamp
      : typeof raw.created_at === "string"
        ? raw.created_at
        : "1970-01-01T00:00:00.000Z";
  return {
    actor: "governance",
    authorityPurpose: "governance_projection",
    basis: issue.passId ?? issue.code,
    id: `issue:${issue.code}`,
    openedAt,
    status: createDisputeStatus("under_review"),
    target: issue.path ?? issue.passId ?? "decision",
    title: issue.message,
  };
}

export function createDisputeStatus(value: unknown): InteractionState {
  const label =
    typeof value === "string"
      ? value
      : typeof value === "object" &&
          value !== null &&
          "label" in value &&
          typeof value.label === "string"
        ? value.label
        : null;
  if (label !== "open" && label !== "under_review" && label !== "resolved") {
    throw new TypeError("run dispute interaction state is unrecognized");
  }
  return createInteractionState(label, "progress");
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function hasExactKeys(value: Record<string, unknown>, expected: string[]) {
  const actual = Object.keys(value).sort();
  const sortedExpected = [...expected].sort();
  return (
    actual.length === sortedExpected.length &&
    actual.every((key, index) => key === sortedExpected[index])
  );
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isCanonicalTimestamp(value: unknown): value is string {
  if (typeof value !== "string") {
    return false;
  }
  const milliseconds = Date.parse(value);
  return (
    Number.isFinite(milliseconds) &&
    new Date(milliseconds).toISOString() === value
  );
}

function parseStoredDispute(value: unknown): StoredDisputeRecord | null {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ["basis", "id", "openedAt", "target", "title"]) ||
    !isNonEmptyString(value.basis) ||
    !isNonEmptyString(value.id) ||
    !isCanonicalTimestamp(value.openedAt) ||
    !isNonEmptyString(value.target) ||
    !isNonEmptyString(value.title)
  ) {
    return null;
  }
  return {
    basis: value.basis,
    id: value.id,
    openedAt: value.openedAt,
    target: value.target,
    title: value.title,
  };
}

function parseStoredDisputes(value: unknown): StoredDisputes | null {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ["disputes"]) ||
    !Array.isArray(value.disputes)
  ) {
    return null;
  }
  const disputes: StoredDisputeRecord[] = [];
  const ids = new Set<string>();
  for (const candidate of value.disputes) {
    const dispute = parseStoredDispute(candidate);
    if (!dispute || ids.has(dispute.id)) {
      return null;
    }
    ids.add(dispute.id);
    disputes.push(dispute);
  }
  return { disputes };
}

function encodeStoredDisputes(
  disputes: DisputeRecord[],
): StoredDisputes | null {
  if (!Array.isArray(disputes)) {
    return null;
  }
  return parseStoredDisputes({
    disputes: disputes.map(({ basis, id, openedAt, target, title }) => ({
      basis,
      id,
      openedAt,
      target,
      title,
    })),
  });
}

function decodeStoredDisputes(value: unknown): DisputeRecord[] | null {
  const stored = parseStoredDisputes(value);
  if (!stored) {
    return null;
  }
  return stored.disputes.map((dispute) => ({
    ...dispute,
    actor: "reviewer",
    authorityPurpose: "case_management_note",
    status: createDisputeStatus("open"),
  }));
}

function browserDisputeStorage(): DisputeStorage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function createDisputePersistence(config?: {
  clock?: () => Date;
  storage?: () => DisputeStorage | null;
}) {
  const owner = createAuthorityLocalStateEnvelopeFamily({
    clock: config?.clock ?? (() => new Date()),
    codec: {
      decode: decodeStoredDisputes,
      encode: encodeStoredDisputes,
    },
    family: DISPUTE_FAMILY,
    ttlMs: DISPUTE_TTL_MS,
    version: 1,
  });
  const storageResolver = config?.storage ?? browserDisputeStorage;

  function resolveStorage(): DisputeStorage | null {
    try {
      return storageResolver();
    } catch {
      return null;
    }
  }

  type DisputeBinding = Readonly<{
    scope: AuthorityLocalScope;
    slot: string;
  }>;

  function snapshotBinding(
    scope: AuthorityLocalScope | null | undefined,
    runId: string,
  ): DisputeBinding | null {
    try {
      if (!scope) {
        return null;
      }
      const tenantId = scope.tenantId;
      const userId = scope.userId;
      const slot = runId;
      return Object.freeze({
        scope: Object.freeze({ tenantId, userId }),
        slot,
      });
    } catch {
      return null;
    }
  }

  function keyForBinding(binding: DisputeBinding) {
    try {
      return owner.key({ scope: binding.scope, slot: binding.slot });
    } catch {
      return null;
    }
  }

  function key(scope: AuthorityLocalScope | null | undefined, runId: string) {
    const binding = snapshotBinding(scope, runId);
    return binding ? keyForBinding(binding) : null;
  }

  function read(
    scope: AuthorityLocalScope | null | undefined,
    runId: string,
  ): DisputeRecord[] {
    const binding = snapshotBinding(scope, runId);
    if (!binding) {
      return [];
    }
    const physicalKey = keyForBinding(binding);
    if (!physicalKey) {
      return [];
    }

    try {
      const raw = resolveStorage()?.getItem(physicalKey);
      if (!raw) {
        return [];
      }
      return owner.decode({
        envelope: JSON.parse(raw) as unknown,
        fallback: [],
        scope: binding.scope,
        slot: binding.slot,
      });
    } catch {
      return [];
    }
  }

  function removeBinding(binding: DisputeBinding): boolean {
    const physicalKey = keyForBinding(binding);
    if (!physicalKey) {
      return false;
    }
    try {
      const storage = resolveStorage();
      if (!storage) {
        return false;
      }
      storage.removeItem(physicalKey);
      return true;
    } catch {
      return false;
    }
  }

  function remove(
    scope: AuthorityLocalScope | null | undefined,
    runId: string,
  ): boolean {
    const binding = snapshotBinding(scope, runId);
    return binding ? removeBinding(binding) : false;
  }

  function write(
    scope: AuthorityLocalScope | null | undefined,
    runId: string,
    disputes: DisputeRecord[],
  ): boolean {
    const binding = snapshotBinding(scope, runId);
    if (!binding) {
      return false;
    }
    try {
      if (!Array.isArray(disputes)) {
        return false;
      }
      if (disputes.length === 0) {
        return removeBinding(binding);
      }
    } catch {
      return false;
    }
    const issued = (() => {
      try {
        return owner.encode({
          scope: binding.scope,
          slot: binding.slot,
          value: disputes,
        });
      } catch {
        return null;
      }
    })();
    if (!issued) {
      return false;
    }
    try {
      const storage = resolveStorage();
      if (!storage) {
        return false;
      }
      storage.setItem(issued.key, JSON.stringify(issued.envelope));
      return true;
    } catch {
      return false;
    }
  }

  return Object.freeze({ key, read, remove, write });
}

const disputePersistence = createDisputePersistence();

export function readStoredDisputes(
  scope: AuthorityLocalScope | null | undefined,
  runId: string,
) {
  return disputePersistence.read(scope, runId);
}

export function writeStoredDisputes(
  scope: AuthorityLocalScope | null | undefined,
  runId: string,
  disputes: DisputeRecord[],
) {
  return disputePersistence.write(scope, runId, disputes);
}

export function buildDisputeRecords(
  issues: GovernanceIssueView[],
  localDisputes: DisputeRecord[],
) {
  return [
    ...localDisputes.map((dispute) => ({
      ...dispute,
      actor: "reviewer" as const,
      authorityPurpose: "case_management_note" as const,
    })),
    ...issues.map(issueToDispute),
  ];
}
