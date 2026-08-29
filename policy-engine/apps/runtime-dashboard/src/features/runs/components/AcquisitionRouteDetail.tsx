import type { ReactNode } from "react";
import type {
  AcquisitionRouteProjection,
  StructuralRouteProjection,
} from "@polisyos/runtime-api-client";

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
            {t("pages.cycleBoard.acquisition.route.runEyebrow")}
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
          <dd>{props.route.route_status}</dd>
        </div>
        <div>
          <dt className="font-semibold">
            {t("pages.cycleBoard.acquisition.route.voi")}
          </dt>
          <dd>{visible.voiAvailability}</dd>
        </div>
      </dl>
      <section className="space-y-2">
        <h3 className="font-semibold">
          {t("pages.cycleBoard.acquisition.route.costedPlan")}
        </h3>
        <Badge kind="outline">{visible.costAvailability}</Badge>
        <pre className="overflow-x-auto text-xs whitespace-pre-wrap">
          {JSON.stringify(visible.cost, null, 2)}
        </pre>
      </section>
      {visible.actionEligible ? props.action : null}
    </Card>
  );
}
