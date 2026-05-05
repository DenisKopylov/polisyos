import { useMemo } from "react";

import InterventionDetail from "@/features/artifacts/components/trinity/InterventionDetail";
import TrinityDiff from "@/features/artifacts/components/trinity/TrinityDiff";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { parseTrinityBundle } from "@/shared/lib/domain/trinity";
import { asRecord } from "@/shared/lib/parsing";
import { Card } from "@/shared/ui";

type TrinityCardProps = {
  payload: unknown;
};

function extractPreviousBundle(payload: unknown): {
  bundle: unknown;
  title: string | null;
} {
  const record = asRecord(payload);
  if (!record) {
    return { bundle: null, title: null };
  }

  const candidates: Array<{ key: string; title: string }> = [
    { key: "previous_trinity_bundle", title: "previous_trinity_bundle" },
    { key: "prior_trinity_bundle", title: "prior_trinity_bundle" },
    { key: "baseline_trinity_bundle", title: "baseline_trinity_bundle" },
    { key: "previous_bundle", title: "previous_bundle" },
    { key: "prior_bundle", title: "prior_bundle" },
  ];

  for (const candidate of candidates) {
    if (record[candidate.key] && typeof record[candidate.key] === "object") {
      return { bundle: record[candidate.key] ?? null, title: candidate.title };
    }
  }

  return { bundle: null, title: null };
}

export default function TrinityCard({ payload }: TrinityCardProps) {
  const { t } = useI18n();
  const bundle = useMemo(() => parseTrinityBundle(payload), [payload]);
  const previousBundle = useMemo(
    () => extractPreviousBundle(payload),
    [payload],
  );
  const resolvedPreviousTitle =
    previousBundle.title ?? t("pages.artifacts.trinity.previousBundle");

  if (!bundle) {
    return (
      <Card>
        <h3 className="mb-2 text-lg font-semibold">
          {t("pages.artifacts.trinity.viewerTitle")}
        </h3>
        <p className="text-muted text-sm">
          {t("pages.artifacts.trinity.invalidPayload")}
        </p>
      </Card>
    );
  }

  return (
    <Card className="space-y-4">
      <div className="border-line flex flex-wrap items-center justify-between gap-2 border-b pb-3">
        <div>
          <h3 className="text-lg font-semibold">
            {t("pages.artifacts.trinity.bundleTitle")}
          </h3>
          <p className="text-muted text-sm">
            {t("pages.artifacts.trinity.schemaVersion", {
              version: bundle.schemaVersion ?? "-",
            })}
          </p>
        </div>
        <div className="bg-canvas/40 border-line text-muted rounded-lg border px-3 py-2 text-xs">
          {t("pages.artifacts.trinity.bundleSummary", {
            how: bundle.model.id,
            what: bundle.policy.id,
            why: bundle.problem.id,
          })}
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <section className="bg-canvas/30 border-line space-y-3 rounded-xl border p-3">
          <div>
            <p className="text-muted text-xs font-semibold uppercase">
              {t("pages.artifacts.trinity.problemFrame")}
            </p>
            <p className="text-sm font-semibold">{bundle.problem.domain}</p>
            {bundle.problem.narrative ? (
              <p className="text-muted mt-1 text-sm">
                {bundle.problem.narrative}
              </p>
            ) : null}
          </div>

          <div>
            <p className="text-muted mb-1 text-xs font-semibold uppercase">
              {t("pages.artifacts.trinity.objectives")}
            </p>
            {bundle.problem.objectives.length > 0 ? (
              <ul className="space-y-1 text-sm">
                {bundle.problem.objectives.map((objective) => (
                  <li
                    key={objective.id}
                    className="border-line bg-panel rounded-lg border p-2"
                  >
                    <p className="font-mono text-xs">{objective.id}</p>
                    <p className="text-muted text-xs">
                      {t("pages.artifacts.trinity.objectiveMeta", {
                        direction: objective.direction,
                        metric: objective.metricId,
                        target: objective.target,
                      })}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted text-sm">
                {t("pages.artifacts.trinity.noObjectives")}
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="border-line bg-panel rounded-lg border p-2">
              <p className="text-muted text-xs uppercase">
                {t("pages.artifacts.trinity.constraints")}
              </p>
              <p className="font-semibold">
                {bundle.problem.constraints.length}
              </p>
            </div>
            <div className="border-line bg-panel rounded-lg border p-2">
              <p className="text-muted text-xs uppercase">
                {t("pages.artifacts.trinity.stakeholders")}
              </p>
              <p className="font-semibold">
                {bundle.problem.stakeholders.length}
              </p>
            </div>
            <div className="border-line bg-panel rounded-lg border p-2">
              <p className="text-muted text-xs uppercase">
                {t("pages.artifacts.trinity.kpis")}
              </p>
              <p className="font-semibold">{bundle.problem.kpiCount}</p>
            </div>
            <div className="border-line bg-panel rounded-lg border p-2">
              <p className="text-muted text-xs uppercase">
                {t("pages.artifacts.trinity.successCriteria")}
              </p>
              <p className="font-semibold">
                {bundle.problem.successCriteriaCount}
              </p>
            </div>
          </div>
        </section>

        <section className="bg-canvas/30 border-line space-y-3 rounded-xl border p-3">
          <div>
            <p className="text-muted text-xs font-semibold uppercase">
              {t("pages.artifacts.trinity.policySpec")}
            </p>
            <p className="text-sm font-semibold">{bundle.policy.id}</p>
            <p className="text-muted text-xs">
              {t("pages.artifacts.trinity.bindingSummary", {
                bindings: bundle.policy.mechanismBindingCount,
                parameters: bundle.policy.parameterCount,
              })}
            </p>
          </div>

          {bundle.policy.interventions.length > 0 ? (
            <div className="space-y-2">
              {bundle.policy.interventions.map((intervention, index) => (
                <InterventionDetail
                  key={intervention.id}
                  intervention={intervention}
                  defaultOpen={index === 0}
                />
              ))}
            </div>
          ) : (
            <p className="text-muted text-sm">
              {t("pages.artifacts.trinity.noInterventions")}
            </p>
          )}

          {bundle.policy.notes.length > 0 ? (
            <div className="border-line bg-panel text-muted rounded-lg border p-2 text-xs">
              {t("pages.artifacts.trinity.notes", {
                value: bundle.policy.notes.join("; "),
              })}
            </div>
          ) : null}
        </section>

        <section className="bg-canvas/30 border-line space-y-3 rounded-xl border p-3">
          <div>
            <p className="text-muted text-xs font-semibold uppercase">
              {t("pages.artifacts.trinity.modelSpec")}
            </p>
            <p className="text-sm font-semibold">{bundle.model.id}</p>
            <p className="text-muted text-xs">
              {bundle.model.fidelityLevel ??
                t("pages.artifacts.trinity.fidelityUnknown")}
              {bundle.model.timeSemanticsLabel
                ? ` · ${bundle.model.timeSemanticsLabel}`
                : ""}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="border-line bg-panel rounded-lg border p-2">
              <p className="text-muted text-xs uppercase">
                {t("pages.artifacts.trinity.agentTypes")}
              </p>
              <p className="font-semibold">{bundle.model.agentTypeCount}</p>
            </div>
            <div className="border-line bg-panel rounded-lg border p-2">
              <p className="text-muted text-xs uppercase">
                {t("pages.artifacts.trinity.envParams")}
              </p>
              <p className="font-semibold">
                {bundle.model.environmentParamCount}
              </p>
            </div>
            <div className="border-line bg-panel rounded-lg border p-2">
              <p className="text-muted text-xs uppercase">
                {t("pages.artifacts.trinity.assumptions")}
              </p>
              <p className="font-semibold">{bundle.model.assumptions.length}</p>
            </div>
            <div className="border-line bg-panel rounded-lg border p-2">
              <p className="text-muted text-xs uppercase">
                {t("pages.artifacts.trinity.calibrated")}
              </p>
              <p className="font-semibold">
                {bundle.model.calibrated === null
                  ? "-"
                  : bundle.model.calibrated
                    ? t("common.yes")
                    : t("common.no")}
              </p>
            </div>
          </div>

          <div className="text-muted space-y-1 text-xs">
            <p className="truncate">
              {t("pages.artifacts.trinity.dataSnapshotRef", {
                value: bundle.model.dataSnapshotRef ?? "-",
              })}
            </p>
            <p className="truncate">
              {t("pages.artifacts.trinity.registryBundleRef", {
                value: bundle.model.registryBundleRef ?? "-",
              })}
            </p>
            <p className="truncate">
              {t("pages.artifacts.trinity.calibrationRef", {
                value: bundle.model.calibrationRef ?? "-",
              })}
            </p>
          </div>

          {bundle.model.assumptions.length > 0 ? (
            <div className="space-y-1">
              {bundle.model.assumptions.slice(0, 5).map((assumption) => (
                <div
                  key={assumption.id}
                  className="border-line bg-panel rounded-lg border p-2"
                >
                  <p className="font-mono text-xs">{assumption.id}</p>
                  <p className="text-muted text-xs">{assumption.type}</p>
                  <p className="text-sm">{assumption.description}</p>
                </div>
              ))}
            </div>
          ) : null}
        </section>
      </div>

      <div className="border-line space-y-2 border-t pt-3">
        <p className="text-muted text-xs font-semibold uppercase">
          {t("pages.artifacts.trinity.diffTitle")}
        </p>
        <TrinityDiff
          currentPayload={payload}
          previousPayload={previousBundle.bundle}
          previousTitle={resolvedPreviousTitle}
        />
      </div>
    </Card>
  );
}
