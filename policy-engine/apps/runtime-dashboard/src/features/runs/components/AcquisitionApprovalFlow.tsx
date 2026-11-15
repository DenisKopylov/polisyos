import { onlineManager } from "@tanstack/react-query";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { AcquisitionRouteMutationRequest } from "@polisyos/runtime-api-client";
import { useLocation, useNavigate } from "react-router-dom";

import { useControlJobStatus } from "@/api/hooks/useControlJobStatus";
import type {
  AcquisitionDecisionRequestResponseCurrent,
  AcquisitionExecutionResponseCurrent,
  AcquisitionRouteProjection,
} from "@/features/runs/api/acquisitionRouteValidators";
import {
  executeAcquisitionRoute,
  requestAcquisitionDecision,
  useAcquisitionGrowth,
  useAcquisitionRoute,
} from "@/features/runs/api/useAcquisitionRoutes";
import {
  fetchHumanDecisionEvidence,
  HumanDecisionRecoveryAttemptError,
  type HumanDecisionCreateReceipt,
  type HumanDecisionMutationRequest,
  type HumanDecisionReplaySelector,
  type HumanDecisionSubmissionResult,
  useCreateHumanDecision,
  useHumanDecisionGate,
  withoutHumanDecisionOwnedQuery,
} from "@/features/runs/api/useHumanDecisions";
import { AcquisitionRouteDetail } from "@/features/runs/components/AcquisitionRouteDetail";
import { HumanDecisionGate } from "@/features/runs/components/HumanDecisionGate";
import {
  buildHumanDecisionMutation,
  type HumanDecisionFormInput,
} from "@/features/runs/domain/humanDecisionPresentation";
import { presentRunAcquisitionRoute } from "@/features/runs/domain/acquisitionRoutePresentation";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { TimeSemanticsLabel } from "@/shared/ui/temporal/TimeSemanticsLabel";
import { exportCapturedResponseBytes } from "@/shared/ui/dataExport";
import { Button, Card } from "@polisyos/atlas-ui";

import { AcquisitionExecutionTimeline } from "./AcquisitionExecutionTimeline";
import { downloadAcquisitionRoutePacket } from "./acquisitionRouteExport";

type AcquisitionApprovalFlowProps = Readonly<{
  canMutate: boolean;
  route: AcquisitionRouteProjection;
}>;

type HumanDecisionRecoveryContext = Readonly<{
  body: HumanDecisionMutationRequest;
  continuation: HumanDecisionReplaySelector;
  exposureSessionRef: string;
  input: HumanDecisionFormInput;
  runId: string;
}>;

function isRecord(value: unknown): value is Readonly<Record<string, unknown>> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function mutationForRoute(
  route: AcquisitionRouteProjection,
  humanDecisionRecordRef?: string,
): AcquisitionRouteMutationRequest {
  return {
    human_decision_record_ref: humanDecisionRecordRef,
    idempotency_key: humanDecisionRecordRef
      ? `${route.route_projection_hash}:${humanDecisionRecordRef}`
      : route.route_projection_hash,
    planner_report_hash: route.planner_report_hash,
    replay_pins: route.replay_pins,
    route_projection_hash: route.route_projection_hash,
  };
}

function jsonValuesEqual(left: unknown, right: unknown): boolean {
  if (Object.is(left, right)) return true;
  if (Array.isArray(left) || Array.isArray(right)) {
    return (
      Array.isArray(left) &&
      Array.isArray(right) &&
      left.length === right.length &&
      left.every((member, index) => jsonValuesEqual(member, right[index]))
    );
  }
  if (!isRecord(left) || !isRecord(right)) return false;
  const leftKeys = Object.keys(left)
    .filter((key) => left[key] !== undefined)
    .sort();
  const rightKeys = Object.keys(right)
    .filter((key) => right[key] !== undefined)
    .sort();
  return (
    leftKeys.length === rightKeys.length &&
    leftKeys.every(
      (key, index) =>
        key === rightKeys[index] && jsonValuesEqual(left[key], right[key]),
    )
  );
}

function sameRoute(
  expected: AcquisitionRouteProjection,
  actual: AcquisitionRouteProjection,
) {
  return jsonValuesEqual(expected, actual);
}

function surfacedError(error: unknown) {
  if (
    error &&
    typeof error === "object" &&
    "code" in error &&
    typeof error.code === "string"
  ) {
    return error.code;
  }
  return error instanceof Error
    ? error.message
    : "DS15-ACQUISITION-ACTION-FAILED";
}

function requireOnline() {
  if (!onlineManager.isOnline()) {
    throw new TypeError("DS15-OFFLINE-AUTHORITY");
  }
}

export function AcquisitionApprovalFlow({
  canMutate,
  route,
}: AcquisitionApprovalFlowProps) {
  const { t } = useI18n();
  const location = useLocation();
  const navigate = useNavigate();
  const routeQuery = useAcquisitionRoute(route.run_id, route.route_id);
  const growthQuery = useAcquisitionGrowth();
  const gateQuery = useHumanDecisionGate(route.run_id, location.search);
  const createDecision = useCreateHumanDecision(route.run_id);
  const [decision, setDecision] =
    useState<AcquisitionDecisionRequestResponseCurrent | null>(null);
  const [humanDecision, setHumanDecision] =
    useState<HumanDecisionCreateReceipt | null>(null);
  const [submissionResult, setSubmissionResult] =
    useState<HumanDecisionSubmissionResult | null>(null);
  const [execution, setExecution] =
    useState<AcquisitionExecutionResponseCurrent | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const actionInFlight = useRef(false);
  const executionStarted = useRef(false);
  const recoveryContext = useRef<HumanDecisionRecoveryContext | null>(null);
  const activeRunId = useRef(route.run_id);
  activeRunId.current = route.run_id;
  const componentMounted = useRef(false);
  const reviewSurface = useRef<HTMLDivElement>(null);
  const reviewWasVisible = useRef(false);
  const refreshedJob = useRef<string | null>(null);
  const timelineFocus = useRef<HTMLDivElement>(null);
  const jobQuery = useControlJobStatus(execution?.job_id);
  const routeDetail = routeQuery.data?.packet ?? route;
  const routePresentation = presentRunAcquisitionRoute(routeDetail);
  const costEstablished = routePresentation.costEstablished;

  useLayoutEffect(() => {
    componentMounted.current = true;
    return () => {
      componentMounted.current = false;
      recoveryContext.current = null;
    };
  }, []);

  useEffect(() => {
    recoveryContext.current = null;
    setDecision(null);
    setHumanDecision(null);
    setSubmissionResult(null);
    setExecution(null);
    setErrorCode(null);
    if (!actionInFlight.current) setPending(false);
  }, [route.run_id]);

  function assertCurrentRun(expectedRunId: string) {
    if (
      !componentMounted.current ||
      activeRunId.current !== expectedRunId ||
      route.run_id !== expectedRunId
    ) {
      throw new TypeError("DS15-SAME-CASE-MISMATCH");
    }
  }

  const recoveryStatusKey =
    submissionResult?.kind === "created"
      ? "created"
      : submissionResult?.kind === "recovered_committed"
        ? "recoveredCommitted"
        : submissionResult?.kind === "recovery_pending"
          ? "recoveryPending"
          : submissionResult?.kind === "recovery_not_established"
            ? "recoveryNotEstablished"
            : submissionResult?.kind === "recovered_expired"
              ? "recoveredExpired"
              : createDecision.recoveryPosture?.kind === "recovery_unavailable"
                ? "recoveryUnavailable"
                : null;

  async function finishHumanDecisionSubmission(
    result: HumanDecisionSubmissionResult,
    context: HumanDecisionRecoveryContext,
  ) {
    assertCurrentRun(context.runId);
    if (
      context.runId !== route.run_id ||
      ("receipt" in result && result.receipt.run_id !== context.runId)
    ) {
      throw new TypeError("DS15-SAME-CASE-MISMATCH");
    }
    setSubmissionResult(result);
    setErrorCode(null);
    if (
      result.kind === "recovery_pending" ||
      result.kind === "recovery_not_established"
    ) {
      recoveryContext.current = context;
      gateQuery.clear();
      return;
    }

    const receipt = result.receipt;
    setHumanDecision(receipt);
    gateQuery.clear();
    if (result.kind === "recovered_expired") {
      recoveryContext.current = null;
      return;
    }

    if (result.kind === "recovered_committed") {
      try {
        const fresh = await gateQuery.revalidate(context.continuation);
        assertCurrentRun(context.runId);
        if (fresh.packet.run_id !== context.runId) {
          throw new TypeError("DS15-SAME-CASE-MISMATCH");
        }
        const currentBody = buildHumanDecisionMutation(
          fresh.packet,
          context.input,
        );
        if (
          fresh.packet.exposure.exposure_session_ref !==
            context.exposureSessionRef ||
          !jsonValuesEqual(currentBody, context.body)
        ) {
          throw new TypeError("DS9-RECOVERED-DECISION-GATE-CHANGED");
        }
        if (context.input.action === "approve") {
          const sourceRef = fresh.packet.source_ref;
          if (
            fresh.packet.source_kind !== "agent_action_authority" ||
            !sourceRef ||
            sourceRef !== context.body.source_ref
          ) {
            throw new TypeError("DS15-AUTHORITY-DECISION-REF-MISSING");
          }
          assertCurrentRun(context.runId);
          await executeFresh(sourceRef, receipt.record_ref, context.runId);
        }
      } finally {
        recoveryContext.current = null;
      }
      return;
    }

    recoveryContext.current = null;
    if (context.input.action === "approve") {
      const sourceRef = context.body.source_ref;
      if (context.body.source_kind !== "agent_action_authority" || !sourceRef) {
        throw new TypeError("DS15-AUTHORITY-DECISION-REF-MISSING");
      }
      assertCurrentRun(context.runId);
      await executeFresh(sourceRef, receipt.record_ref, context.runId);
    }
  }

  async function checkSavedHumanDecision() {
    if (actionInFlight.current) return;
    const context = recoveryContext.current;
    if (!context) {
      setErrorCode("human_decision_recovery_not_pending");
      return;
    }
    assertCurrentRun(context.runId);
    actionInFlight.current = true;
    setErrorCode(null);
    setPending(true);
    try {
      const result = await createDecision.recoverPending();
      assertCurrentRun(context.runId);
      await finishHumanDecisionSubmission(result, context);
    } catch (error) {
      if (componentMounted.current && activeRunId.current === context.runId) {
        setErrorCode(surfacedError(error));
      }
    } finally {
      actionInFlight.current = false;
      if (componentMounted.current) setPending(false);
    }
  }

  async function freshBoundRoute(expectedRunId = route.run_id) {
    assertCurrentRun(expectedRunId);
    const result = await routeQuery.refetch();
    const fresh = result.data?.packet;
    assertCurrentRun(expectedRunId);
    if (!fresh || fresh.run_id !== expectedRunId || !sameRoute(route, fresh)) {
      throw new TypeError("DS15-STALE-DECISION-REPLAY");
    }
    return fresh;
  }

  async function executeFresh(
    authorityDecisionRef: string,
    humanDecisionRecordRef?: string,
    expectedRunId = route.run_id,
  ) {
    if (executionStarted.current || execution) return;
    executionStarted.current = true;
    try {
      assertCurrentRun(expectedRunId);
      requireOnline();
      const fresh = await freshBoundRoute(expectedRunId);
      assertCurrentRun(expectedRunId);
      if (fresh.run_id !== expectedRunId) {
        throw new TypeError("DS15-SAME-CASE-MISMATCH");
      }
      assertCurrentRun(expectedRunId);
      const receipt = await executeAcquisitionRoute(
        fresh.run_id,
        fresh.route_id,
        mutationForRoute(fresh, humanDecisionRecordRef),
      );
      if (
        receipt.run_id !== fresh.run_id ||
        receipt.route_id !== fresh.route_id ||
        receipt.authority_decision_ref !== authorityDecisionRef
      ) {
        throw new TypeError("DS15-SAME-CASE-MISMATCH");
      }
      assertCurrentRun(expectedRunId);
      setExecution(receipt);
    } catch (error) {
      executionStarted.current = false;
      throw error;
    }
  }

  function openDecisionSelector(authorityDecisionRef: string) {
    const retained = withoutHumanDecisionOwnedQuery(location.search);
    const parameters = new URLSearchParams(
      retained.startsWith("?") ? retained.slice(1) : retained,
    );
    parameters.set("source_kind", "agent_action_authority");
    parameters.set("source_ref", authorityDecisionRef);
    navigate(
      {
        pathname: location.pathname,
        search: `?${parameters.toString()}`,
      },
      { replace: true },
    );
  }

  async function prepareDecision() {
    if (actionInFlight.current) return;
    assertCurrentRun(route.run_id);
    actionInFlight.current = true;
    setErrorCode(null);
    setPending(true);
    try {
      requireOnline();
      const currentPresentation = presentRunAcquisitionRoute(route);
      if (!currentPresentation.costEstablished) {
        throw new TypeError("DS15-COST-NOT-ESTABLISHED");
      }
      if (!currentPresentation.actionEligible) {
        throw new TypeError("DS15-ROUTE-NOT-ELIGIBLE");
      }
      const fresh = await freshBoundRoute(route.run_id);
      assertCurrentRun(route.run_id);
      if (!presentRunAcquisitionRoute(fresh).actionEligible) {
        throw new TypeError("DS15-ROUTE-NOT-ELIGIBLE");
      }
      const response = await requestAcquisitionDecision(
        fresh.run_id,
        fresh.route_id,
        mutationForRoute(fresh),
      );
      if (
        response.run_id !== fresh.run_id ||
        response.route_id !== fresh.route_id
      ) {
        throw new TypeError("DS15-SAME-CASE-MISMATCH");
      }
      assertCurrentRun(route.run_id);
      setDecision(response);
      if (response.outcome === "decision_available") {
        await executeFresh(response.authority_decision_ref);
      } else {
        openDecisionSelector(response.authority_decision_ref);
      }
    } catch (error) {
      if (componentMounted.current && activeRunId.current === route.run_id) {
        setErrorCode(surfacedError(error));
      }
    } finally {
      actionInFlight.current = false;
      if (componentMounted.current) setPending(false);
    }
  }

  useEffect(() => {
    const job = jobQuery.data;
    if (
      !job ||
      job.state !== "completed" ||
      refreshedJob.current === job.job_id
    ) {
      return;
    }
    refreshedJob.current = job.job_id;
    void Promise.all([routeQuery.refetch(), growthQuery.refetch()]).catch(
      (error: unknown) => setErrorCode(surfacedError(error)),
    );
  }, [growthQuery, jobQuery.data, routeQuery]);

  const capturedGate = gateQuery.data;
  useEffect(() => {
    if (!capturedGate) {
      reviewWasVisible.current = false;
      return;
    }
    if (reviewWasVisible.current) return;
    reviewWasVisible.current = true;
    reviewSurface.current
      ?.querySelector<HTMLElement>("#human-decision-accountability")
      ?.focus();
  }, [capturedGate]);

  useEffect(() => {
    if (execution) timelineFocus.current?.focus();
  }, [execution]);

  return (
    <section
      className="w-[min(42rem,calc(100vw-3rem))] min-w-0 space-y-4 overflow-hidden [&_pre]:max-w-full [&_pre]:break-all"
      data-testid="acquisition-approval-flow"
    >
      <div data-testid="acquisition-approval-time-semantics">
        <TimeSemanticsLabel />
      </div>
      <AcquisitionRouteDetail
        action={
          <div className="space-y-2">
            <Button
              disabled={
                !canMutate ||
                !costEstablished ||
                !routePresentation.actionEligible ||
                pending ||
                actionInFlight.current ||
                Boolean(execution)
              }
              onClick={() => void prepareDecision()}
              type="button"
              variant="primary"
            >
              {t(
                routePresentation.acquisitionMode ===
                  "paid_input_admission_only"
                  ? "pages.cycleBoard.acquisition.action.requestAdmissionReview"
                  : "pages.cycleBoard.acquisition.action.requestReview",
              )}
            </Button>
            {!costEstablished ? (
              <p
                className="font-mono text-sm"
                data-testid="acquisition-cost-refusal"
              >
                {t("pages.cycleBoard.acquisition.action.costNotEstablished")}
              </p>
            ) : null}
          </div>
        }
        kind="run"
        route={routeDetail}
      />

      {routeQuery.data ? (
        <Button
          onClick={() =>
            downloadAcquisitionRoutePacket(
              route.run_id,
              routeQuery.data.rawPacketBytes,
            )
          }
          type="button"
          variant="ghost"
        >
          {t("pages.cycleBoard.acquisition.action.exportRoute")}
        </Button>
      ) : null}

      {capturedGate ? (
        <div className="space-y-3" ref={reviewSurface}>
          <Button
            onClick={() =>
              exportCapturedResponseBytes(
                `policyos-run-${route.run_id}-human-decision.json`,
                capturedGate.rawPacketBytes,
                "application/json",
              )
            }
            type="button"
            variant="ghost"
          >
            {t("pages.cycleBoard.acquisition.action.exportReview")}
          </Button>
          <HumanDecisionGate
            canMutate={canMutate && !actionInFlight.current}
            captured={capturedGate}
            onOpenEvidence={async (artifactDigest) => {
              const current = gateQuery.data?.packet;
              const continuation = current?.continuation;
              const exposureSessionRef = current?.exposure.exposure_session_ref;
              if (!continuation || !exposureSessionRef) {
                throw new TypeError(
                  "DS9-EVIDENCE-REVALIDATION-SELECTOR-MISSING",
                );
              }
              const evidence = await fetchHumanDecisionEvidence(
                route.run_id,
                artifactDigest,
                exposureSessionRef,
              );
              exportCapturedResponseBytes(
                `policyos-run-${route.run_id}-evidence-${artifactDigest.replace(":", "-")}`,
                evidence.bytes,
                evidence.mediaType,
              );
              await gateQuery.revalidate(continuation);
            }}
            onSubmit={async (input) => {
              if (actionInFlight.current) return;
              actionInFlight.current = true;
              setErrorCode(null);
              setPending(true);
              try {
                requireOnline();
                const continuation = gateQuery.data?.packet.continuation;
                if (!continuation) {
                  throw new TypeError(
                    "DS9-SUBMISSION-REVALIDATION-SELECTOR-MISSING",
                  );
                }
                assertCurrentRun(route.run_id);
                const freshGate = await gateQuery.revalidate(continuation);
                assertCurrentRun(route.run_id);
                if (freshGate.packet.run_id !== route.run_id) {
                  throw new TypeError("DS15-SAME-CASE-MISMATCH");
                }
                const exposureSessionRef =
                  freshGate.packet.exposure.exposure_session_ref;
                if (!exposureSessionRef) {
                  throw new TypeError("DS9-EXPOSURE-SESSION-MISSING");
                }
                const body = buildHumanDecisionMutation(
                  freshGate.packet,
                  input,
                );
                const context: HumanDecisionRecoveryContext = Object.freeze({
                  body,
                  continuation,
                  exposureSessionRef,
                  input,
                  runId: route.run_id,
                });
                recoveryContext.current = context;
                const result = await createDecision.mutateAsync({
                  body,
                  exposureSessionRef,
                  runId: route.run_id,
                });
                assertCurrentRun(route.run_id);
                if (
                  (result.kind === "created" ||
                    result.kind === "recovered_committed" ||
                    result.kind === "recovered_expired") &&
                  result.receipt.run_id !== route.run_id
                ) {
                  throw new TypeError("DS15-SAME-CASE-MISMATCH");
                }
                await finishHumanDecisionSubmission(result, context);
              } catch (error) {
                const isCurrentRun =
                  componentMounted.current &&
                  activeRunId.current === route.run_id;
                if (isCurrentRun) setErrorCode(surfacedError(error));
                if (
                  isCurrentRun &&
                  error instanceof HumanDecisionRecoveryAttemptError
                ) {
                  gateQuery.clear();
                } else if (isCurrentRun && !createDecision.recoveryPosture) {
                  recoveryContext.current = null;
                }
                throw error;
              } finally {
                actionInFlight.current = false;
                if (componentMounted.current) setPending(false);
              }
            }}
          />
        </div>
      ) : null}

      {gateQuery.hasSelector && gateQuery.isLoading ? (
        <Card aria-live="polite">
          {t("pages.cycleBoard.acquisition.action.loadingReview")}
        </Card>
      ) : null}
      {gateQuery.hasSelector && gateQuery.isError ? (
        <p role="alert">DS15-ACCOUNTABLE-REVIEW-UNAVAILABLE</p>
      ) : null}
      {recoveryStatusKey ? (
        <Card
          className="space-y-2"
          data-testid="human-decision-submission-status"
          role="status"
        >
          <p>
            {t(
              `pages.runs.report.humanDecision.submission.${recoveryStatusKey}`,
            )}
          </p>
          {submissionResult?.kind === "recovery_pending" ? (
            <code>{submissionResult.recovery.reservation_id}</code>
          ) : null}
          {submissionResult?.kind === "recovery_not_established" ? (
            <code>{submissionResult.recovery.reason_code}</code>
          ) : null}
          {createDecision.recoveryPosture?.kind === "recovery_unavailable" ? (
            <code>{createDecision.recoveryPosture.code}</code>
          ) : null}
          {createDecision.recoveryPosture !== null ? (
            <Button
              disabled={pending}
              onClick={() => void checkSavedHumanDecision()}
              type="button"
              variant="secondary"
            >
              {t("pages.runs.report.humanDecision.submission.checkStatus")}
            </Button>
          ) : null}
        </Card>
      ) : null}
      {errorCode ? (
        <p className="font-mono text-sm" role="alert">
          {errorCode}
        </p>
      ) : null}

      <div
        data-testid="acquisition-timeline-focus-target"
        ref={timelineFocus}
        tabIndex={-1}
      >
        <AcquisitionExecutionTimeline
          decision={decision}
          execution={execution}
          growthHistory={growthQuery.data?.payload.n13b_history}
          humanDecision={humanDecision}
          humanDecisionSubmissionKind={submissionResult?.kind}
          job={jobQuery.data}
          route={routeDetail}
        />
      </div>
    </section>
  );
}
