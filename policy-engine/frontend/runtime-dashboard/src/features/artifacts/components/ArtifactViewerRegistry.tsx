import { lazy, Suspense, type ReactNode } from "react";
import { Link } from "react-router-dom";

import type { ArtifactView } from "@/features/artifacts/domain/searchParams";
import { useI18n } from "@/i18n/LocaleProvider";
import {
  asArray,
  asNumber,
  asRecord,
  asString,
  toDisplayLabel,
} from "@/lib/parsing";
import { formatNumber } from "@/lib/utils";
import { Badge, JsonPreview } from "@/shared/ui";

const DecisionCardView = lazy(() => import("./DecisionCardView"));
const SimulationResultsViewer = lazy(
  () => import("./simulation/SimulationResultsViewer"),
);
const TrinityCard = lazy(() => import("./trinity/TrinityCard"));

type ArtifactViewerProps = {
  kind: string;
  preview: unknown;
  view?: ArtifactView;
  onViewChange?: (nextView: ArtifactView) => void;
};

type ArtifactViewerSummaryItem = {
  label: string;
  value: ReactNode;
};

type ArtifactViewerRelatedRef = {
  label: string;
  artifactId: string;
};

export type ArtifactViewerDescriptor = {
  title: string;
  summaryItems: ArtifactViewerSummaryItem[];
  relatedRefs: ArtifactViewerRelatedRef[];
  node: ReactNode;
};

function ArtifactViewerFallback({ messageKey }: { messageKey: string }) {
  const { t } = useI18n();
  return <p className="text-muted text-sm">{t(messageKey)}</p>;
}

function SummaryGrid({ items }: { items: ArtifactViewerSummaryItem[] }) {
  if (!items.length) {
    return null;
  }

  return (
    <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => (
        <div
          key={item.label}
          className="bg-surface/80 border-line rounded-xl border p-3 text-sm"
        >
          <p className="text-muted text-xs uppercase">{item.label}</p>
          <div className="mt-1 font-semibold">{item.value}</div>
        </div>
      ))}
    </div>
  );
}

function TextList({ title, items }: { title: string; items: string[] }) {
  if (!items.length) {
    return null;
  }
  return (
    <div className="bg-surface/80 border-line rounded-2xl border p-3 text-sm">
      <p className="text-muted mb-2 text-xs font-semibold tracking-wide uppercase">
        {title}
      </p>
      <ul className="space-y-1">
        {items.map((item) => (
          <li key={item}>- {item}</li>
        ))}
      </ul>
    </div>
  );
}

function GenericObjectHighlights({ preview }: { preview: unknown }) {
  const record = asRecord(preview);
  if (!record) {
    return null;
  }
  const entries = Object.entries(record).slice(0, 6);
  if (entries.length === 0) {
    return null;
  }
  return (
    <SummaryGrid
      items={entries.map(([key, value]) => ({
        label: toDisplayLabel(key),
        value:
          typeof value === "object" ? JSON.stringify(value) : String(value),
      }))}
    />
  );
}

function ArtifactViewerShell({
  kind,
  title,
  summaryItems,
  relatedRefs,
  preview,
  children,
}: {
  kind: string;
  title: string;
  summaryItems: ArtifactViewerSummaryItem[];
  relatedRefs: ArtifactViewerRelatedRef[];
  preview: unknown;
  children: ReactNode;
}) {
  const { t } = useI18n();

  return (
    <div className="space-y-3">
      <div className="bg-panel/70 border-line flex flex-wrap items-center justify-between gap-3 rounded-2xl border p-3">
        <div>
          <p className="text-muted text-xs tracking-wide uppercase">
            {t("pages.artifacts.title")}
          </p>
          <p className="mt-1 text-lg font-semibold">{title}</p>
          <p className="text-muted mt-1 text-xs">{kind}</p>
        </div>
        {relatedRefs.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {relatedRefs.slice(0, 4).map((ref) => (
              <Link
                key={`${ref.label}:${ref.artifactId}`}
                to={`/artifacts/${ref.artifactId}`}
                className="border-line bg-surface rounded-full border px-3 py-1 text-xs font-semibold"
              >
                {ref.label}
              </Link>
            ))}
          </div>
        ) : null}
      </div>
      <SummaryGrid items={summaryItems} />
      {children}
      <details className="bg-surface/80 border-line rounded-2xl border p-3">
        <summary className="cursor-pointer text-sm font-semibold">
          {t("pages.artifacts.viewers.rawPayload")}
        </summary>
        <div className="mt-3">
          <JsonPreview data={preview} />
        </div>
      </details>
    </div>
  );
}

function extractRelatedRefs(preview: unknown): ArtifactViewerRelatedRef[] {
  const record = asRecord(preview);
  if (!record) {
    return [];
  }

  const relatedRefs: ArtifactViewerRelatedRef[] = [];
  const seen = new Set<string>();

  function push(label: string, artifactId: string | null) {
    if (!artifactId || seen.has(artifactId)) {
      return;
    }
    seen.add(artifactId);
    relatedRefs.push({ label, artifactId });
  }

  for (const [key, value] of Object.entries(record)) {
    const directRef = asRecord(value);
    if (key.endsWith("_ref") && directRef) {
      push(toDisplayLabel(key), asString(directRef.artifact_id));
      continue;
    }
    if (key === "links" && directRef) {
      for (const [linkKey, linkValue] of Object.entries(directRef)) {
        push(
          toDisplayLabel(linkKey),
          asString(asRecord(linkValue)?.artifact_id),
        );
      }
      continue;
    }
    if (key === "artifacts" && directRef) {
      for (const [artifactKey, artifactValue] of Object.entries(directRef)) {
        push(toDisplayLabel(artifactKey), asString(artifactValue));
      }
      continue;
    }
    if (key === "inputs" && directRef) {
      for (const [inputKey, inputValue] of Object.entries(directRef)) {
        const refId =
          typeof inputValue === "string"
            ? inputValue
            : asString(asRecord(inputValue)?.artifact_id);
        push(toDisplayLabel(inputKey), refId);
      }
    }
  }

  return relatedRefs;
}

function PreflightReportViewer({ preview }: { preview: unknown }) {
  const { t, label } = useI18n();
  const report = asRecord(preview);
  const diagnostics = asArray(report?.diagnostics)
    .map((item) => asRecord(item))
    .filter(Boolean) as Array<Record<string, unknown>>;
  const notes = asArray(report?.notes)
    .map((item) => asString(item))
    .filter((item): item is string => Boolean(item));
  const grouped = diagnostics.reduce<Record<string, number>>(
    (acc, diagnostic) => {
      const severity = asString(diagnostic.severity) ?? "info";
      acc[severity] = (acc[severity] ?? 0) + 1;
      return acc;
    },
    {},
  );

  return (
    <div className="space-y-3">
      <SummaryGrid
        items={[
          {
            label: t("pages.artifacts.viewers.readyToRun"),
            value: (
              <Badge kind={report?.ready_to_run === true ? "ok" : "warn"}>
                {report?.ready_to_run === true
                  ? t("common.ready")
                  : t("common.blocked")}
              </Badge>
            ),
          },
          {
            label: t("pages.artifacts.viewers.diagnostics"),
            value: formatNumber(diagnostics.length),
          },
          {
            label: t("pages.artifacts.viewers.severitySplit"),
            value:
              Object.entries(grouped)
                .map(
                  ([severity, count]) =>
                    `${label("governanceSeverity", severity, severity)} ${count}`,
                )
                .join(" · ") || "-",
          },
          {
            label: t("pages.artifacts.viewers.notes"),
            value: formatNumber(notes.length),
          },
        ]}
      />

      {diagnostics.length > 0 ? (
        <div className="space-y-2">
          {diagnostics.map((diagnostic, index) => {
            const hints = asArray(diagnostic.replanning_hints)
              .map((item) => asString(item))
              .filter((item): item is string => Boolean(item));
            return (
              <div
                key={`${asString(diagnostic.code) ?? "diagnostic"}-${index}`}
                className="bg-surface/80 border-line rounded-2xl border p-3 text-sm"
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="font-semibold">
                    {asString(diagnostic.code) ?? `diagnostic_${index + 1}`}
                  </p>
                  <Badge kind="warn">
                    {label(
                      "governanceSeverity",
                      asString(diagnostic.severity),
                      asString(diagnostic.severity) ?? "info",
                    )}
                  </Badge>
                </div>
                <p className="mt-2">
                  {asString(diagnostic.message) ??
                    t("pages.artifacts.viewers.noDiagnosticMessage")}
                </p>
                {hints.length > 0 ? (
                  <p className="text-muted mt-2 text-xs">
                    {t("pages.artifacts.viewers.hints", {
                      hints: hints.join(" · "),
                    })}
                  </p>
                ) : null}
              </div>
            );
          })}
        </div>
      ) : null}

      <TextList title={t("pages.artifacts.viewers.notes")} items={notes} />
    </div>
  );
}

function EvaluatorReportViewer({ preview }: { preview: unknown }) {
  const { t, label } = useI18n();
  const report = asRecord(preview);
  const scores = asRecord(report?.scores);
  const reasons = asArray(report?.reasons)
    .map((item) => asString(item))
    .filter((item): item is string => Boolean(item));
  const replanningHints = asArray(report?.replanning_hints)
    .map((item) => asString(item))
    .filter((item): item is string => Boolean(item));
  const diagnostics = asArray(report?.diagnostics)
    .map((item) => asRecord(item))
    .filter(Boolean) as Array<Record<string, unknown>>;

  return (
    <div className="space-y-3">
      <SummaryGrid
        items={[
          {
            label: t("pages.artifacts.viewers.verdict"),
            value: (
              <Badge
                kind={asString(report?.verdict) === "APPROVE" ? "ok" : "warn"}
              >
                {label(
                  "evaluatorVerdicts",
                  asString(report?.verdict),
                  asString(report?.verdict) ?? t("common.unknown"),
                )}
              </Badge>
            ),
          },
          {
            label: t("pages.artifacts.viewers.totalScore"),
            value: formatNumber(asNumber(scores?.total_score), {
              maximumFractionDigits: 3,
            }),
          },
          {
            label: t("pages.artifacts.viewers.kpiScore"),
            value: formatNumber(asNumber(scores?.kpi_score), {
              maximumFractionDigits: 3,
            }),
          },
          {
            label: t("pages.artifacts.viewers.budgetScore"),
            value: formatNumber(asNumber(scores?.budget_score), {
              maximumFractionDigits: 3,
            }),
          },
        ]}
      />
      <TextList title={t("pages.artifacts.viewers.reasons")} items={reasons} />
      <TextList
        title={t("pages.artifacts.viewers.replanningHints")}
        items={replanningHints}
      />
      {diagnostics.length > 0 ? (
        <div className="space-y-2">
          {diagnostics.map((diagnostic, index) => (
            <div
              key={`${asString(diagnostic.code) ?? "diagnostic"}-${index}`}
              className="bg-surface/80 border-line rounded-2xl border p-3 text-sm"
            >
              <p className="font-semibold">
                {asString(diagnostic.code) ?? `diagnostic_${index + 1}`}
              </p>
              <p className="mt-1">{asString(diagnostic.message) ?? "-"}</p>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function ReproducibilityManifestViewer({ preview }: { preview: unknown }) {
  const { t } = useI18n();
  const manifest = asRecord(preview);
  const whyPartial = asArray(manifest?.why_partial)
    .map((item) => asString(item))
    .filter((item): item is string => Boolean(item));
  const missingRefs = asArray(manifest?.missing_refs)
    .map((item) => asString(item))
    .filter((item): item is string => Boolean(item));

  return (
    <div className="space-y-3">
      <SummaryGrid
        items={[
          {
            label: t("pages.artifacts.viewers.readiness"),
            value: asString(manifest?.readiness) ?? "-",
          },
          {
            label: t("pages.artifacts.viewers.determinism"),
            value: asString(manifest?.determinism_tier) ?? "-",
          },
          {
            label: t("pages.artifacts.viewers.seed"),
            value: asString(manifest?.seed) ?? "-",
          },
          {
            label: t("pages.artifacts.viewers.planHash"),
            value: asString(manifest?.plan_hash) ?? "-",
          },
          {
            label: t("pages.artifacts.viewers.dataSnapshotHash"),
            value: asString(manifest?.data_snapshot_hash) ?? "-",
          },
          {
            label: t("pages.artifacts.viewers.bindingsHash"),
            value: asString(manifest?.input_bindings_hash) ?? "-",
          },
          {
            label: t("pages.artifacts.viewers.registryHash"),
            value: asString(manifest?.registry_hash) ?? "-",
          },
          {
            label: t("pages.artifacts.viewers.methodCatalogHash"),
            value: asString(manifest?.method_catalog_hash) ?? "-",
          },
        ]}
      />
      <TextList
        title={t("pages.artifacts.viewers.whyPartial")}
        items={whyPartial}
      />
      <TextList
        title={t("pages.artifacts.viewers.missingRefs")}
        items={missingRefs}
      />
      {asString(manifest?.suggested_next_step) ? (
        <div className="bg-surface/80 border-line rounded-2xl border p-3 text-sm">
          <p className="text-muted text-xs uppercase">
            {t("pages.artifacts.viewers.suggestedNextStep")}
          </p>
          <p className="mt-1 font-semibold">
            {asString(manifest?.suggested_next_step)}
          </p>
        </div>
      ) : null}
    </div>
  );
}

function LegalReportViewer({ preview }: { preview: unknown }) {
  const { t } = useI18n();
  const report = asRecord(preview);
  const issues = asArray(report?.issues)
    .map((item) => asRecord(item))
    .filter(Boolean) as Array<Record<string, unknown>>;
  const recommendations = asArray(report?.recommendations)
    .map((item) => asString(item))
    .filter((item): item is string => Boolean(item));

  return (
    <div className="space-y-3">
      <SummaryGrid
        items={[
          {
            label: t("pages.artifacts.viewers.status"),
            value: asString(report?.status) ?? asString(report?.verdict) ?? "-",
          },
          {
            label: t("pages.artifacts.viewers.jurisdiction"),
            value: asString(report?.jurisdiction) ?? "-",
          },
          {
            label: t("pages.artifacts.viewers.issues"),
            value: formatNumber(issues.length),
          },
          {
            label: t("pages.artifacts.viewers.norms"),
            value: formatNumber(asArray(report?.norms).length),
          },
        ]}
      />
      {issues.length > 0 ? (
        <div className="space-y-2">
          {issues.map((issue, index) => (
            <div
              key={`${asString(issue.code) ?? "issue"}-${index}`}
              className="bg-surface/80 border-line rounded-2xl border p-3 text-sm"
            >
              <p className="font-semibold">
                {asString(issue.code) ?? `issue_${index + 1}`}
              </p>
              <p className="mt-1">
                {asString(issue.message) ??
                  t("pages.artifacts.viewers.noDiagnosticMessage")}
              </p>
            </div>
          ))}
        </div>
      ) : null}
      <TextList
        title={t("pages.artifacts.viewers.recommendations")}
        items={recommendations}
      />
    </div>
  );
}

function QualityReportViewer({ preview }: { preview: unknown }) {
  const { t } = useI18n();
  const report = asRecord(preview);
  const metrics = asRecord(report?.metrics);
  const gates = asRecord(report?.gates);
  const violations = asArray(report?.violations);

  return (
    <div className="space-y-3">
      <SummaryGrid
        items={[
          {
            label: t("pages.artifacts.viewers.qualityScore"),
            value: formatNumber(asNumber(report?.quality_score), {
              maximumFractionDigits: 3,
            }),
          },
          {
            label: t("pages.artifacts.viewers.coverage"),
            value: formatNumber(asNumber(metrics?.coverage), {
              maximumFractionDigits: 3,
            }),
          },
          {
            label: t("pages.artifacts.viewers.completeness"),
            value: formatNumber(asNumber(metrics?.completeness), {
              maximumFractionDigits: 3,
            }),
          },
          {
            label: t("pages.artifacts.viewers.gateStatus"),
            value: asString(gates?.status) ?? asString(report?.status) ?? "-",
          },
          {
            label: t("pages.artifacts.viewers.thresholds"),
            value: Object.keys(metrics ?? {}).length
              ? Object.keys(metrics ?? {}).join(", ")
              : "-",
          },
          {
            label: t("pages.artifacts.viewers.coverageGaps"),
            value: formatNumber(violations.length),
          },
        ]}
      />
      <GenericObjectHighlights preview={preview} />
    </div>
  );
}

function CausalEffectReportViewer({ preview }: { preview: unknown }) {
  const { t } = useI18n();
  const report = asRecord(preview);
  const transport = asRecord(report?.transport_result);
  const assumptions = asArray(transport?.assumptions)
    .map((item) => asString(item))
    .filter((item): item is string => Boolean(item));
  const blockers = asArray(transport?.portability_blockers)
    .map((item) => asString(item))
    .filter((item): item is string => Boolean(item));

  return (
    <div className="space-y-3">
      <SummaryGrid
        items={[
          {
            label: t("pages.artifacts.viewers.method"),
            value:
              asString(report?.method) ?? asString(report?.method_id) ?? "-",
          },
          {
            label: t("pages.artifacts.viewers.estimand"),
            value: asString(report?.estimand) ?? "-",
          },
          {
            label: t("pages.artifacts.viewers.effect"),
            value: formatNumber(asNumber(report?.effect_estimate), {
              maximumFractionDigits: 4,
            }),
          },
          {
            label: t("pages.artifacts.viewers.status"),
            value: asString(report?.status) ?? "-",
          },
          {
            label: t("pages.artifacts.viewers.transport"),
            value: asString(transport?.status) ?? "-",
          },
          {
            label: t("pages.artifacts.viewers.stdError"),
            value: formatNumber(asNumber(report?.standard_error), {
              maximumFractionDigits: 4,
            }),
          },
        ]}
      />
      <TextList
        title={t("pages.artifacts.viewers.assumptions")}
        items={assumptions}
      />
      <TextList
        title={t("pages.artifacts.viewers.portabilityBlockers")}
        items={blockers}
      />
    </div>
  );
}

const SIMULATION_KINDS = new Set<string>([
  "scientist.decision_packet",
  "scientist.metric_validation_report",
  "foundry.metrics",
  "foundry.simulation_result",
  "scientist.simulation_results",
  "foundry.calibration_report",
  "ir.distributional_report",
  "ir.uncertainty_envelope",
]);

function isSimulationKind(kind: string): boolean {
  return (
    SIMULATION_KINDS.has(kind) ||
    kind.includes("simulation") ||
    kind.includes("calibration")
  );
}

function hasTypedViewer(kind: string): boolean {
  return (
    kind === "ir.trinity_bundle" ||
    kind === "scientist.decision_card" ||
    kind === "scientist.decision_packet" ||
    isSimulationKind(kind) ||
    kind === "scientist.preflight_report" ||
    kind === "scientist.evaluator_report" ||
    kind === "scientist.reproducibility_manifest" ||
    kind === "lex.legal_report" ||
    kind === "fabric.quality_report" ||
    kind === "ir.causal_effect_report"
  );
}

function buildTypedViewerNode({
  kind,
  onViewChange,
  preview,
  view,
}: ArtifactViewerProps): ReactNode {
  if (kind === "ir.trinity_bundle") {
    return (
      <Suspense
        fallback={
          <ArtifactViewerFallback messageKey="pages.artifacts.viewers.loadingTrinity" />
        }
      >
        <TrinityCard payload={preview} />
      </Suspense>
    );
  }

  if (
    kind === "scientist.decision_card" ||
    kind === "scientist.decision_packet"
  ) {
    return (
      <Suspense
        fallback={
          <ArtifactViewerFallback messageKey="pages.artifacts.viewers.loadingDecision" />
        }
      >
        <DecisionCardView
          payload={preview}
          artifactKind={kind}
          viewMode={view}
          onViewModeChange={onViewChange}
        />
      </Suspense>
    );
  }

  if (isSimulationKind(kind)) {
    return (
      <Suspense
        fallback={
          <ArtifactViewerFallback messageKey="pages.artifacts.viewers.loadingSimulation" />
        }
      >
        <SimulationResultsViewer artifactKind={kind} preview={preview} />
      </Suspense>
    );
  }

  if (kind === "scientist.preflight_report") {
    return <PreflightReportViewer preview={preview} />;
  }

  if (kind === "scientist.evaluator_report") {
    return <EvaluatorReportViewer preview={preview} />;
  }

  if (kind === "scientist.reproducibility_manifest") {
    return <ReproducibilityManifestViewer preview={preview} />;
  }

  if (kind === "lex.legal_report") {
    return <LegalReportViewer preview={preview} />;
  }

  if (kind === "fabric.quality_report") {
    return <QualityReportViewer preview={preview} />;
  }

  if (kind === "ir.causal_effect_report") {
    return <CausalEffectReportViewer preview={preview} />;
  }

  return <JsonPreview data={preview} />;
}

function buildSummaryItems(
  kind: string,
  preview: unknown,
  t: ReturnType<typeof useI18n>["t"],
): ArtifactViewerSummaryItem[] {
  const record = asRecord(preview);
  if (!record) {
    return [];
  }

  if (kind === "scientist.preflight_report") {
    return [
      {
        label: t("pages.artifacts.viewers.readyToRun"),
        value: String(record.ready_to_run ?? "-"),
      },
      {
        label: t("pages.artifacts.viewers.diagnostics"),
        value: formatNumber(asArray(record.diagnostics).length),
      },
      {
        label: t("pages.artifacts.viewers.notes"),
        value: formatNumber(asArray(record.notes).length),
      },
    ];
  }

  if (kind === "scientist.evaluator_report") {
    const scores = asRecord(record.scores);
    return [
      {
        label: t("pages.artifacts.viewers.verdict"),
        value: asString(record.verdict) ?? "-",
      },
      {
        label: t("pages.artifacts.viewers.totalScore"),
        value: formatNumber(asNumber(scores?.total_score), {
          maximumFractionDigits: 3,
        }),
      },
      {
        label: t("pages.artifacts.viewers.kpiScore"),
        value: formatNumber(asNumber(scores?.kpi_score), {
          maximumFractionDigits: 3,
        }),
      },
      {
        label: t("pages.artifacts.viewers.budgetScore"),
        value: formatNumber(asNumber(scores?.budget_score), {
          maximumFractionDigits: 3,
        }),
      },
    ];
  }

  if (kind === "scientist.reproducibility_manifest") {
    return [
      {
        label: t("pages.artifacts.viewers.readiness"),
        value: asString(record.readiness) ?? "-",
      },
      {
        label: t("pages.artifacts.viewers.seed"),
        value: asString(record.seed) ?? "-",
      },
      {
        label: t("pages.artifacts.viewers.planHash"),
        value: asString(record.plan_hash) ?? "-",
      },
      {
        label: t("pages.artifacts.viewers.missingRefs"),
        value: formatNumber(asArray(record.missing_refs).length),
      },
    ];
  }

  if (kind === "lex.legal_report") {
    return [
      {
        label: t("pages.artifacts.viewers.status"),
        value: asString(record.status) ?? "-",
      },
      {
        label: t("pages.artifacts.viewers.jurisdiction"),
        value: asString(record.jurisdiction) ?? "-",
      },
      {
        label: t("pages.artifacts.viewers.issues"),
        value: formatNumber(asArray(record.issues).length),
      },
    ];
  }

  if (kind === "fabric.quality_report") {
    const metrics = asRecord(record.metrics);
    return [
      {
        label: t("pages.artifacts.viewers.qualityScore"),
        value: formatNumber(asNumber(record.quality_score), {
          maximumFractionDigits: 3,
        }),
      },
      {
        label: t("pages.artifacts.viewers.coverage"),
        value: formatNumber(asNumber(metrics?.coverage), {
          maximumFractionDigits: 3,
        }),
      },
      {
        label: t("pages.artifacts.viewers.completeness"),
        value: formatNumber(asNumber(metrics?.completeness), {
          maximumFractionDigits: 3,
        }),
      },
    ];
  }

  if (kind === "ir.causal_effect_report") {
    return [
      {
        label: t("pages.artifacts.viewers.method"),
        value: asString(record.method) ?? asString(record.method_id) ?? "-",
      },
      {
        label: t("pages.artifacts.viewers.effect"),
        value: formatNumber(asNumber(record.effect_estimate), {
          maximumFractionDigits: 4,
        }),
      },
      {
        label: t("pages.artifacts.viewers.status"),
        value: asString(record.status) ?? "-",
      },
    ];
  }

  return Object.entries(record)
    .slice(0, 4)
    .map(([key, value]) => ({
      label: toDisplayLabel(key),
      value: typeof value === "object" ? JSON.stringify(value) : String(value),
    }));
}

export function getArtifactViewerDescriptor({
  kind,
  onViewChange,
  preview,
  view,
}: ArtifactViewerProps): ArtifactViewerDescriptor {
  const viewerTitle = kind;
  const relatedRefs = extractRelatedRefs(preview);
  const title = viewerTitle;
  const typedNode = buildTypedViewerNode({ kind, onViewChange, preview, view });

  return {
    title,
    summaryItems: [],
    relatedRefs,
    node: typedNode,
  };
}

function ArtifactViewerDescriptorAdapter({
  kind,
  onViewChange,
  preview,
  view,
}: ArtifactViewerProps) {
  const { t, label } = useI18n();
  const descriptor = getArtifactViewerDescriptor({
    kind,
    onViewChange,
    preview,
    view,
  });
  const title = label("artifactKinds", kind, descriptor.title);
  const summaryItems = buildSummaryItems(kind, preview, t);

  if (!hasTypedViewer(kind)) {
    return descriptor.node;
  }

  return (
    <ArtifactViewerShell
      kind={kind}
      title={title}
      summaryItems={summaryItems}
      relatedRefs={descriptor.relatedRefs}
      preview={preview}
    >
      {descriptor.node}
    </ArtifactViewerShell>
  );
}

export function renderArtifactViewer({
  kind,
  onViewChange,
  preview,
  view,
}: ArtifactViewerProps): ReactNode {
  if (!hasTypedViewer(kind)) {
    return <JsonPreview data={preview} />;
  }

  return (
    <ArtifactViewerDescriptorAdapter
      kind={kind}
      onViewChange={onViewChange}
      preview={preview}
      view={view}
    />
  );
}
