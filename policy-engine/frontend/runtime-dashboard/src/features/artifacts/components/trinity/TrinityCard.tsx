import { useMemo } from "react";

import InterventionDetail from "@/features/artifacts/components/trinity/InterventionDetail";
import TrinityDiff from "@/features/artifacts/components/trinity/TrinityDiff";
import { parseTrinityBundle } from "@/lib/domain/trinity";
import { asRecord } from "@/lib/parsing";
import { Card } from "@/shared/ui";

type TrinityCardProps = {
  payload: unknown;
};

function extractPreviousBundle(payload: unknown): {
  bundle: unknown;
  title: string;
} {
  const record = asRecord(payload);
  if (!record) {
    return { bundle: null, title: "previous bundle" };
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

  return { bundle: null, title: "previous bundle" };
}

export default function TrinityCard({ payload }: TrinityCardProps) {
  const bundle = useMemo(() => parseTrinityBundle(payload), [payload]);
  const previousBundle = useMemo(
    () => extractPreviousBundle(payload),
    [payload],
  );

  if (!bundle) {
    return (
      <Card>
        <h3 className="mb-2 text-lg font-semibold">Trinity Viewer</h3>
        <p className="text-sm text-muted">
          Payload does not match `ir.trinity_bundle` structure.
        </p>
      </Card>
    );
  }

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-3">
        <div>
          <h3 className="text-lg font-semibold">Trinity Bundle</h3>
          <p className="text-sm text-muted">
            Schema v{bundle.schemaVersion ?? "-"}
          </p>
        </div>
        <div className="bg-canvas/40 rounded-lg border border-line px-3 py-2 text-xs text-muted">
          WHY: {bundle.problem.id} | WHAT: {bundle.policy.id} | HOW:{" "}
          {bundle.model.id}
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <section className="bg-canvas/30 space-y-3 rounded-xl border border-line p-3">
          <div>
            <p className="text-xs font-semibold uppercase text-muted">
              ProblemFrame (Why)
            </p>
            <p className="text-sm font-semibold">{bundle.problem.domain}</p>
            {bundle.problem.narrative ? (
              <p className="mt-1 text-sm text-muted">
                {bundle.problem.narrative}
              </p>
            ) : null}
          </div>

          <div>
            <p className="mb-1 text-xs font-semibold uppercase text-muted">
              Objectives
            </p>
            {bundle.problem.objectives.length > 0 ? (
              <ul className="space-y-1 text-sm">
                {bundle.problem.objectives.map((objective) => (
                  <li
                    key={objective.id}
                    className="rounded-lg border border-line bg-panel p-2"
                  >
                    <p className="font-mono text-xs">{objective.id}</p>
                    <p className="text-xs text-muted">
                      {objective.metricId} · {objective.direction} · target=
                      {objective.target}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted">No objectives.</p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="rounded-lg border border-line bg-panel p-2">
              <p className="text-xs uppercase text-muted">Constraints</p>
              <p className="font-semibold">
                {bundle.problem.constraints.length}
              </p>
            </div>
            <div className="rounded-lg border border-line bg-panel p-2">
              <p className="text-xs uppercase text-muted">Stakeholders</p>
              <p className="font-semibold">
                {bundle.problem.stakeholders.length}
              </p>
            </div>
            <div className="rounded-lg border border-line bg-panel p-2">
              <p className="text-xs uppercase text-muted">KPIs</p>
              <p className="font-semibold">{bundle.problem.kpiCount}</p>
            </div>
            <div className="rounded-lg border border-line bg-panel p-2">
              <p className="text-xs uppercase text-muted">Success Criteria</p>
              <p className="font-semibold">
                {bundle.problem.successCriteriaCount}
              </p>
            </div>
          </div>
        </section>

        <section className="bg-canvas/30 space-y-3 rounded-xl border border-line p-3">
          <div>
            <p className="text-xs font-semibold uppercase text-muted">
              PolicySpec (What)
            </p>
            <p className="text-sm font-semibold">{bundle.policy.id}</p>
            <p className="text-xs text-muted">
              {bundle.policy.mechanismBindingCount} bindings ·{" "}
              {bundle.policy.parameterCount} parameters
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
            <p className="text-sm text-muted">No interventions.</p>
          )}

          {bundle.policy.notes.length > 0 ? (
            <div className="rounded-lg border border-line bg-panel p-2 text-xs text-muted">
              Notes: {bundle.policy.notes.join("; ")}
            </div>
          ) : null}
        </section>

        <section className="bg-canvas/30 space-y-3 rounded-xl border border-line p-3">
          <div>
            <p className="text-xs font-semibold uppercase text-muted">
              ModelSpec (How)
            </p>
            <p className="text-sm font-semibold">{bundle.model.id}</p>
            <p className="text-xs text-muted">
              {bundle.model.fidelityLevel ?? "fidelity unknown"}
              {bundle.model.timeSemanticsLabel
                ? ` · ${bundle.model.timeSemanticsLabel}`
                : ""}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="rounded-lg border border-line bg-panel p-2">
              <p className="text-xs uppercase text-muted">Agent Types</p>
              <p className="font-semibold">{bundle.model.agentTypeCount}</p>
            </div>
            <div className="rounded-lg border border-line bg-panel p-2">
              <p className="text-xs uppercase text-muted">Env Params</p>
              <p className="font-semibold">
                {bundle.model.environmentParamCount}
              </p>
            </div>
            <div className="rounded-lg border border-line bg-panel p-2">
              <p className="text-xs uppercase text-muted">Assumptions</p>
              <p className="font-semibold">{bundle.model.assumptions.length}</p>
            </div>
            <div className="rounded-lg border border-line bg-panel p-2">
              <p className="text-xs uppercase text-muted">Calibrated</p>
              <p className="font-semibold">
                {bundle.model.calibrated === null
                  ? "-"
                  : bundle.model.calibrated
                    ? "yes"
                    : "no"}
              </p>
            </div>
          </div>

          <div className="space-y-1 text-xs text-muted">
            <p className="truncate">
              data_snapshot_ref: {bundle.model.dataSnapshotRef ?? "-"}
            </p>
            <p className="truncate">
              registry_bundle_ref: {bundle.model.registryBundleRef ?? "-"}
            </p>
            <p className="truncate">
              calibration_ref: {bundle.model.calibrationRef ?? "-"}
            </p>
          </div>

          {bundle.model.assumptions.length > 0 ? (
            <div className="space-y-1">
              {bundle.model.assumptions.slice(0, 5).map((assumption) => (
                <div
                  key={assumption.id}
                  className="rounded-lg border border-line bg-panel p-2"
                >
                  <p className="font-mono text-xs">{assumption.id}</p>
                  <p className="text-xs text-muted">{assumption.type}</p>
                  <p className="text-sm">{assumption.description}</p>
                </div>
              ))}
            </div>
          ) : null}
        </section>
      </div>

      <div className="space-y-2 border-t border-line pt-3">
        <p className="text-xs font-semibold uppercase text-muted">
          Trinity Diff
        </p>
        <TrinityDiff
          currentPayload={payload}
          previousPayload={previousBundle.bundle}
          previousTitle={previousBundle.title}
        />
      </div>
    </Card>
  );
}
