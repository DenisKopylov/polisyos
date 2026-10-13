import {
  CONTROL_PRE_ADMISSION_RECOVERY_STORE,
  openOfflineDb,
} from "@/app/offline/db";
import { API_BASE_URL } from "@/shared/lib/constants";
import type { ControlPreAdmissionAttemptResponse } from "./validators";

export type ControlPreAdmissionRecoveryScope = Readonly<{
  tenantId: string;
  cellId: string;
  userId: string;
}>;

export type { ControlPreAdmissionAttemptResponse } from "./validators";

export type ControlPreAdmissionRecoveryRecord = Readonly<{
  scopeKey: string;
  scopeSha256: string;
  bodySha256: string;
  idempotencyKey: string | null;
  attemptId: string | null;
  status: ControlPreAdmissionAttemptResponse["status"] | null;
  runId: string | null;
  jobId: string | null;
  intentSha256: string | null;
  producerEventIds: readonly string[];
  lastSequence: number;
  lastEventId: string | null;
  updatedAt: string | null;
}>;

export type ControlPreAdmissionRecoveryPort = Readonly<{
  read: (scopeKey: string) => Promise<unknown>;
  update: (
    scopeKey: string,
    update: (existing: unknown) => ControlPreAdmissionRecoveryRecord,
  ) => Promise<unknown>;
}>;

export class ControlPreAdmissionRecoveryError extends Error {
  constructor(
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ControlPreAdmissionRecoveryError";
  }
}

type ProducerObservation =
  ControlPreAdmissionAttemptResponse["producer_event_observation"];
type NoCallReason = Exclude<
  ControlPreAdmissionAttemptResponse["producer_no_call_reason"],
  null
>;

const STATUS_VALUES = new Set([
  "started",
  "settled",
  "admitted",
  "refused",
  "cancelled",
  "failed",
]);
const PRODUCER_CALL_STATES = new Set<ProducerObservation>([
  "not_applicable",
  "no_call",
  "complete",
  "unavailable",
]);
const NO_CALL_REASONS = new Set<NoCallReason>([
  "producer_run_binding_not_established",
  "provider_preflight_not_started",
]);
const LEGACY_RECORD_KEYS = [
  "attemptId",
  "bodySha256",
  "idempotencyKey",
  "jobId",
  "lastSequence",
  "producerEventIds",
  "runId",
  "scopeKey",
  "scopeSha256",
  "status",
  "updatedAt",
].sort();
const RECORD_KEYS = [
  ...LEGACY_RECORD_KEYS,
  "intentSha256",
  "lastEventId",
].sort();
const SCOPE_SENTINELS = new Set([
  "anonymous",
  "cell-unknown",
  "none",
  "null",
  "tenant-unknown",
  "unknown",
]);

function requireScope(
  scope: ControlPreAdmissionRecoveryScope | null | undefined,
) {
  if (!scope) {
    throw new ControlPreAdmissionRecoveryError(
      "control_pre_admission_recovery_scope_not_established",
      "Cannot prepare a billable launch until the authenticated user, tenant, and cell are known.",
    );
  }
  const values = [scope.userId, scope.tenantId, scope.cellId];
  if (
    values.some(
      (value) =>
        typeof value !== "string" ||
        value.length === 0 ||
        value !== value.trim() ||
        SCOPE_SENTINELS.has(value.toLowerCase()),
    )
  ) {
    throw new ControlPreAdmissionRecoveryError(
      "control_pre_admission_recovery_scope_not_established",
      "Cannot prepare a billable launch until the authenticated user, tenant, and cell are known.",
    );
  }
  if (typeof window === "undefined") {
    throw new ControlPreAdmissionRecoveryError(
      "control_pre_admission_recovery_browser_unavailable",
      "Durable browser recovery is unavailable; the launch was not sent.",
    );
  }
  const baseUrl = API_BASE_URL || window.location.origin;
  let apiOrigin: string;
  try {
    apiOrigin = new URL(baseUrl, window.location.origin).origin;
  } catch {
    throw new ControlPreAdmissionRecoveryError(
      "control_pre_admission_recovery_api_origin_invalid",
      "The runtime API origin is invalid; the launch was not sent.",
    );
  }
  return {
    userId: scope.userId,
    tenantId: scope.tenantId,
    cellId: scope.cellId,
    apiOrigin,
  };
}

function canonicalJson(value: unknown, inArray = false): string | undefined {
  if (value === null) return "null";
  if (typeof value === "string" || typeof value === "boolean") {
    return JSON.stringify(value);
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      throw new ControlPreAdmissionRecoveryError(
        "control_pre_admission_recovery_intent_invalid",
        "The launch request contains a non-finite number and was not sent.",
      );
    }
    return JSON.stringify(value);
  }
  if (typeof value === "undefined") return inArray ? "null" : undefined;
  if (Array.isArray(value)) {
    return `[${value.map((item) => canonicalJson(item, true) ?? "null").join(",")}]`;
  }
  if (typeof value === "object") {
    const prototype = Object.getPrototypeOf(value);
    if (prototype !== Object.prototype && prototype !== null) {
      throw new ControlPreAdmissionRecoveryError(
        "control_pre_admission_recovery_intent_invalid",
        "The launch request contains a non-JSON value and was not sent.",
      );
    }
    const entries = Object.entries(value as Record<string, unknown>)
      .filter(([, item]) => item !== undefined)
      .sort(([left], [right]) => (left < right ? -1 : left > right ? 1 : 0));
    return `{${entries
      .map(([key, item]) => `${JSON.stringify(key)}:${canonicalJson(item)}`)
      .join(",")}}`;
  }
  throw new ControlPreAdmissionRecoveryError(
    "control_pre_admission_recovery_intent_invalid",
    "The launch request is not JSON-compatible and was not sent.",
  );
}

async function sha256Hex(
  value: string,
  cryptoProvider: Crypto,
): Promise<string> {
  if (!cryptoProvider?.subtle) {
    throw new ControlPreAdmissionRecoveryError(
      "control_pre_admission_recovery_crypto_unavailable",
      "Secure request recovery is unavailable; the launch was not sent.",
    );
  }
  const digest = await cryptoProvider.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(value),
  );
  return Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}

function validateIdempotencyKey(key: string): void {
  if (
    !key ||
    key !== key.trim() ||
    key.length > 128 ||
    /[^\x21-\x7e]/u.test(key)
  ) {
    throw new ControlPreAdmissionRecoveryError(
      "control_pre_admission_recovery_key_invalid",
      "The launch recovery key is invalid; the request was not sent.",
    );
  }
}

function validateRecord(
  value: unknown,
  expectedKey: string,
): ControlPreAdmissionRecoveryRecord {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new ControlPreAdmissionRecoveryError(
      "control_pre_admission_recovery_record_invalid",
      "Stored launch recovery state is malformed; the request was not sent.",
    );
  }
  const raw = value as Record<string, unknown>;
  const keys = Object.keys(raw).sort();
  const legacy = keys.join("\u0000") === LEGACY_RECORD_KEYS.join("\u0000");
  const record: Record<string, unknown> = legacy
    ? { ...raw, intentSha256: null, lastEventId: null }
    : raw;
  if (
    (!legacy && keys.join("\u0000") !== RECORD_KEYS.join("\u0000")) ||
    record.scopeKey !== expectedKey ||
    typeof record.scopeSha256 !== "string" ||
    !/^[a-f0-9]{64}$/.test(record.scopeSha256) ||
    typeof record.bodySha256 !== "string" ||
    !/^[a-f0-9]{64}$/.test(record.bodySha256) ||
    !(
      record.idempotencyKey === null ||
      typeof record.idempotencyKey === "string"
    ) ||
    !(
      record.attemptId === null ||
      (typeof record.attemptId === "string" &&
        /^[a-f0-9]{32}$/.test(record.attemptId))
    ) ||
    !(
      record.status === null ||
      (typeof record.status === "string" && STATUS_VALUES.has(record.status))
    ) ||
    !(record.runId === null || typeof record.runId === "string") ||
    !(record.jobId === null || typeof record.jobId === "string") ||
    !(
      record.intentSha256 === null ||
      (typeof record.intentSha256 === "string" &&
        /^[a-f0-9]{64}$/.test(record.intentSha256))
    ) ||
    !(
      record.lastEventId === null ||
      (typeof record.lastEventId === "string" && record.lastEventId.length > 0)
    ) ||
    !Array.isArray(record.producerEventIds) ||
    record.producerEventIds.some((item) => typeof item !== "string") ||
    !Number.isSafeInteger(record.lastSequence) ||
    (record.lastSequence as number) < 0 ||
    !(record.updatedAt === null || typeof record.updatedAt === "string")
  ) {
    throw new ControlPreAdmissionRecoveryError(
      "control_pre_admission_recovery_record_invalid",
      "Stored launch recovery state is malformed; the request was not sent.",
    );
  }
  if (record.idempotencyKey !== null)
    validateIdempotencyKey(record.idempotencyKey as string);
  return record as unknown as ControlPreAdmissionRecoveryRecord;
}

function validateAttemptEvidence(
  response: ControlPreAdmissionAttemptResponse,
  scope: ControlPreAdmissionRecoveryScope,
): void {
  const binding = response.owner_binding;
  const profile = response.effective_execution_profile;
  const seriousProfile =
    profile === "research" ||
    profile === "governed" ||
    profile === "production";
  if (
    !binding ||
    binding.purpose !== "control.nl_pre_admission.v1" ||
    binding.scope_kind !== "route" ||
    binding.scope_id !== "control.runs.nl" ||
    binding.tenant_id !== scope.tenantId ||
    binding.cell_id !== scope.cellId ||
    !/^[a-f0-9]{64}$/.test(binding.actor_subject_sha256) ||
    binding.run_id !== response.run_id ||
    binding.intent_id !== response.attempt_id ||
    binding.body_sha256 !== response.intent_sha256 ||
    !/^[a-f0-9]{64}$/.test(binding.body_sha256) ||
    !/^sha256:[a-f0-9]{64}$/.test(binding.request_content_sha256) ||
    binding.effective_execution_profile !== profile ||
    !(profile === "dev" || seriousProfile)
  ) {
    throw new ControlPreAdmissionRecoveryError(
      "control_pre_admission_recovery_owner_binding_invalid",
      "The recovered attempt is not bound to this authenticated caller, request owner, and route.",
    );
  }
  const history = response.history;
  if (!Array.isArray(history) || history.length === 0) {
    throw new ControlPreAdmissionRecoveryError(
      "control_pre_admission_recovery_history_invalid",
      "The recovered attempt has no complete status history.",
    );
  }
  const seenEventIds = new Set<string>();
  const allRefs = new Set<string>();
  let previousStatus: string | null = null;
  let aggregateObservation: ProducerObservation = "not_applicable";
  for (let index = 0; index < history.length; index += 1) {
    const event = history[index];
    const observation = event.producer_event_observation;
    const noCallReason = event.producer_no_call_reason;
    if (
      event.sequence !== index + 1 ||
      !event.event_id ||
      seenEventIds.has(event.event_id) ||
      !STATUS_VALUES.has(event.event_type) ||
      !Array.isArray(event.producer_event_ids) ||
      event.producer_event_ids.some(
        (ref) => typeof ref !== "string" || !ref || ref !== ref.trim(),
      ) ||
      !(
        event.failure_code === null ||
        (typeof event.failure_code === "string" &&
          /^[A-Za-z0-9._-]{1,96}$/.test(event.failure_code))
      ) ||
      !(
        event.job_id === null ||
        (typeof event.job_id === "string" &&
          event.job_id.length > 0 &&
          event.job_id === event.job_id.trim())
      ) ||
      !PRODUCER_CALL_STATES.has(observation) ||
      !(
        noCallReason === null ||
        (typeof noCallReason === "string" &&
          NO_CALL_REASONS.has(noCallReason as NoCallReason))
      )
    ) {
      throw new ControlPreAdmissionRecoveryError(
        "control_pre_admission_recovery_history_invalid",
        "The recovered attempt history is malformed or incomplete.",
      );
    }
    if (observation !== "no_call" && noCallReason !== null) {
      throw new ControlPreAdmissionRecoveryError(
        "control_pre_admission_recovery_history_invalid",
        "A no-call reason cannot accompany another producer-call state.",
      );
    }
    seenEventIds.add(event.event_id);
    const eventRefs = [...new Set(event.producer_event_ids)].sort();
    if (
      eventRefs.length !== event.producer_event_ids.length ||
      eventRefs.some((ref, offset) => ref !== event.producer_event_ids[offset])
    ) {
      throw new ControlPreAdmissionRecoveryError(
        "control_pre_admission_recovery_history_invalid",
        "Producer references in the recovered attempt history are not canonical.",
      );
    }
    if ([...allRefs].some((ref) => !event.producer_event_ids.includes(ref))) {
      throw new ControlPreAdmissionRecoveryError(
        "control_pre_admission_recovery_history_invalid",
        "Producer references in the recovered attempt history are not append-only.",
      );
    }
    if (observation === "complete" && event.producer_event_ids.length === 0) {
      throw new ControlPreAdmissionRecoveryError(
        "control_pre_admission_recovery_history_invalid",
        "A complete producer observation must carry event references.",
      );
    }
    if (
      ["not_applicable", "no_call"].includes(observation) &&
      event.producer_event_ids.length > 0
    ) {
      throw new ControlPreAdmissionRecoveryError(
        "control_pre_admission_recovery_history_invalid",
        "A no-call producer observation cannot carry event references.",
      );
    }
    if (
      observation === "no_call" &&
      (event.event_type !== "refused" ||
        previousStatus !== "started" ||
        noCallReason === null ||
        event.failure_code !== noCallReason ||
        aggregateObservation !== "not_applicable")
    ) {
      throw new ControlPreAdmissionRecoveryError(
        "control_pre_admission_recovery_history_invalid",
        "A no-call fact must be a complete pre-provider refusal with its typed reason.",
      );
    }
    if (event.job_id !== null && event.job_id !== response.job_id) {
      throw new ControlPreAdmissionRecoveryError(
        "control_pre_admission_recovery_history_invalid",
        "The recovered status event is not joined to the response job.",
      );
    }
    event.producer_event_ids.forEach((ref) => allRefs.add(ref));
    const expectedObservation: ProducerObservation =
      aggregateObservation === "unavailable" || observation === "unavailable"
        ? "unavailable"
        : aggregateObservation === "complete" || observation === "complete"
          ? "complete"
          : aggregateObservation === "no_call" || observation === "no_call"
            ? "no_call"
            : "not_applicable";
    if (event.producer_event_observation !== expectedObservation) {
      throw new ControlPreAdmissionRecoveryError(
        "control_pre_admission_recovery_history_invalid",
        "Producer observation history is not monotonic.",
      );
    }
    if (
      observation === "unavailable" ||
      aggregateObservation === "unavailable"
    ) {
      aggregateObservation = "unavailable";
    } else if (observation === "complete") {
      aggregateObservation = "complete";
    } else if (observation === "no_call") {
      aggregateObservation = "no_call";
    }
    if (index === 0) {
      if (
        event.event_type !== "started" ||
        event.producer_event_ids.length > 0 ||
        event.producer_event_observation !== "not_applicable" ||
        event.failure_code !== null ||
        event.producer_no_call_reason !== null ||
        event.job_id !== null
      ) {
        throw new ControlPreAdmissionRecoveryError(
          "control_pre_admission_recovery_history_invalid",
          "The recovered attempt history does not begin with an empty start.",
        );
      }
    } else {
      const allowed: Record<string, readonly string[]> = {
        started: ["settled", "refused", "cancelled", "failed"],
        settled: ["admitted", "refused", "cancelled", "failed"],
      };
      const possible: readonly string[] =
        previousStatus === "started" && profile === "dev"
          ? [...allowed.started, "admitted"]
          : (allowed[previousStatus ?? ""] ?? []);
      if (!possible.includes(event.event_type)) {
        throw new ControlPreAdmissionRecoveryError(
          "control_pre_admission_recovery_history_invalid",
          "The recovered attempt contains an invalid status transition.",
        );
      }
      if (
        event.event_type === "settled" &&
        (!seriousProfile ||
          event.producer_event_observation !== "complete" ||
          event.producer_event_ids.length === 0)
      ) {
        throw new ControlPreAdmissionRecoveryError(
          "control_pre_admission_recovery_history_invalid",
          "A settled attempt must carry complete producer event references.",
        );
      }
      if (
        previousStatus === "started" &&
        ["refused", "cancelled", "failed"].includes(event.event_type)
      ) {
        const safeNoCallRefusal =
          event.event_type === "refused" && observation === "no_call";
        const unresolvedProviderCall =
          ["cancelled", "failed"].includes(event.event_type) &&
          observation === "unavailable";
        if (!safeNoCallRefusal && !unresolvedProviderCall) {
          throw new ControlPreAdmissionRecoveryError(
            "control_pre_admission_recovery_history_invalid",
            "A terminal attempt needs settled evidence, a producer-attested no-call refusal, or unresolved state.",
          );
        }
      }
      if (event.event_type === "admitted") {
        if (!event.job_id) {
          throw new ControlPreAdmissionRecoveryError(
            "control_pre_admission_recovery_history_invalid",
            "An admitted attempt must bind its created job.",
          );
        }
        const directDevAdmission =
          previousStatus === "started" &&
          profile === "dev" &&
          observation === "not_applicable" &&
          event.producer_event_ids.length === 0;
        const settledAdmission =
          previousStatus === "settled" &&
          aggregateObservation === "complete" &&
          allRefs.size > 0;
        if (!directDevAdmission && !settledAdmission) {
          throw new ControlPreAdmissionRecoveryError(
            "control_pre_admission_recovery_history_invalid",
            "Admission lacks a matching dev no-preflight or settled producer basis.",
          );
        }
      }
      if (
        event.event_type !== "admitted" &&
        event.event_type !== "settled" &&
        observation === "complete" &&
        event.producer_event_ids.length === 0 &&
        allRefs.size === 0
      ) {
        throw new ControlPreAdmissionRecoveryError(
          "control_pre_admission_recovery_history_invalid",
          "A completed terminal observation must carry producer references.",
        );
      }
    }
    previousStatus = event.event_type;
  }
  const canonicalRefs = [...allRefs].sort();
  if (
    history.at(-1)?.event_type !== response.status ||
    history.at(-1)?.job_id !== response.job_id ||
    response.producer_event_ids.length !== canonicalRefs.length ||
    response.producer_event_ids.some(
      (ref, index) => ref !== canonicalRefs[index],
    ) ||
    response.producer_event_observation !== aggregateObservation ||
    (aggregateObservation === "no_call"
      ? response.producer_no_call_reason !==
          history.at(-1)?.producer_no_call_reason ||
        response.failure_code !== response.producer_no_call_reason
      : response.producer_no_call_reason !== null) ||
    (response.status === "admitted" && !response.job_id)
  ) {
    throw new ControlPreAdmissionRecoveryError(
      "control_pre_admission_recovery_history_invalid",
      "The recovered status and durable history do not agree.",
    );
  }
}

function isResolved(response: ControlPreAdmissionAttemptResponse): boolean {
  const profile = response.effective_execution_profile;
  const observation = String(response.producer_event_observation);
  if (response.status === "admitted") {
    if (!response.job_id) return false;
    if (profile === "dev") {
      return (
        observation === "not_applicable" &&
        response.producer_event_ids.length === 0
      );
    }
    return observation === "complete" && response.producer_event_ids.length > 0;
  }
  if (
    response.status === "refused" ||
    response.status === "cancelled" ||
    response.status === "failed"
  ) {
    if (observation === "unavailable") return false;
    if (response.status === "refused" && observation === "no_call") {
      return (
        response.producer_event_ids.length === 0 &&
        response.producer_no_call_reason !== null &&
        NO_CALL_REASONS.has(response.producer_no_call_reason)
      );
    }
    return observation === "complete" && response.producer_event_ids.length > 0;
  }
  return false;
}

function indexedDbPort(): ControlPreAdmissionRecoveryPort {
  return {
    read: async (scopeKey) => {
      const database = await openOfflineDb();
      return database.get(CONTROL_PRE_ADMISSION_RECOVERY_STORE, scopeKey);
    },
    update: async (scopeKey, update) => {
      const database = await openOfflineDb();
      const transaction = database.transaction(
        CONTROL_PRE_ADMISSION_RECOVERY_STORE,
        "readwrite",
      );
      try {
        const existing = await transaction.store.get(scopeKey);
        const next = update(existing);
        await transaction.store.put(next);
        await transaction.done;
        return next;
      } catch (error) {
        transaction.abort();
        throw error;
      }
    },
  };
}

export function createControlPreAdmissionRecoveryRepository(
  port: ControlPreAdmissionRecoveryPort = indexedDbPort(),
  cryptoProvider: Crypto = globalThis.crypto,
) {
  async function identity(
    scope: ControlPreAdmissionRecoveryScope | null | undefined,
  ) {
    const normalized = requireScope(scope);
    const scopeSha256 = await sha256Hex(
      canonicalJson(normalized)!,
      cryptoProvider,
    );
    return { scopeKey: scopeSha256, scopeSha256 };
  }

  return {
    async read(scope: ControlPreAdmissionRecoveryScope | null | undefined) {
      const { scopeKey, scopeSha256 } = await identity(scope);
      const value = await port.read(scopeKey);
      if (value === undefined) return null;
      const record = validateRecord(value, scopeKey);
      if (record.scopeSha256 !== scopeSha256) {
        throw new ControlPreAdmissionRecoveryError(
          "control_pre_admission_recovery_scope_collision",
          "Stored recovery state does not match the authenticated caller scope.",
        );
      }
      return record;
    },

    async claim(
      scope: ControlPreAdmissionRecoveryScope | null | undefined,
      request: unknown,
      requestedKey?: string,
    ) {
      const { scopeKey, scopeSha256 } = await identity(scope);
      const requestJson = canonicalJson(request);
      if (requestJson === undefined) {
        throw new ControlPreAdmissionRecoveryError(
          "control_pre_admission_recovery_intent_invalid",
          "The launch request is absent and was not sent.",
        );
      }
      const bodySha256 = await sha256Hex(requestJson, cryptoProvider);
      const candidateKey = requestedKey ?? cryptoProvider.randomUUID();
      validateIdempotencyKey(candidateKey);
      const value = await port.update(scopeKey, (existing) => {
        if (existing !== undefined) {
          const record = validateRecord(existing, scopeKey);
          if (record.scopeSha256 !== scopeSha256) {
            throw new ControlPreAdmissionRecoveryError(
              "control_pre_admission_recovery_scope_collision",
              "Stored recovery state does not match the authenticated caller scope.",
            );
          }
          if (
            record.idempotencyKey === null &&
            record.attemptId !== null &&
            record.intentSha256 === null
          ) {
            throw new ControlPreAdmissionRecoveryError(
              "control_pre_admission_recovery_legacy_attempt_unverified",
              "A prior stored attempt has no verified owner binding; recover its status before launching again.",
            );
          }
          if (record.idempotencyKey !== null) {
            if (record.bodySha256 !== bodySha256) {
              throw new ControlPreAdmissionRecoveryError(
                "control_pre_admission_recovery_intent_unresolved",
                "A prior launch is still unresolved. Restore and retry that exact request before starting a different launch.",
              );
            }
            if (requestedKey && requestedKey !== record.idempotencyKey) {
              throw new ControlPreAdmissionRecoveryError(
                "control_pre_admission_recovery_key_conflict",
                "The supplied key differs from the unresolved launch key; the request was not sent.",
              );
            }
            return record;
          }
        }
        return {
          scopeKey,
          scopeSha256,
          bodySha256,
          idempotencyKey: candidateKey,
          attemptId: null,
          status: null,
          runId: null,
          jobId: null,
          intentSha256: null,
          producerEventIds: [],
          lastSequence: 0,
          lastEventId: null,
          updatedAt: null,
        } satisfies ControlPreAdmissionRecoveryRecord;
      });
      return validateRecord(value, scopeKey);
    },

    async releaseKnownNoAttempt(
      scope: ControlPreAdmissionRecoveryScope | null | undefined,
      request: unknown,
      idempotencyKey: string,
    ) {
      const { scopeKey, scopeSha256 } = await identity(scope);
      const requestJson = canonicalJson(request);
      if (requestJson === undefined) return false;
      const bodySha256 = await sha256Hex(requestJson, cryptoProvider);
      validateIdempotencyKey(idempotencyKey);
      let released = false;
      const value = await port.update(scopeKey, (existing) => {
        if (existing === undefined) {
          throw new ControlPreAdmissionRecoveryError(
            "control_pre_admission_recovery_record_missing",
            "The no-attempt response has no matching local launch claim.",
          );
        }
        const record = validateRecord(existing, scopeKey);
        if (record.scopeSha256 !== scopeSha256) {
          throw new ControlPreAdmissionRecoveryError(
            "control_pre_admission_recovery_scope_collision",
            "Stored recovery state does not match the authenticated caller scope.",
          );
        }
        if (
          record.idempotencyKey !== idempotencyKey ||
          record.bodySha256 !== bodySha256 ||
          record.attemptId !== null ||
          record.status !== null
        ) {
          return record;
        }
        released = true;
        return { ...record, idempotencyKey: null };
      });
      validateRecord(value, scopeKey);
      return released;
    },

    async rememberAttemptId(
      scope: ControlPreAdmissionRecoveryScope | null | undefined,
      attemptId: string,
    ) {
      if (!/^[a-f0-9]{32}$/.test(attemptId)) {
        throw new ControlPreAdmissionRecoveryError(
          "control_pre_admission_recovery_attempt_id_invalid",
          "The server returned an invalid attempt identifier.",
        );
      }
      const { scopeKey, scopeSha256 } = await identity(scope);
      const value = await port.update(scopeKey, (existing) => {
        if (existing === undefined) {
          throw new ControlPreAdmissionRecoveryError(
            "control_pre_admission_recovery_record_missing",
            "The launch key is missing; no new request was sent.",
          );
        }
        const record = validateRecord(existing, scopeKey);
        if (record.scopeSha256 !== scopeSha256) {
          throw new ControlPreAdmissionRecoveryError(
            "control_pre_admission_recovery_scope_collision",
            "Stored recovery state does not match the authenticated caller scope.",
          );
        }
        if (record.attemptId !== null && record.attemptId !== attemptId) {
          throw new ControlPreAdmissionRecoveryError(
            "control_pre_admission_recovery_attempt_conflict",
            "The server returned a different attempt for the unresolved launch key.",
          );
        }
        return { ...record, attemptId };
      });
      return validateRecord(value, scopeKey);
    },

    async observe(
      scope: ControlPreAdmissionRecoveryScope | null | undefined,
      response: ControlPreAdmissionAttemptResponse,
    ) {
      const { scopeKey, scopeSha256 } = await identity(scope);
      if (!/^[a-f0-9]{32}$/.test(response.attempt_id)) {
        throw new ControlPreAdmissionRecoveryError(
          "control_pre_admission_recovery_attempt_id_invalid",
          "The server returned an invalid attempt identifier.",
        );
      }
      const scoped = requireScope(scope);
      const actorSubjectSha256 = await sha256Hex(scoped.userId, cryptoProvider);
      validateAttemptEvidence(response, scoped);
      if (response.owner_binding.actor_subject_sha256 !== actorSubjectSha256) {
        throw new ControlPreAdmissionRecoveryError(
          "control_pre_admission_recovery_owner_binding_invalid",
          "The recovered attempt belongs to a different authenticated principal.",
        );
      }
      const lastSequence = response.history.at(-1)?.sequence ?? 0;
      const lastEventId = response.history.at(-1)?.event_id ?? null;
      const value = await port.update(scopeKey, (existing) => {
        if (existing === undefined) {
          throw new ControlPreAdmissionRecoveryError(
            "control_pre_admission_recovery_record_missing",
            "The launch key is missing; status was not attached to another request.",
          );
        }
        const record = validateRecord(existing, scopeKey);
        if (record.scopeSha256 !== scopeSha256) {
          throw new ControlPreAdmissionRecoveryError(
            "control_pre_admission_recovery_scope_collision",
            "Stored recovery state does not match the authenticated caller scope.",
          );
        }
        if (
          record.attemptId !== null &&
          record.attemptId !== response.attempt_id
        ) {
          throw new ControlPreAdmissionRecoveryError(
            "control_pre_admission_recovery_attempt_conflict",
            "The server returned a different attempt for the unresolved launch key.",
          );
        }
        if (
          record.intentSha256 !== null &&
          record.intentSha256 !== response.intent_sha256
        ) {
          throw new ControlPreAdmissionRecoveryError(
            "control_pre_admission_recovery_intent_conflict",
            "The server returned a different immutable request owner.",
          );
        }
        if (record.runId !== null && record.runId !== response.run_id) {
          throw new ControlPreAdmissionRecoveryError(
            "control_pre_admission_recovery_run_conflict",
            "The server changed the run bound to this launch key.",
          );
        }
        if (lastSequence < record.lastSequence) return record;
        if (record.jobId !== null && record.jobId !== response.job_id) {
          throw new ControlPreAdmissionRecoveryError(
            "control_pre_admission_recovery_job_conflict",
            "The server changed the job bound to this launch key.",
          );
        }
        if (
          lastSequence === record.lastSequence &&
          record.lastEventId !== null &&
          record.lastEventId !== lastEventId
        ) {
          throw new ControlPreAdmissionRecoveryError(
            "control_pre_admission_recovery_history_conflict",
            "The server changed an already observed status event.",
          );
        }
        if (
          lastSequence > record.lastSequence &&
          record.lastEventId !== null &&
          response.history[record.lastSequence - 1]?.event_id !==
            record.lastEventId
        ) {
          throw new ControlPreAdmissionRecoveryError(
            "control_pre_admission_recovery_history_conflict",
            "The server history does not extend the previously observed event stream.",
          );
        }
        return {
          ...record,
          idempotencyKey: isResolved(response) ? null : record.idempotencyKey,
          attemptId: response.attempt_id,
          status: response.status,
          runId: response.run_id,
          jobId: response.job_id,
          intentSha256: response.intent_sha256,
          producerEventIds: [...new Set(response.producer_event_ids)].sort(),
          lastSequence,
          lastEventId,
          updatedAt: response.updated_at,
        };
      });
      return validateRecord(value, scopeKey);
    },
  };
}

export const controlPreAdmissionRecoveryRepository =
  createControlPreAdmissionRecoveryRepository();
