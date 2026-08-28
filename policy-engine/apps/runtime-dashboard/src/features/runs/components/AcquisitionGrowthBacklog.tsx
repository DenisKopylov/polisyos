import { useMemo, useState } from "react";
import type { AcquisitionBacklogProjection } from "@polisyos/runtime-api-client";

import {
  presentAcquisitionBacklog,
  type AcquisitionBacklogOrder,
} from "@/features/runs/domain/acquisitionRoutePresentation";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Badge, Card } from "@polisyos/atlas-ui";

export function AcquisitionGrowthBacklog({
  backlog,
}: {
  backlog: readonly AcquisitionBacklogProjection[];
}) {
  const { t } = useI18n();
  const [order, setOrder] = useState<AcquisitionBacklogOrder>("server_rank");
  const visible = useMemo(
    () => presentAcquisitionBacklog(backlog, order),
    [backlog, order],
  );

  return (
    <Card
      className="space-y-4 p-4"
      data-acquisition-raw={JSON.stringify(backlog)}
      data-local-order-override={String(visible.localOrderOverride)}
      data-testid="acquisition-growth-backlog"
    >
      <header className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">
            {t("pages.cycleBoard.acquisition.backlog.title")}
          </h2>
          <Badge kind="outline">
            {t("pages.cycleBoard.acquisition.backlog.authorityBoundary")}
          </Badge>
        </div>
        <p className="text-sm font-semibold">
          {t("pages.cycleBoard.acquisition.backlog.zeroScoreBasis", {
            confidenceCount: visible.zeroConfidenceCount,
            scoreCount: visible.zeroScoreCount,
            total: visible.totalCount,
          })}
        </p>
        <p className="text-muted-foreground text-sm">
          {t("pages.cycleBoard.acquisition.backlog.noGradient")}
        </p>
        <p className="text-muted-foreground text-sm">
          {t("pages.cycleBoard.acquisition.backlog.demandSplit", {
            demandOne: visible.demandOneCount,
            demandTwo: visible.demandTwoCount,
          })}
        </p>
        <dl className="grid gap-2 text-sm md:grid-cols-3">
          <div>
            <dt className="font-semibold">
              {t("pages.cycleBoard.acquisition.backlog.voiOwnerFit")}
            </dt>
            <dd className="font-mono">
              {backlog[0]?.voi_owner_fit ?? "not_established"}
            </dd>
          </div>
          <div>
            <dt className="font-semibold">
              {t("pages.cycleBoard.acquisition.backlog.voiOwnerIntegration")}
            </dt>
            <dd className="font-mono">
              {backlog[0]?.voi_owner_integration ?? "not_established"}
            </dd>
          </div>
          <div>
            <dt className="font-semibold">
              {t("pages.cycleBoard.acquisition.backlog.voiOwnerRef")}
            </dt>
            <dd className="font-mono break-all">
              {backlog[0]?.voi_owner_ref ?? "not_established"}
            </dd>
          </div>
        </dl>
      </header>

      <label className="flex flex-wrap items-center gap-2 text-sm font-semibold">
        {t("pages.cycleBoard.acquisition.backlog.orderLabel")}
        <select
          className="border-border bg-background rounded-md border px-2 py-1"
          onChange={(event) =>
            setOrder(event.currentTarget.value as AcquisitionBacklogOrder)
          }
          value={order}
        >
          <option value="server_rank">
            {t("pages.cycleBoard.acquisition.backlog.orderServer")}
          </option>
          <option value="route_demand">
            {t("pages.cycleBoard.acquisition.backlog.orderDemand")}
          </option>
          <option value="variable_id">
            {t("pages.cycleBoard.acquisition.backlog.orderVariable")}
          </option>
        </select>
      </label>
      {visible.localOrderOverride ? (
        <Badge kind="warn">
          {t("pages.cycleBoard.acquisition.backlog.localOverride")}
        </Badge>
      ) : null}

      <ol className="space-y-2">
        {visible.rows.map((row) => (
          <li
            className="border-border grid gap-2 rounded-lg border p-3 text-sm md:grid-cols-5"
            data-acquisition-backlog-row=""
            data-acquisition-raw={JSON.stringify(row)}
            data-variable-id={row.variable_id}
            key={row.variable_id}
          >
            <div>
              <span className="text-muted-foreground block text-xs">
                {t("pages.cycleBoard.acquisition.backlog.serverRank")}
              </span>
              <span>{row.serverRank}</span>
            </div>
            <div className="md:col-span-2">
              <span className="text-muted-foreground block text-xs">
                {t("pages.cycleBoard.acquisition.backlog.variable")}
              </span>
              <span className="font-mono">{row.variable_id}</span>
            </div>
            <div>
              <span className="text-muted-foreground block text-xs">
                {t("pages.cycleBoard.acquisition.backlog.score")}
              </span>
              <span>{row.ranking_score.toFixed(1)}</span>
            </div>
            <div>
              <span className="text-muted-foreground block text-xs">
                {t("pages.cycleBoard.acquisition.backlog.demand")}
              </span>
              <span>{row.route_demand.toFixed(1)}</span>
            </div>
            <div className="md:col-span-5">
              <Badge kind="outline">{row.gap_class}</Badge>
              <span className="ml-2 font-mono text-xs">
                {row.classification_basis}
              </span>
            </div>
          </li>
        ))}
      </ol>
    </Card>
  );
}
