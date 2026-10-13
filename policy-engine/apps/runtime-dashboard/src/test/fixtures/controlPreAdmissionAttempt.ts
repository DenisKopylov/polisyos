import type { components } from "@/api/types";

type AttemptResponse =
  components["schemas"]["ControlPreAdmissionAttemptResponse"];
type AttemptEvent =
  components["schemas"]["ControlPreAdmissionAttemptEventInfo"];

export function controlPreAdmissionAttemptFixture(input: {
  attemptId: string;
  runId: string;
  status: "started" | "settled";
}): AttemptResponse {
  const timestamp = "2026-10-12T10:00:00Z";
  const started: AttemptEvent = {
    event_id: input.attemptId + "-started",
    event_type: "started",
    failure_code: null,
    job_id: null,
    observed_at: timestamp,
    producer_event_ids: [],
    producer_event_observation: "not_applicable",
    producer_no_call_reason: null,
    sequence: 1,
  };
  const settlement: AttemptEvent = {
    event_id: input.attemptId + "-settled",
    event_type: "settled",
    failure_code: null,
    job_id: null,
    observed_at: timestamp,
    producer_event_ids: ["producer-event-a"],
    producer_event_observation: "complete",
    producer_no_call_reason: null,
    sequence: 2,
  };
  const settled = input.status === "settled";
  return {
    attempt_id: input.attemptId,
    created_at: timestamp,
    effective_execution_profile: "research",
    failure_code: null,
    history: settled ? [started, settlement] : [started],
    intent_sha256: "c".repeat(64),
    job_id: null,
    meta: {
      generated_at: timestamp,
      request_id: "request-control-pre-admission-fixture",
      source_kinds: ["core_run"],
    },
    owner_binding: {
      actor_subject_sha256: "d".repeat(64),
      body_sha256: "e".repeat(64),
      cell_id: "cell-test",
      effective_execution_profile: "research",
      intent_id: "f".repeat(32),
      purpose: "control.nl_pre_admission.v1",
      request_content_sha256: "sha256:" + "0".repeat(64),
      run_id: input.runId,
      scope_id: "control.runs.nl",
      scope_kind: "route",
      tenant_id: "tenant-test",
    },
    producer_event_ids: settled ? ["producer-event-a"] : [],
    producer_event_observation: settled ? "complete" : "not_applicable",
    producer_no_call_reason: null,
    run_id: input.runId,
    status: input.status,
    updated_at: timestamp,
  };
}
