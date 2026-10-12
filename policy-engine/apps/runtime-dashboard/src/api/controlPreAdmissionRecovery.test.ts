import {
  ControlPreAdmissionRecoveryError,
  createControlPreAdmissionRecoveryRepository,
  type ControlPreAdmissionRecoveryPort,
  type ControlPreAdmissionRecoveryScope,
} from "./controlPreAdmissionRecovery";
import type { components } from "./types";

const scope: ControlPreAdmissionRecoveryScope = {
  tenantId: "tenant-a",
  cellId: "cell-a",
  userId: "principal-a",
};
const request = {
  nl_request: "Assess the policy",
  execution_profile: "research",
};

function memoryPort(): ControlPreAdmissionRecoveryPort & {
  records: Map<string, unknown>;
} {
  const records = new Map<string, unknown>();
  return {
    records,
    read: async (key) => records.get(key),
    update: async (key, update) => {
      const value = update(records.get(key));
      records.set(key, value);
      return value;
    },
  };
}

function response(
  status: components["schemas"]["ControlPreAdmissionAttemptResponse"]["status"],
  jobId: string | null = null,
  profile: "dev" | "research" | "governed" | "production" = "research",
  terminalObservation:
    | "complete"
    | "unavailable"
    | "not_applicable"
    | "no_call" = "complete",
): components["schemas"]["ControlPreAdmissionAttemptResponse"] {
  const timestamp = "2026-10-12T10:00:00Z";
  const serious = profile !== "dev";
  const statuses =
    status === "started"
      ? ["started"]
      : status === "settled"
        ? ["started", "settled"]
        : status === "admitted"
          ? serious
            ? ["started", "settled", "admitted"]
            : ["started", "admitted"]
          : terminalObservation === "complete" && serious
            ? ["started", "settled", status]
            : ["started", status];
  const events = statuses.map((eventType, index) => {
    const hasSettlement =
      statuses.includes("settled") && index >= statuses.indexOf("settled");
    const isTerminal =
      index === statuses.length - 1 &&
      ["refused", "cancelled", "failed"].includes(eventType);
    const observation = hasSettlement
      ? "complete"
      : isTerminal
        ? terminalObservation
        : "not_applicable";
    const refs = observation === "complete" ? ["producer-event-a"] : [];
    return {
      event_id: `event-${eventType}-${index + 1}`,
      sequence: index + 1,
      event_type: eventType,
      observed_at: timestamp,
      producer_event_ids: refs,
      producer_event_observation:
        observation as components["schemas"]["ControlPreAdmissionAttemptResponse"]["producer_event_observation"],
      producer_no_call_reason:
        observation === "no_call" ? "provider_preflight_not_started" : null,
      failure_code: isTerminal
        ? observation === "no_call"
          ? "provider_preflight_not_started"
          : `provider_${eventType}`
        : null,
      job_id: index === statuses.length - 1 ? jobId : null,
    };
  });
  const aggregateObservation = events.some(
    (event) => event.producer_event_observation === "unavailable",
  )
    ? "unavailable"
    : events.some((event) => event.producer_event_observation === "complete")
      ? "complete"
      : events.some(
            (event) => String(event.producer_event_observation) === "no_call",
          )
        ? ("no_call" as components["schemas"]["ControlPreAdmissionAttemptResponse"]["producer_event_observation"])
        : "not_applicable";
  return {
    meta: {
      generated_at: timestamp,
      request_id: "request-a",
      source_kinds: [],
    },
    owner_binding: {
      purpose: "control.nl_pre_admission.v1",
      scope_kind: "route",
      scope_id: "control.runs.nl",
      tenant_id: scope.tenantId,
      cell_id: scope.cellId,
      actor_subject_sha256:
        "d864423f4b34667b61e3d3aa7ad3748a3fb9ebf260012e2a87b796ce9b458f8e",
      run_id: "run-a",
      intent_id: "a".repeat(32),
      body_sha256: "b".repeat(64),
      request_content_sha256: `sha256:${"c".repeat(64)}`,
      effective_execution_profile: profile,
    },
    attempt_id: "a".repeat(32),
    intent_sha256: "b".repeat(64),
    status,
    run_id: "run-a",
    job_id: jobId,
    effective_execution_profile: profile,
    producer_event_ids:
      aggregateObservation === "complete" ? ["producer-event-a"] : [],
    producer_event_observation: aggregateObservation,
    producer_no_call_reason:
      aggregateObservation === "no_call"
        ? "provider_preflight_not_started"
        : null,
    failure_code:
      aggregateObservation === "no_call"
        ? "provider_preflight_not_started"
        : null,
    created_at: timestamp,
    updated_at: timestamp,
    history: events,
  };
}

describe("control pre-admission recovery repository", () => {
  it("reuses the exact key across repository instances without persisting body or credentials", async () => {
    const port = memoryPort();
    const first = createControlPreAdmissionRecoveryRepository(port);
    const firstRecord = await first.claim(scope, request);
    const remounted = createControlPreAdmissionRecoveryRepository(port);
    const retry = await remounted.claim(scope, request);
    const reordered = await remounted.claim(scope, {
      execution_profile: "research",
      nl_request: "Assess the policy",
    });

    expect(retry.idempotencyKey).toBe(firstRecord.idempotencyKey);
    expect(reordered.idempotencyKey).toBe(firstRecord.idempotencyKey);
    const serialized = JSON.stringify([...port.records.values()]);
    expect(serialized).toContain(firstRecord.idempotencyKey);
    expect(serialized).not.toContain("Assess the policy");
    expect(serialized).not.toContain("access_token");
    expect(serialized).toMatch(/"bodySha256":"[a-f0-9]{64}"/);
  });

  it("refuses a changed intent while the prior request has no terminal/job observation", async () => {
    const repository =
      createControlPreAdmissionRecoveryRepository(memoryPort());
    const first = await repository.claim(scope, request);

    await expect(
      repository.claim(scope, { ...request, nl_request: "Different policy" }),
    ).rejects.toMatchObject({
      code: "control_pre_admission_recovery_intent_unresolved",
    });
    expect((await repository.read(scope))?.idempotencyKey).toBe(
      first.idempotencyKey,
    );
  });

  it("retains settled event identity and releases the key only on a terminal attempt", async () => {
    const repository =
      createControlPreAdmissionRecoveryRepository(memoryPort());
    const started = await repository.claim(scope, request);
    await repository.observe(scope, response("settled"));
    expect((await repository.read(scope))?.idempotencyKey).toBe(
      started.idempotencyKey,
    );

    const refused = await repository.observe(scope, response("refused"));
    expect(refused.idempotencyKey).toBeNull();
    expect(refused.attemptId).toBe("a".repeat(32));
    expect(refused.producerEventIds).toEqual(["producer-event-a"]);
    const nextLaunch = await repository.claim(scope, request);
    expect(nextLaunch.idempotencyKey).not.toBe(started.idempotencyKey);
  });

  it("requires the bound concrete job and complete history before resolving admission", async () => {
    const repository =
      createControlPreAdmissionRecoveryRepository(memoryPort());
    const started = await repository.claim(scope, request);
    await expect(
      repository.observe(scope, response("admitted")),
    ).rejects.toMatchObject({
      code: "control_pre_admission_recovery_history_invalid",
    });
    expect((await repository.read(scope))?.idempotencyKey).toBe(
      started.idempotencyKey,
    );
    const admitted = await repository.observe(
      scope,
      response("admitted", "job-a"),
    );
    expect(admitted.idempotencyKey).toBeNull();
    expect(admitted.jobId).toBe("job-a");
    expect(admitted.intentSha256).toBe("b".repeat(64));
  });

  it("keeps a settled owner unresolved when a later producer read becomes unavailable", async () => {
    const repository =
      createControlPreAdmissionRecoveryRepository(memoryPort());
    const first = await repository.claim(scope, request);
    const mixed = response("failed", null, "research", "complete");
    mixed.history[mixed.history.length - 1].producer_event_observation =
      "unavailable";
    mixed.producer_event_observation = "unavailable";

    const recovered = await repository.observe(scope, mixed);
    expect(recovered.idempotencyKey).toBe(first.idempotencyKey);
    expect(recovered.producerEventIds).toEqual(["producer-event-a"]);
    expect((await repository.claim(scope, request)).idempotencyKey).toBe(
      first.idempotencyKey,
    );
  });

  it("releases only a producer-attested no-call refusal", async () => {
    const repository =
      createControlPreAdmissionRecoveryRepository(memoryPort());
    const first = await repository.claim(scope, request);
    const refused = await repository.observe(
      scope,
      response("refused", null, "research", "no_call"),
    );
    expect(refused.idempotencyKey).toBeNull();
    expect(refused.producerEventIds).toEqual([]);
    expect((await repository.claim(scope, request)).idempotencyKey).not.toBe(
      first.idempotencyKey,
    );
  });

  it("keeps the key for a no-call state without its typed reason", async () => {
    const repository =
      createControlPreAdmissionRecoveryRepository(memoryPort());
    const first = await repository.claim(scope, request);
    const malformed = response("refused", null, "research", "no_call");
    malformed.history[1].producer_no_call_reason = null;
    await expect(repository.observe(scope, malformed)).rejects.toMatchObject({
      code: "control_pre_admission_recovery_history_invalid",
    });
    expect((await repository.read(scope))?.idempotencyKey).toBe(
      first.idempotencyKey,
    );
  });

  it("retains the key when a reason appears without a no-call state", async () => {
    const repository =
      createControlPreAdmissionRecoveryRepository(memoryPort());
    const first = await repository.claim(scope, request);
    const malformed = response("failed", null, "research", "unavailable");
    malformed.history[1].producer_no_call_reason =
      "provider_preflight_not_started";
    await expect(repository.observe(scope, malformed)).rejects.toMatchObject({
      code: "control_pre_admission_recovery_history_invalid",
    });
    expect((await repository.read(scope))?.idempotencyKey).toBe(
      first.idempotencyKey,
    );
  });

  it("retains the key when the aggregate no-call reason differs from history", async () => {
    const repository =
      createControlPreAdmissionRecoveryRepository(memoryPort());
    const first = await repository.claim(scope, request);
    const malformed = response("refused", null, "research", "no_call");
    malformed.producer_no_call_reason =
      "producer_run_binding_not_established" as never;
    await expect(repository.observe(scope, malformed)).rejects.toMatchObject({
      code: "control_pre_admission_recovery_history_invalid",
    });
    expect((await repository.read(scope))?.idempotencyKey).toBe(
      first.idempotencyKey,
    );
  });

  it("rejects a reason outside the generated no-call union", async () => {
    const repository =
      createControlPreAdmissionRecoveryRepository(memoryPort());
    const first = await repository.claim(scope, request);
    const malformed = response("refused", null, "research", "no_call");
    malformed.history[1].producer_no_call_reason = "invented_reason" as never;
    await expect(repository.observe(scope, malformed)).rejects.toMatchObject({
      code: "control_pre_admission_recovery_history_invalid",
    });
    expect((await repository.read(scope))?.idempotencyKey).toBe(
      first.idempotencyKey,
    );
  });

  it.each(["failed", "cancelled", "refused"] as const)(
    "retains the same key for terminal %s with unavailable producer observation",
    async (status) => {
      const repository =
        createControlPreAdmissionRecoveryRepository(memoryPort());
      const first = await repository.claim(scope, request);
      const unresolved = await repository.observe(
        scope,
        response(status, null, "research", "unavailable"),
      );
      expect(unresolved.idempotencyKey).toBe(first.idempotencyKey);
      expect((await repository.claim(scope, request)).idempotencyKey).toBe(
        first.idempotencyKey,
      );
    },
  );

  it.each(["failed", "cancelled"] as const)(
    "rejects %s when it is mislabeled as a known no-call result",
    async (status) => {
      const repository =
        createControlPreAdmissionRecoveryRepository(memoryPort());
      const first = await repository.claim(scope, request);
      await expect(
        repository.observe(
          scope,
          response(status, null, "research", "no_call"),
        ),
      ).rejects.toMatchObject({
        code: "control_pre_admission_recovery_history_invalid",
      });
      expect((await repository.read(scope))?.idempotencyKey).toBe(
        first.idempotencyKey,
      );
    },
  );

  it("does not release an intent for an untrusted no-call reason", async () => {
    const repository =
      createControlPreAdmissionRecoveryRepository(memoryPort());
    const first = await repository.claim(scope, request);
    const unsupportedReason = response("refused", null, "research", "no_call");
    unsupportedReason.history[1].failure_code = "preflight_failed";

    await expect(
      repository.observe(scope, unsupportedReason),
    ).rejects.toMatchObject({
      code: "control_pre_admission_recovery_history_invalid",
    });
    expect((await repository.read(scope))?.idempotencyKey).toBe(
      first.idempotencyKey,
    );
  });

  it("accepts the default dev direct-admission path without fabricating provider settlement", async () => {
    const repository =
      createControlPreAdmissionRecoveryRepository(memoryPort());
    await repository.claim(scope, request);
    const admitted = await repository.observe(
      scope,
      response("admitted", "dev-job", "dev", "not_applicable"),
    );
    expect(admitted.idempotencyKey).toBeNull();
    expect(admitted.producerEventIds).toEqual([]);
  });

  it.each([
    [
      "principal",
      (value: ReturnType<typeof response>) => ({
        ...value,
        owner_binding: {
          ...value.owner_binding,
          actor_subject_sha256: "d".repeat(64),
        },
      }),
    ],
    [
      "tenant scope",
      (value: ReturnType<typeof response>) => ({
        ...value,
        owner_binding: { ...value.owner_binding, tenant_id: "tenant-other" },
      }),
    ],
    [
      "purpose",
      (value: ReturnType<typeof response>) => ({
        ...value,
        owner_binding: {
          ...value.owner_binding,
          purpose: "run.predictive_calibration.v1" as never,
        },
      }),
    ],
    [
      "body binding",
      (value: ReturnType<typeof response>) => ({
        ...value,
        owner_binding: { ...value.owner_binding, body_sha256: "e".repeat(64) },
      }),
    ],
  ] as const)(
    "refuses a mismatched %s owner binding without clearing the key",
    async (_name, mutate) => {
      const repository =
        createControlPreAdmissionRecoveryRepository(memoryPort());
      const first = await repository.claim(scope, request);
      await expect(
        repository.observe(scope, mutate(response("refused"))),
      ).rejects.toMatchObject({
        code: "control_pre_admission_recovery_owner_binding_invalid",
      });
      expect((await repository.read(scope))?.idempotencyKey).toBe(
        first.idempotencyKey,
      );
    },
  );

  it("keeps the first observed run and job joined to the owner across recovery reads", async () => {
    const repository =
      createControlPreAdmissionRecoveryRepository(memoryPort());
    await repository.claim(scope, request);
    await repository.observe(scope, response("settled"));
    const changedRun = response("failed");
    changedRun.run_id = "run-other";
    changedRun.owner_binding.run_id = "run-other";
    await expect(repository.observe(scope, changedRun)).rejects.toMatchObject({
      code: "control_pre_admission_recovery_run_conflict",
    });

    const devRepository =
      createControlPreAdmissionRecoveryRepository(memoryPort());
    await devRepository.claim(scope, { ...request, execution_profile: "dev" });
    await devRepository.observe(
      scope,
      response("admitted", "job-first", "dev", "not_applicable"),
    );
    const changedJob = response(
      "admitted",
      "job-second",
      "dev",
      "not_applicable",
    );
    await expect(
      devRepository.observe(scope, changedJob),
    ).rejects.toMatchObject({
      code: "control_pre_admission_recovery_job_conflict",
    });
  });

  it("rejects malformed supplied failure evidence instead of treating it as absent", async () => {
    const repository =
      createControlPreAdmissionRecoveryRepository(memoryPort());
    const first = await repository.claim(scope, request);
    const malformed = response("failed");
    malformed.history[1].failure_code = "invalid failure code";

    await expect(repository.observe(scope, malformed)).rejects.toMatchObject({
      code: "control_pre_admission_recovery_history_invalid",
    });
    expect((await repository.read(scope))?.idempotencyKey).toBe(
      first.idempotencyKey,
    );
  });

  it("does not treat a complete observation without refs as empty evidence", async () => {
    const repository =
      createControlPreAdmissionRecoveryRepository(memoryPort());
    const first = await repository.claim(scope, request);
    const malformed = response("failed", null, "research", "complete");
    malformed.history[1].producer_event_ids = [];

    await expect(repository.observe(scope, malformed)).rejects.toMatchObject({
      code: "control_pre_admission_recovery_history_invalid",
    });
    expect((await repository.read(scope))?.idempotencyKey).toBe(
      first.idempotencyKey,
    );
  });

  it("refuses a serious terminal complete event that skipped settlement", async () => {
    const repository =
      createControlPreAdmissionRecoveryRepository(memoryPort());
    const first = await repository.claim(scope, request);
    const malformed = response("failed", null, "research", "complete");
    malformed.history.splice(1, 1);
    malformed.history[1].sequence = 2;

    await expect(repository.observe(scope, malformed)).rejects.toMatchObject({
      code: "control_pre_admission_recovery_history_invalid",
    });
    expect((await repository.read(scope))?.idempotencyKey).toBe(
      first.idempotencyKey,
    );
  });

  it("refuses a non-append-only mixed status history and keeps the key", async () => {
    const repository =
      createControlPreAdmissionRecoveryRepository(memoryPort());
    const first = await repository.claim(scope, request);
    const altered = response("failed", null, "research", "complete");
    altered.history[1] = { ...altered.history[1], sequence: 3 };
    await expect(repository.observe(scope, altered)).rejects.toMatchObject({
      code: "control_pre_admission_recovery_history_invalid",
    });
    expect((await repository.read(scope))?.idempotencyKey).toBe(
      first.idempotencyKey,
    );
  });

  it("releases only an exact key/body after an explicit no-attempt response", async () => {
    const repository =
      createControlPreAdmissionRecoveryRepository(memoryPort());
    const first = await repository.claim(scope, request);
    expect(first.idempotencyKey).not.toBeNull();
    expect(
      await repository.releaseKnownNoAttempt(
        scope,
        request,
        first.idempotencyKey!,
      ),
    ).toBe(true);
    expect(await repository.read(scope)).toMatchObject({
      idempotencyKey: null,
      attemptId: null,
      status: null,
    });
    const next = await repository.claim(scope, request);
    expect(next.idempotencyKey).not.toBe(first.idempotencyKey);
  });

  it("retains an attempt key when the body differs or the server attempt is known", async () => {
    const repository =
      createControlPreAdmissionRecoveryRepository(memoryPort());
    const first = await repository.claim(scope, request);
    expect(
      await repository.releaseKnownNoAttempt(
        scope,
        { ...request, nl_request: "different" },
        first.idempotencyKey!,
      ),
    ).toBe(false);
    await repository.rememberAttemptId(scope, "a".repeat(32));
    expect(
      await repository.releaseKnownNoAttempt(
        scope,
        request,
        first.idempotencyKey!,
      ),
    ).toBe(false);
    expect((await repository.read(scope))?.idempotencyKey).toBe(
      first.idempotencyKey,
    );
  });

  it("does not mint a replacement key for a legacy terminal row without owner proof", async () => {
    const port = memoryPort();
    const repository = createControlPreAdmissionRecoveryRepository(port);
    const first = await repository.claim(scope, request);
    await repository.rememberAttemptId(scope, "a".repeat(32));
    const record = await repository.read(scope);
    expect(record).not.toBeNull();
    const legacy = { ...record! } as Record<string, unknown>;
    delete legacy.intentSha256;
    delete legacy.lastEventId;
    legacy.idempotencyKey = null;
    port.records.set(record!.scopeKey, legacy);

    const remounted = createControlPreAdmissionRecoveryRepository(port);
    await expect(remounted.claim(scope, request)).rejects.toMatchObject({
      code: "control_pre_admission_recovery_legacy_attempt_unverified",
    });
    expect(first.idempotencyKey).not.toBeNull();
    expect((await remounted.read(scope))?.idempotencyKey).toBeNull();
  });

  it("fails closed on malformed persisted state instead of treating it as absent", async () => {
    const port = memoryPort();
    const repository = createControlPreAdmissionRecoveryRepository(port);
    const initial = await repository.claim(scope, request);
    const record = await repository.read(scope);
    expect(record).not.toBeNull();
    port.records.set(record!.scopeKey, { ...record, unexpected: "present" });

    await expect(repository.claim(scope, request)).rejects.toBeInstanceOf(
      ControlPreAdmissionRecoveryError,
    );
    expect(initial.idempotencyKey).toBeTruthy();
  });
});
