import { onlineManager } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import type {
  AcquisitionDecisionRequestResponse,
  AcquisitionExecutionResponse,
  AcquisitionRouteMutationRequest,
  AcquisitionRouteProjection,
} from "@polisyos/runtime-api-client";
import { useLocation, useNavigate } from "react-router-dom";

import { useControlJobStatus } from "@/api/hooks/useControlJobStatus";
import {
  executeAcquisitionRoute,
  requestAcquisitionDecision,
  useAcquisitionGrowth,
  useAcquisitionRoute,
} from "@/features/runs/api/useAcquisitionRoutes";
import {
  fetchHumanDecisionEvidence,
  useCreateHumanDecision,
  useHumanDecisionGate,
  withoutHumanDecisionOwnedQuery,
} from "@/features/runs/api/useHumanDecisions";
import { AcquisitionRouteDetail } from "@/features/runs/components/AcquisitionRouteDetail";
import { HumanDecisionGate } from "@/features/runs/components/HumanDecisionGate";
import { buildHumanDecisionMutation } from "@/features/runs/domain/humanDecisionPresentation";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { exportCapturedResponseBytes } from "@/shared/ui/dataExport";
import { Button, Card } from "@polisyos/atlas-ui";

import { AcquisitionExecutionTimeline } from "./AcquisitionExecutionTimeline";
import { downloadAcquisitionRoutePacket } from "./acquisitionRouteExport";

type AcquisitionApprovalFlowProps = Readonly<{
  canMutate: boolean;
  route: AcquisitionRouteProjection;
}>;

function isRecord(value: unknown): value is Readonly<Record<string, unknown>> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function ownerBackedCostIsEstablished(route: AcquisitionRouteProjection) {
  const cost = route.cost_basis;
  return (
    isRecord(cost) &&
    cost.schema_version === "AcquisitionCostBasisRecord@1.0" &&
    typeof cost.total_amount === "number" &&
    cost.total_amount > 0 &&
    cost.record_content_hash === route.replay_pins.cost_basis_hash
  );
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
    useState<AcquisitionDecisionRequestResponse | null>(null);
  const [humanDecision, setHumanDecision] = useState<Awaited<
    ReturnType<typeof createDecision.mutateAsync>
  > | null>(null);
  const [execution, setExecution] =
    useState<AcquisitionExecutionResponse | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const actionInFlight = useRef(false);
  const executionStarted = useRef(false);
  const reviewSurface = useRef<HTMLDivElement>(null);
  const reviewWasVisible = useRef(false);
  const refreshedJob = useRef<string | null>(null);
  const timelineFocus = useRef<HTMLDivElement>(null);
  const jobQuery = useControlJobStatus(execution?.job_id);
  const routeDetail = routeQuery.data?.packet ?? route;
  const costEstablished = ownerBackedCostIsEstablished(routeDetail);

  async function freshBoundRoute() {
    const result = await routeQuery.refetch();
    const fresh = result.data?.packet;
    if (!fresh || !sameRoute(route, fresh)) {
      throw new TypeError("DS15-STALE-DECISION-REPLAY");
    }
    return fresh;
  }

  async function executeFresh(
    authorityDecisionRef: string,
    humanDecisionRecordRef?: string,
  ) {
    if (executionStarted.current || execution) return;
    executionStarted.current = true;
    try {
      requireOnline();
      const fresh = await freshBoundRoute();
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
    actionInFlight.current = true;
    setErrorCode(null);
    setPending(true);
    try {
      requireOnline();
      if (!ownerBackedCostIsEstablished(route)) {
        throw new TypeError("DS15-COST-NOT-ESTABLISHED");
      }
      const fresh = await freshBoundRoute();
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
      setDecision(response);
      if (response.outcome === "decision_available") {
        await executeFresh(response.authority_decision_ref);
      } else {
        openDecisionSelector(response.authority_decision_ref);
      }
    } catch (error) {
      setErrorCode(surfacedError(error));
    } finally {
      actionInFlight.current = false;
      setPending(false);
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
      <AcquisitionRouteDetail
        action={
          <div className="space-y-2">
            <Button
              disabled={
                !canMutate || !costEstablished || pending || Boolean(execution)
              }
              onClick={() => void prepareDecision()}
              type="button"
              variant="primary"
            >
              {t("pages.cycleBoard.acquisition.action.requestReview")}
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
            canMutate={canMutate}
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
                const freshGate = await gateQuery.revalidate(continuation);
                const exposureSessionRef =
                  freshGate.packet.exposure.exposure_session_ref;
                if (!exposureSessionRef) {
                  throw new TypeError("DS9-EXPOSURE-SESSION-MISSING");
                }
                const body = buildHumanDecisionMutation(
                  freshGate.packet,
                  input,
                );
                const receipt = await createDecision.mutateAsync({
                  body,
                  exposureSessionRef,
                  runId: route.run_id,
                });
                if (receipt.run_id !== route.run_id) {
                  throw new TypeError("DS15-SAME-CASE-MISMATCH");
                }
                setHumanDecision(receipt);
                if (input.action === "approve") {
                  const sourceRef = freshGate.packet.source_ref;
                  if (
                    freshGate.packet.source_kind !== "agent_action_authority" ||
                    !sourceRef
                  ) {
                    throw new TypeError("DS15-AUTHORITY-DECISION-REF-MISSING");
                  }
                  await executeFresh(sourceRef, receipt.record_ref);
                }
                gateQuery.clear();
              } catch (error) {
                setErrorCode(surfacedError(error));
                throw error;
              } finally {
                actionInFlight.current = false;
                setPending(false);
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
          job={jobQuery.data}
          route={routeDetail}
        />
      </div>
    </section>
  );
}
