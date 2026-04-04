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
        <p className="text-muted text-sm">
          Payload does not match `ir.trinity_bundle` structure.
        </p>
      </Card>
    );
  }

  return (
    <Card className="space-y-4">
      <div className="border-line flex flex-wrap items-center justify-between gap-2 border-b pb-3">
        <div>
          <h3 className="text-lg font-semibold">Trinity Bundle</h3>
          <p className="text-muted text-sm">
            Schema v{bundle.schemaVersion ?? "-"}
          </p>
        </div>
        <div className="bg-canvas/40 border-line text-muted rounded-lg border px-3 py-2 text-xs">
          WHY: {bundle.problem.id} | WHAT: {bundle.policy.id} | HOW:{" "}
          {bundle.model.id}
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <section className="bg-canvas/30 border-line space-y-3 rounded-xl border p-3">
          <div>
            <p className="text-muted text-xs font-semibold uppercase">
              ProblemFrame (Why)
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
              Objectives
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
                      {objective.metricId} · {objective.direction} · target=
                      {objective.target}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted text-sm">No objectives.</p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="border-line bg-panel rounded-lg border p-2">
              <p className="text-muted text-xs uppercase">Constraints</p>
              <p className="font-semibold">
                {bundle.problem.constraints.length}
              </p>
            </div>
            <div className="border-line bg-panel rounded-lg border p-2">
              <p className="text-muted text-xs uppercase">Stakeholders</p>
              <p className="font-semibold">
                {bundle.problem.stakeholders.length}
              </p>
            </div>
            <div className="border-line bg-panel rounded-lg border p-2">
              <p className="text-muted text-xs uppercase">KPIs</p>
              <p className="font-semibold">{bundle.problem.kpiCount}</p>
            </div>
            <div className="border-line bg-panel rounded-lg border p-2">
              <p className="text-muted text-xs uppercase">Success Criteria</p>
              <p className="font-semibold">
                {bundle.problem.successCriteriaCount}
              </p>
            </div>
          </div>
        </section>

        <section className="bg-canvas/30 border-line space-y-3 rounded-xl border p-3">
          <div>
            <p className="text-muted text-xs font-semibold uppercase">
              PolicySpec (What)
            </p>
            <p className="text-sm font-semibold">{bundle.policy.id}</p>
            <p className="text-muted text-xs">
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
            <p className="text-muted text-sm">No interventions.</p>
          )}

          {bundle.policy.notes.length > 0 ? (
            <div className="border-line bg-panel text-muted rounded-lg border p-2 text-xs">
              Notes: {bundle.policy.notes.join("; ")}
            </div>
          ) : null}
        </section>

        <section className="bg-canvas/30 border-line space-y-3 rounded-xl border p-3">
          <div>
            <p className="text-muted text-xs font-semibold uppercase">
              ModelSpec (How)
            </p>
            <p className="text-sm font-semibold">{bundle.model.id}</p>
            <p className="text-muted text-xs">
              {bundle.model.fidelityLevel ?? "fidelity unknown"}
              {bundle.model.timeSemanticsLabel
                ? ` · ${bundle.model.timeSemanticsLabel}`
                : ""}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="border-line bg-panel rounded-lg border p-2">
              <p className="text-muted text-xs uppercase">Agent Types</p>
              <p className="font-semibold">{bundle.model.agentTypeCount}</p>
            </div>
            <div className="border-line bg-panel rounded-lg border p-2">
              <p className="text-muted text-xs uppercase">Env Params</p>
              <p className="font-semibold">
                {bundle.model.environmentParamCount}
              </p>
            </div>
            <div className="border-line bg-panel rounded-lg border p-2">
              <p className="text-muted text-xs uppercase">Assumptions</p>
              <p className="font-semibold">{bundle.model.assumptions.length}</p>
            </div>
            <div className="border-line bg-panel rounded-lg border p-2">
              <p className="text-muted text-xs uppercase">Calibrated</p>
              <p className="font-semibold">
                {bundle.model.calibrated === null
                  ? "-"
                  : bundle.model.calibrated
                    ? "yes"
                    : "no"}
              </p>
            </div>
          </div>

          <div className="text-muted space-y-1 text-xs">
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
