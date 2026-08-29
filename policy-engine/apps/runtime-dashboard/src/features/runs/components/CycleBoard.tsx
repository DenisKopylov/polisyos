import type { ReactNode } from "react";

import type { DepthNCycleBoardProjection } from "@/features/runs/api/useDepthNCycleBoardProjection";
import {
  useAcquisitionGrowth,
  type AcquisitionGrowthProjection,
} from "@/features/runs/api/useAcquisitionRoutes";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { DataFreshnessBadge } from "@/shared/ui/compounds/DataFreshnessBadge";
import { Badge, Button, Card } from "@polisyos/atlas-ui";

import { downloadCycleBoardPacket } from "./cycleBoardExport";
import { AcquisitionGrowthBacklog } from "./AcquisitionGrowthBacklog";
import { AcquisitionPassportPanel } from "./AcquisitionPassportPanel";
import { AcquisitionQuarantineLedger } from "./AcquisitionQuarantineLedger";
import { AcquisitionRouteDetail } from "./AcquisitionRouteDetail";
import { ConnectorAcquisitionScorecard } from "./ConnectorAcquisitionScorecard";
import {
  packetToVisibleCycleBoard,
  type VisibleCycleBoard,
} from "./cycleBoardPresentation";

type Fact =
  | Readonly<{
      availability: "available";
      source_as_of?: string | null;
      source_ref: string;
      value: unknown;
    }>
  | Readonly<{
      availability: "artifact_missing" | "invalid_source" | "not_established";
      owner_route: string;
      reason: string;
    }>;

function raw(value: unknown) {
  return JSON.stringify(value);
}

function JsonValue({ value }: { value: unknown }) {
  if (typeof value === "string" || typeof value === "number") {
    return <span>{String(value)}</span>;
  }
  if (typeof value === "boolean") {
    return <span>{value ? "true" : "false"}</span>;
  }
  if (value == null) {
    return <span>{String(value)}</span>;
  }
  return (
    <pre className="overflow-x-auto text-xs whitespace-pre-wrap">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

function FactField({
  fact,
  fieldId,
  label,
  testId,
}: {
  fact: Fact;
  fieldId: string;
  label: string;
  testId?: string;
}) {
  return (
    <div
      className="border-border space-y-1 rounded-lg border p-2"
      data-availability={fact.availability}
      data-cycle-board-field={fieldId}
      data-cycle-board-raw={raw(fact)}
      data-testid={testId}
    >
      <dt className="text-muted-foreground text-xs font-semibold">{label}</dt>
      {fact.availability === "available" ? (
        <dd className="space-y-1 text-sm">
          <JsonValue value={fact.value} />
          <p className="text-muted-foreground font-mono text-xs">
            {fact.source_ref}
            {fact.source_as_of ? ` · ${fact.source_as_of}` : ""}
          </p>
        </dd>
      ) : (
        <dd className="space-y-1 text-sm">
          <Badge kind="outline">{fact.availability}</Badge>
          <p>{fact.reason}</p>
          <p className="text-muted-foreground font-mono text-xs">
            {fact.owner_route}
          </p>
        </dd>
      )}
    </div>
  );
}

function GapCard({
  children,
  exhaustive,
  gap,
  gapKind,
  knownRowCount,
  testId,
}: {
  children: ReactNode;
  exhaustive?: boolean;
  gap: unknown;
  gapKind: "coverage" | "movement";
  knownRowCount?: number;
  testId: string;
}) {
  return (
    <Card
      className="space-y-3 p-4"
      data-cycle-board-gap={gapKind}
      data-cycle-board-raw={raw(gap)}
      data-exhaustive={exhaustive == null ? undefined : String(exhaustive)}
      data-known-row-count={knownRowCount}
      data-testid={testId}
    >
      {children}
    </Card>
  );
}

function CycleBoardRow({ row }: { row: VisibleCycleBoard["rows"][number] }) {
  const { t } = useI18n();
  return (
    <article
      className="border-border space-y-4 rounded-xl border p-4"
      data-cycle-board-raw={raw(row)}
      data-cycle-board-row=""
      data-row-id={row.rowId}
      data-testid="cycle-board-row"
    >
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-muted-foreground text-xs">{row.cohort}</p>
          <h3 className="font-semibold">{row.rowId}</h3>
          <p className="text-muted-foreground text-sm">{row.domainRole}</p>
        </div>
        <div className="flex flex-wrap gap-1">
          {row.responsibleSlices.map((slice) => (
            <Badge key={slice} kind="outline">
              {slice}
            </Badge>
          ))}
        </div>
      </header>

      <dl className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <FactField
          fact={row.searchTerminalKind}
          fieldId="searchTerminalKind"
          label={t("pages.cycleBoard.columns.searchTerminal")}
          testId="cycle-board-search-terminal"
        />
        <FactField
          fact={row.lifecycleTerminality}
          fieldId="lifecycleTerminality"
          label={t("pages.cycleBoard.columns.lifecycleTerminality")}
          testId="cycle-board-lifecycle-terminality"
        />
        <FactField
          fact={row.structuralEvidenceClass}
          fieldId="structuralEvidenceClass"
          label={t("pages.cycleBoard.columns.evidenceClass")}
        />
        <FactField
          fact={row.weakestLinks}
          fieldId="weakestLinks"
          label={t("pages.cycleBoard.columns.weakestLinks")}
        />
        <FactField
          fact={row.missingLink}
          fieldId="missingLink"
          label={t("pages.cycleBoard.columns.missingLink")}
        />
        <FactField
          fact={row.acquisitionRoute}
          fieldId="acquisitionRoute"
          label={t("pages.cycleBoard.columns.acquisitionRoute")}
          testId="cycle-board-acquisition-route"
        />
        <FactField
          fact={row.acquisitionEconomics}
          fieldId="acquisitionEconomics"
          label={t("pages.cycleBoard.columns.acquisitionEconomics")}
          testId="cycle-board-acquisition-economics"
        />
        <FactField
          fact={row.generationCycleRunId}
          fieldId="generationCycleRunId"
          label={t("pages.cycleBoard.columns.runId")}
        />
        <FactField
          fact={row.designProblem}
          fieldId="designProblem"
          label={t("pages.cycleBoard.columns.designProblem")}
        />
        <FactField
          fact={row.surfaceReadiness}
          fieldId="surfaceReadiness"
          label={t("pages.cycleBoard.columns.surfaceReadiness")}
        />
      </dl>

      <details>
        <summary className="cursor-pointer text-sm font-semibold">
          {t("pages.cycleBoard.stageTrace")}
        </summary>
        <FactField
          fact={row.stageTraceHref}
          fieldId="stageTraceHref"
          label={t("pages.cycleBoard.columns.stageTrace")}
        />
        {row.stageTraceHref.availability === "available" ? (
          <a
            className="text-accent text-sm underline"
            href={row.stageTraceHref.value}
          >
            {t("pages.cycleBoard.openStageTrace")}
          </a>
        ) : null}
      </details>

      <section
        className="space-y-1"
        data-cycle-board-field="public-safe-explanation"
        data-cycle-board-raw={raw({
          explanation_code: row.explanationCode,
          explanation_inputs: row.explanationInputs,
        })}
      >
        <h4 className="text-sm font-semibold">
          {t("pages.cycleBoard.columns.explanation")}
        </h4>
        <code className="text-xs">{row.explanationCode}</code>
        <JsonValue value={row.explanationInputs} />
      </section>

      {row.movementRecords.map((movement, index) => (
        <div
          data-cycle-board-movement=""
          data-cycle-board-raw={raw(movement)}
          data-testid="cycle-board-movement"
          key={`${row.rowId}:movement:${index}`}
        >
          <JsonValue value={movement} />
        </div>
      ))}
    </article>
  );
}

function LoadedAcquisitionGrowth({
  projection,
}: {
  projection: AcquisitionGrowthProjection;
}) {
  const { t } = useI18n();
  const { payload } = projection;
  return (
    <section
      className="space-y-4"
      data-acquisition-growth-packet=""
      data-acquisition-raw={JSON.stringify(projection.packet)}
      data-testid="acquisition-growth-surface"
    >
      <header className="space-y-1">
        <p className="eyebrow">{t("pages.cycleBoard.acquisition.eyebrow")}</p>
        <h2 className="text-xl font-semibold">
          {t("pages.cycleBoard.acquisition.title")}
        </h2>
        <p className="text-muted-foreground">
          {t("pages.cycleBoard.acquisition.subtitle")}
        </p>
      </header>

      <dl className="grid gap-2 text-sm sm:grid-cols-2 xl:grid-cols-6">
        {(
          [
            ["familyScorecards", payload.summary.family_scorecard_count],
            ["networkCalls", payload.summary.actual_network_call_count],
            ["selectedRecords", payload.summary.selected_record_count],
            ["metricResolutions", payload.summary.metric_resolution_count],
            ["backlogRows", payload.summary.backlog_count],
            ["structuralRoutes", payload.summary.structural_route_count],
          ] as const
        ).map(([label, value]) => (
          <div className="border-border rounded-lg border p-2" key={label}>
            <dt className="text-muted-foreground text-xs">
              {t(`pages.cycleBoard.acquisition.summary.${label}`)}
            </dt>
            <dd className="font-mono text-lg font-semibold">{value}</dd>
          </div>
        ))}
      </dl>

      <div className="grid gap-4 xl:grid-cols-2">
        <ConnectorAcquisitionScorecard
          carrierLiveness={payload.carrier_liveness}
          familyCount={payload.summary.family_scorecard_count}
        />
        <AcquisitionQuarantineLedger history={payload.n13b_history} />
      </div>
      <AcquisitionPassportPanel history={payload.n13b_history} />
      <AcquisitionGrowthBacklog backlog={payload.backlog} />

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">
          {t("pages.cycleBoard.acquisition.structuralRoutes")}
        </h2>
        <div className="grid gap-3 xl:grid-cols-2">
          {payload.structural_routes.map((route) => (
            <AcquisitionRouteDetail
              key={route.route_id}
              kind="structural"
              route={route}
            />
          ))}
        </div>
      </section>
    </section>
  );
}

function QueriedAcquisitionGrowth() {
  const { t } = useI18n();
  const query = useAcquisitionGrowth();
  if (query.isLoading) {
    return (
      <Card data-testid="acquisition-growth-loading">
        {t("pages.cycleBoard.acquisition.loading")}
      </Card>
    );
  }
  if (query.isError || !query.data) {
    return (
      <Card data-testid="acquisition-growth-unavailable">
        <h2 className="font-semibold">
          {t("pages.cycleBoard.acquisition.unavailableTitle")}
        </h2>
        <p>{t("pages.cycleBoard.acquisition.unavailableBody")}</p>
      </Card>
    );
  }
  return <LoadedAcquisitionGrowth projection={query.data} />;
}

function AcquisitionGrowthSurface({
  projection,
}: {
  projection?: AcquisitionGrowthProjection;
}) {
  return projection ? (
    <LoadedAcquisitionGrowth projection={projection} />
  ) : (
    <QueriedAcquisitionGrowth />
  );
}

export function CycleBoard({
  acquisitionGrowth,
  projection,
}: {
  acquisitionGrowth?: AcquisitionGrowthProjection;
  projection: DepthNCycleBoardProjection;
}) {
  const { t } = useI18n();
  const visible = packetToVisibleCycleBoard(projection.packet);

  return (
    <section
      className="space-y-6"
      data-audiences={projection.packet.intended_audiences.join(",")}
      data-cycle-board-packet=""
      data-cycle-board-raw={raw(visible.packet)}
      data-testid="cycle-board"
    >
      <header className="space-y-2">
        <p className="eyebrow">{t("pages.cycleBoard.eyebrow")}</p>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h1 className="text-2xl font-semibold">
            {t("pages.cycleBoard.title")}
          </h1>
          <Button
            onClick={() => downloadCycleBoardPacket(projection.rawPacketBytes)}
            type="button"
            variant="ghost"
          >
            {t("pages.cycleBoard.exportPacket")}
          </Button>
        </div>
        <p className="text-muted-foreground">
          {t("pages.cycleBoard.subtitle")}
        </p>
        <p className="text-muted-foreground text-xs">
          {t("pages.cycleBoard.projectionObservedAt")}:{" "}
          <span className="font-mono">
            {visible.packet.projectionObservedAt}
          </span>
        </p>
      </header>

      <AcquisitionGrowthSurface projection={acquisitionGrowth} />

      <div className="grid gap-4 xl:grid-cols-2">
        <GapCard
          exhaustive={visible.coverage.exhaustive}
          gap={visible.coverage}
          gapKind="coverage"
          knownRowCount={visible.coverage.known_row_count}
          testId="cycle-board-coverage-gap"
        >
          <h2 className="font-semibold">{t("pages.cycleBoard.coverageGap")}</h2>
          <div>
            <JsonValue value={visible.coverage} />
          </div>
        </GapCard>
        <GapCard
          gap={visible.movementGap}
          gapKind="movement"
          testId="cycle-board-movement-gap"
        >
          <h2 className="font-semibold">{t("pages.cycleBoard.movementGap")}</h2>
          <div>
            <JsonValue value={visible.movementGap} />
          </div>
        </GapCard>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card
          className="space-y-2 p-4"
          data-cycle-board-raw={raw(visible.realizedDs4Disposition)}
          data-cycle-board-summary="ds4-disposition"
        >
          <h2 className="font-semibold">
            {t("pages.cycleBoard.historicalDs4")}
          </h2>
          <JsonValue value={visible.realizedDs4Disposition} />
        </Card>
        <Card
          className="space-y-2 p-4"
          data-cycle-board-raw={raw(visible.historicalProducerAvailability)}
          data-cycle-board-summary="historical-producer-availability"
        >
          <h2 className="font-semibold">
            {t("pages.cycleBoard.historicalAvailability")}
          </h2>
          <JsonValue value={visible.historicalProducerAvailability} />
        </Card>
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">
          {t("pages.cycleBoard.sources")}
        </h2>
        <div className="grid gap-3 xl:grid-cols-2">
          {visible.sources.map((source) => (
            <Card
              className="space-y-2 p-4"
              data-availability={source.availability}
              data-cycle-board-raw={raw(source)}
              data-cycle-board-source=""
              data-source-id={source.source_id}
              data-testid="cycle-board-source"
              key={source.source_id}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-semibold">{source.source_id}</h3>
                <Badge kind="outline">{source.availability}</Badge>
              </div>
              {source.freshness ? (
                <>
                  <DataFreshnessBadge freshness={source.freshness} />
                  <p className="text-sm">{source.freshness.basis}</p>
                  <p className="text-sm">{source.freshness.state}</p>
                </>
              ) : null}
              <JsonValue value={source} />
            </Card>
          ))}
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">{t("pages.cycleBoard.rows")}</h2>
        {visible.rows.map((row, index) => {
          const previous = visible.rows[index - 1];
          const showCohort = !previous || previous.cohort !== row.cohort;
          return (
            <div className="space-y-3" key={row.rowId}>
              {showCohort ? (
                <h3
                  className="text-base font-semibold"
                  data-cycle-board-cohort=""
                  data-cycle-board-raw={raw({ cohort: row.cohort })}
                >
                  {row.cohort}
                </h3>
              ) : null}
              <CycleBoardRow row={row} />
            </div>
          );
        })}
      </section>
    </section>
  );
}
