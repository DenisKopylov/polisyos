import type {
  AcquisitionDecisionRequestResponse,
  AcquisitionExecutionResponse,
  AcquisitionGrowthPayload,
  AcquisitionRouteProjection,
} from "@polisyos/runtime-api-client";

import type { ControlJobResponse } from "@/api/hooks/useControlJobStatus";
import type { HumanDecisionCreateReceipt } from "@/api/validators";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { TimeSemanticsLabel } from "@/shared/ui/temporal/TimeSemanticsLabel";
import { Badge, Card } from "@polisyos/atlas-ui";

export type AcquisitionExecutionTimelineProps = Readonly<{
  decision?: AcquisitionDecisionRequestResponse | null;
  execution?: AcquisitionExecutionResponse | null;
  growthHistory?: AcquisitionGrowthPayload["n13b_history"] | null;
  humanDecision?: HumanDecisionCreateReceipt | null;
  job?: ControlJobResponse | null;
  route: AcquisitionRouteProjection;
}>;

type TimelineFact = Readonly<{
  phase: string;
  raw: Readonly<Record<string, unknown>>;
  receiptRef?: string;
  scope: "run_route" | "global_n13b_history";
  status: string;
}>;

function recordValue(value: unknown): Readonly<Record<string, unknown>> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Readonly<Record<string, unknown>>)
    : {};
}

function jobPhase(job: ControlJobResponse): string {
  const phase = recordValue(job.progress).receipt_phase;
  return typeof phase === "string" ? phase : job.state;
}

function terminalReceiptRef(job: ControlJobResponse): string | undefined {
  const value = recordValue(job.progress).terminal_receipt_ref;
  return typeof value === "string" ? value : undefined;
}

function decisionAction(receipt: HumanDecisionCreateReceipt): string {
  const action = recordValue(receipt.record).action;
  return typeof action === "string" ? action : "recorded";
}

function assertSameCase(
  route: AcquisitionRouteProjection,
  candidate: Readonly<{ route_id?: string; run_id?: string }>,
) {
  if (
    candidate.run_id !== route.run_id ||
    (candidate.route_id !== undefined && candidate.route_id !== route.route_id)
  ) {
    throw new TypeError("DS15-SAME-CASE-MISMATCH");
  }
}

function timelineFacts({
  decision,
  execution,
  growthHistory,
  humanDecision,
  job,
  route,
}: AcquisitionExecutionTimelineProps): readonly TimelineFact[] {
  const facts: TimelineFact[] = [
    {
      phase: "refusal_with_path",
      raw: route as Readonly<Record<string, unknown>>,
      scope: "run_route",
      status: route.route_status,
    },
  ];
  if (decision) {
    assertSameCase(route, decision);
    facts.push({
      phase: decision.outcome,
      raw: decision as Readonly<Record<string, unknown>>,
      receiptRef: decision.authority_decision_ref,
      scope: "run_route",
      status: decision.outcome,
    });
  }
  if (humanDecision) {
    assertSameCase(route, humanDecision);
    facts.push({
      phase:
        decisionAction(humanDecision) === "approve"
          ? "approved"
          : "decision_recorded",
      raw: humanDecision as Readonly<Record<string, unknown>>,
      receiptRef: humanDecision.record_ref,
      scope: "run_route",
      status: decisionAction(humanDecision),
    });
  }
  if (execution) {
    assertSameCase(route, execution);
    if (!humanDecision && decision?.outcome !== "decision_available") {
      throw new TypeError("DS15-APPROVAL-WITHOUT-EXECUTION");
    }
    if (
      decision &&
      execution.authority_decision_ref !== decision.authority_decision_ref
    ) {
      throw new TypeError("DS15-SAME-CASE-MISMATCH");
    }
    facts.push({
      phase: "executing",
      raw: execution as Readonly<Record<string, unknown>>,
      receiptRef: execution.authority_decision_ref,
      scope: "run_route",
      status: `${execution.status}:${execution.receipt_phase}`,
    });
  }
  if (job) {
    if (
      !execution ||
      job.kind !== "acquisition" ||
      job.job_id !== execution.job_id ||
      job.run_id !== route.run_id
    ) {
      throw new TypeError("DS15-SAME-CASE-MISMATCH");
    }
    facts.push({
      phase: jobPhase(job) === "terminal" ? "terminal" : jobPhase(job),
      raw: job as Readonly<Record<string, unknown>>,
      receiptRef: terminalReceiptRef(job),
      scope: "run_route",
      status: `${job.state}:${jobPhase(job)}`,
    });
  }
  if (growthHistory) {
    const disposition =
      growthHistory.quarantine === "raw_terminal" &&
      growthHistory.world_growth === "no_growth"
        ? "quarantined_no_growth"
        : `${growthHistory.world_growth}:${growthHistory.reentry}`;
    facts.push({
      phase: "world_history",
      raw: growthHistory as Readonly<Record<string, unknown>>,
      scope: "global_n13b_history",
      status: disposition,
    });
  }
  return Object.freeze(facts);
}

function artifactHref(receiptRef: string) {
  return `/api/v1/artifacts/${encodeURIComponent(receiptRef)}`;
}

export function AcquisitionExecutionTimeline(
  props: AcquisitionExecutionTimelineProps,
) {
  const { t } = useI18n();
  const facts = timelineFacts(props);
  return (
    <Card
      className="min-w-0 space-y-4"
      data-testid="acquisition-execution-timeline"
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="eyebrow">
            {t("pages.cycleBoard.acquisition.action.eyebrow")}
          </p>
          <h2 className="text-xl font-semibold">
            {t("pages.cycleBoard.acquisition.action.title")}
          </h2>
        </div>
        <Badge kind="warn">{props.route.authority_badge}</Badge>
      </header>

      <div data-testid="acquisition-timeline-time-semantics">
        <TimeSemanticsLabel />
      </div>

      <p className="font-mono text-sm" aria-live="polite">
        {facts.at(-1)?.status}
      </p>

      <ol
        className="space-y-3"
        aria-label={t("pages.cycleBoard.acquisition.action.timelineAria")}
      >
        {facts.map((fact, index) => (
          <li
            className="min-w-0 rounded-md border p-3"
            data-acquisition-phase={fact.phase}
            data-acquisition-scope={fact.scope}
            data-testid="acquisition-timeline-fact"
            key={`${fact.scope}:${fact.phase}:${String(index)}`}
          >
            <div className="flex min-w-0 flex-wrap items-center justify-between gap-2 [&>*]:max-w-full [&>*]:min-w-0 [&>*]:break-all">
              <strong>{fact.phase}</strong>
              <Badge kind={fact.scope === "run_route" ? "outline" : "warn"}>
                {fact.status}
              </Badge>
            </div>
            {fact.phase === "refusal_with_path" ? (
              <dl className="mt-2 grid gap-2 text-sm sm:grid-cols-2">
                <div>
                  <dt>{t("pages.cycleBoard.acquisition.action.cost")}</dt>
                  <dd>
                    {String(
                      props.route.cost_basis.total_amount ?? "not_established",
                    )}
                  </dd>
                </div>
                <div>
                  <dt>
                    {t("pages.cycleBoard.acquisition.action.qualification")}
                  </dt>
                  <dd>
                    {props.route.qualification_status} ·{" "}
                    {props.route.qualification_predicate} ·{" "}
                    {props.route.qualification_reason}
                  </dd>
                </div>
                <div>
                  <dt>{t("pages.cycleBoard.acquisition.action.owner")}</dt>
                  <dd>{t("pages.cycleBoard.acquisition.action.ownerValue")}</dd>
                </div>
                <div>
                  <dt>
                    {t(
                      "pages.cycleBoard.acquisition.action.appointmentWouldEstablish",
                    )}
                  </dt>
                  <dd>
                    {t("pages.cycleBoard.acquisition.action.appointmentEffect")}
                  </dd>
                </div>
              </dl>
            ) : null}
            {fact.phase === "world_history" && props.growthHistory ? (
              <p className="mt-2 font-mono text-sm">
                {props.growthHistory.quarantine} ·{" "}
                {props.growthHistory.world_growth} ·{" "}
                {props.growthHistory.reentry} ·{" "}
                {props.growthHistory.epoch_qualification.code}
              </p>
            ) : null}
            {fact.phase !== "world_history" &&
            fact.phase !== "refusal_with_path" ? (
              <p
                className="mt-2 font-mono text-sm"
                data-testid={
                  fact.raw.kind === "acquisition"
                    ? "acquisition-job-phase"
                    : undefined
                }
              >
                {fact.status}
              </p>
            ) : null}
            {fact.receiptRef ? (
              <a
                className="mt-2 block font-mono text-xs break-all underline"
                href={artifactHref(fact.receiptRef)}
              >
                {fact.receiptRef}
              </a>
            ) : null}
            <pre
              className="mt-2 max-w-full overflow-x-auto text-xs break-all whitespace-pre-wrap"
              data-acquisition-machine-fact={fact.phase}
            >
              {JSON.stringify(fact.raw)}
            </pre>
          </li>
        ))}
      </ol>
    </Card>
  );
}
