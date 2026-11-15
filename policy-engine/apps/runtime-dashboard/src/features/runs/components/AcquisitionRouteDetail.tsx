import type { ReactNode } from "react";
import type { StructuralRouteProjection } from "@polisyos/runtime-api-client";

import type { AcquisitionRouteProjection } from "@/features/runs/api/acquisitionRouteValidators";

import { presentRunAcquisitionRoute } from "@/features/runs/domain/acquisitionRoutePresentation";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { TimeSemanticsLabel } from "@/shared/ui/temporal/TimeSemanticsLabel";
import { Badge, Card } from "@polisyos/atlas-ui";

type AcquisitionRouteDetailProps =
  | Readonly<{
      action?: never;
      kind: "structural";
      route: StructuralRouteProjection;
    }>
  | Readonly<{
      action?: ReactNode;
      kind: "run";
      route: AcquisitionRouteProjection;
    }>;

export function AcquisitionRouteDetail(props: AcquisitionRouteDetailProps) {
  const { t } = useI18n();
  if (props.kind === "structural") {
    return (
      <Card
        className="space-y-3 p-4"
        data-acquisition-raw={JSON.stringify(props.route)}
        data-action-eligibility={props.route.action_eligibility}
        data-testid={`acquisition-structural-route-${props.route.route_id}`}
      >
        <header className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <p className="text-muted-foreground text-xs">
              {t("pages.cycleBoard.acquisition.route.structuralEyebrow")}
            </p>
            <h3 className="font-semibold">{props.route.route_id}</h3>
          </div>
          <Badge kind="warn">{props.route.action_eligibility}</Badge>
        </header>
        <div data-testid="acquisition-route-time-semantics">
          <TimeSemanticsLabel />
        </div>
        <dl className="grid gap-2 text-sm md:grid-cols-2">
          <div>
            <dt className="font-semibold">
              {t("pages.cycleBoard.acquisition.route.gapClass")}
            </dt>
            <dd>{props.route.gap_class}</dd>
          </div>
          <div>
            <dt className="font-semibold">
              {t("pages.cycleBoard.acquisition.route.routeClass")}
            </dt>
            <dd>{props.route.route_class}</dd>
          </div>
          <div>
            <dt className="font-semibold">
              {t("pages.cycleBoard.acquisition.route.witness")}
            </dt>
            <dd>{props.route.witness_kind}</dd>
          </div>
          <div>
            <dt className="font-semibold">
              {t("pages.cycleBoard.acquisition.route.missingLink")}
            </dt>
            <dd>{props.route.missing_link}</dd>
          </div>
        </dl>
        <p className="text-muted-foreground text-sm">
          {t("pages.cycleBoard.acquisition.route.structuralRefusal")}
        </p>
      </Card>
    );
  }

  const visible = presentRunAcquisitionRoute(props.route);
  const worldGrowthLabel = {
    not_established: t(
      "pages.cycleBoard.acquisition.route.growthStatus.notEstablished",
    ),
    no_growth: t("pages.cycleBoard.acquisition.route.growthStatus.noGrowth"),
    admitted_delta: t(
      "pages.cycleBoard.acquisition.route.growthStatus.admittedDelta",
    ),
  }[visible.worldGrowth];
  const priorPaidInput = visible.priorPaidInputAdmission;
  const priorPaidInputRefs = priorPaidInput
    ? [
        { name: "attempt", ref: priorPaidInput.attempt_ref },
        { name: "executingPhase", ref: priorPaidInput.executing_phase_ref },
        { name: "terminal", ref: priorPaidInput.terminal_ref },
        { name: "deferral", ref: priorPaidInput.deferral_ref },
        { name: "negativeReceipt", ref: priorPaidInput.negative_receipt_ref },
        { name: "preparedEpoch", ref: priorPaidInput.prepared_epoch_ref },
        {
          name: "ownerProfile",
          ref: priorPaidInput.owner_declared_profile_ref,
        },
      ]
    : [];
  const historicalCostAmount =
    typeof visible.cost.total_amount === "number"
      ? `${String(visible.cost.currency ?? "USD")} ${visible.cost.total_amount}`
      : "not_established";
  return (
    <Card
      className="space-y-4 p-4"
      data-acquisition-raw={JSON.stringify(props.route)}
      data-action-eligible={String(visible.actionEligible)}
      data-testid="acquisition-route-detail"
    >
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-muted-foreground text-xs">
            {visible.acquisitionMode === "paid_input_admission_only"
              ? t("pages.cycleBoard.acquisition.route.priorPaidInput.title")
              : t("pages.cycleBoard.acquisition.route.runEyebrow")}
          </p>
          <h2 className="font-semibold">{props.route.planner_record_id}</h2>
        </div>
        <Badge kind="warn">{visible.authorityBadge}</Badge>
      </header>
      <div data-testid="acquisition-route-time-semantics">
        <TimeSemanticsLabel />
      </div>
      <dl className="grid gap-3 text-sm md:grid-cols-2">
        <div>
          <dt className="font-semibold">
            {t("pages.cycleBoard.acquisition.route.requirement")}
          </dt>
          <dd className="font-mono break-all">
            {props.route.replay_pins.design_problem_ref}
          </dd>
        </div>
        <div>
          <dt className="font-semibold">
            {t("pages.cycleBoard.acquisition.route.strategy")}
          </dt>
          <dd>{visible.strategy}</dd>
        </div>
        <div>
          <dt className="font-semibold">
            {t("pages.cycleBoard.acquisition.route.status")}
          </dt>
          <dd>
            {props.route.route_status ??
              t("pages.cycleBoard.acquisition.route.statusNotEstablished")}
          </dd>
        </div>
        <div>
          <dt className="font-semibold">
            {t("pages.cycleBoard.acquisition.route.worldGrowth")}
          </dt>
          <dd data-testid="acquisition-route-world-growth">
            {worldGrowthLabel}
          </dd>
        </div>
        <div>
          <dt className="font-semibold">
            {t("pages.cycleBoard.acquisition.route.voi")}
          </dt>
          <dd>{visible.voiAvailability}</dd>
        </div>
      </dl>
      {priorPaidInput ? (
        <section
          aria-label={t(
            "pages.cycleBoard.acquisition.route.priorPaidInput.title",
          )}
          className="border-warning/40 space-y-2 rounded-md border p-4"
          data-testid="prior-paid-input-admission"
          role="status"
        >
          <h3 className="font-semibold">
            {t("pages.cycleBoard.acquisition.route.priorPaidInput.title")}
          </h3>
          <p className="text-sm">
            {t("pages.cycleBoard.acquisition.route.priorPaidInput.disclosure")}
          </p>
          <dl className="grid gap-2 text-sm md:grid-cols-2">
            <div>
              <dt className="font-semibold">
                {t(
                  "pages.cycleBoard.acquisition.route.priorPaidInput.originalAction",
                )}
              </dt>
              <dd className="font-mono break-all">
                {priorPaidInput.original_action_job_id}
              </dd>
            </div>
            {priorPaidInputRefs.map(({ name, ref }) => (
              <div key={name}>
                <dt className="font-semibold">
                  {t(
                    `pages.cycleBoard.acquisition.route.priorPaidInput.refs.${name}`,
                  )}
                </dt>
                <dd className="font-mono break-all">{ref.artifact_id}</dd>
                <dd className="text-muted-foreground text-xs break-all">
                  {ref.kind} · {ref.manifest_profile_sha256}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}
      <section className="space-y-2">
        <h3 className="font-semibold">
          {visible.costMeaning === "historical_prior_paid_basis"
            ? t("pages.cycleBoard.acquisition.route.historicalCostBasis")
            : t("pages.cycleBoard.acquisition.route.costedPlan")}
        </h3>
        {visible.costMeaning === "historical_prior_paid_basis" ? (
          <>
            <Badge kind="warn">
              {t("pages.cycleBoard.acquisition.route.historicalNotOffer")}
            </Badge>
            <p className="text-sm">
              {t("pages.cycleBoard.acquisition.route.historicalCostDisclosure")}
            </p>
            <dl className="grid gap-2 text-sm md:grid-cols-2">
              <div>
                <dt className="font-semibold">
                  {t("pages.cycleBoard.acquisition.route.historicalEstimate")}
                </dt>
                <dd>{historicalCostAmount}</dd>
              </div>
              <div>
                <dt className="font-semibold">
                  {t("pages.cycleBoard.acquisition.route.costBasisRecord")}
                </dt>
                <dd className="font-mono break-all">
                  {String(visible.cost.record_ref ?? "not_established")}
                </dd>
              </div>
            </dl>
          </>
        ) : (
          <>
            <Badge kind="outline">
              {visible.costEstablished ? "available" : "not_established"}
            </Badge>
            <pre className="overflow-x-auto text-xs whitespace-pre-wrap">
              {JSON.stringify(visible.cost, null, 2)}
            </pre>
          </>
        )}
      </section>
      {visible.actionEligible ? props.action : null}
    </Card>
  );
}
