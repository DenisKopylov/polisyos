import { buildArtifactHref } from "@/features/artifacts/domain/searchParams";
import type { HTEArtifactRef } from "@/features/artifacts/domain/decisionPacketHte";
import { parseRunExecutionHteProjection } from "@/features/runs/domain/runExecutionHte";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { formatNumber } from "@/shared/lib/utils";

function ReferenceLink({ reference }: { reference: HTEArtifactRef }) {
  return (
    <a
      className="underline decoration-dotted underline-offset-2"
      href={buildArtifactHref(reference.artifact_id, {
        artifactRef: reference,
      })}
      rel="noreferrer"
    >
      {reference.kind}
    </a>
  );
}

function StatusLine({ label, value }: { label: string; value: string }) {
  return (
    <p>
      <span className="text-muted">{label}: </span>
      <span>{value}</span>
    </p>
  );
}

/** Show only the owner-selected scalar summary already present on RunDetails. */
export function RunHteExecutionSummary({
  projection,
}: {
  projection: unknown;
}) {
  const { t } = useI18n();
  const result = parseRunExecutionHteProjection(projection);
  if (result.kind === "absent") return null;

  return (
    <section
      aria-labelledby="run-hte-execution-title"
      className="border-line bg-panel rounded-xl border p-4"
      data-testid="run-hte-execution-summary"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold" id="run-hte-execution-title">
            {t("runHte.title")}
          </h3>
          <p className="text-muted mt-1 text-sm">{t("runHte.candidateOnly")}</p>
        </div>
        <span className="border-line rounded-full border px-2 py-1 text-xs font-semibold">
          {result.kind === "hte"
            ? result.projection_status
            : result.kind === "without_hte"
              ? result.projection_status
              : result.kind}
        </span>
      </div>

      {result.kind === "invalid" ? (
        <p className="mt-3 text-sm" role="status">
          {t("runHte.invalid")}
        </p>
      ) : result.kind === "without_hte" ? (
        <div className="mt-3 space-y-2 text-sm">
          <StatusLine
            label={t("runHte.projectionStatus")}
            value={result.projection_status}
          />
          {result.limitations.map((limitation) => (
            <p className="text-muted" key={limitation}>
              {limitation}
            </p>
          ))}
        </div>
      ) : result.kind === "selected_without_hte" ? (
        <div className="mt-3 space-y-2 text-sm">
          <StatusLine label={t("runHte.method")} value={result.method_fqn} />
          {result.limitations.map((limitation) => (
            <p className="text-muted" key={limitation}>
              {limitation}
            </p>
          ))}
        </div>
      ) : (
        <HteSelectedSummary result={result} />
      )}
    </section>
  );
}

function HteSelectedSummary({
  result,
}: {
  result: Extract<
    ReturnType<typeof parseRunExecutionHteProjection>,
    { kind: "hte" }
  >;
}) {
  const { t } = useI18n();
  const { summary } = result;
  const resource = summary.resource_evidence;
  const relation = summary.target_relation;

  return (
    <div className="mt-4 space-y-4 text-sm">
      <div className="bg-canvas/30 border-line rounded-lg border p-3">
        {summary.kind === "refusal" ? (
          <StatusLine
            label={t("runHte.refusal")}
            value={summary.refusal_reason}
          />
        ) : (
          <>
            <StatusLine
              label={t("runHte.point")}
              value={formatNumber(summary.point_estimate, {
                maximumFractionDigits: 4,
              })}
            />
            {summary.kind === "interval_estimate" ? (
              <>
                <StatusLine
                  label={t("runHte.conditionalInterval")}
                  value={`${formatNumber(summary.lower_bound, {
                    maximumFractionDigits: 4,
                  })} – ${formatNumber(summary.upper_bound, {
                    maximumFractionDigits: 4,
                  })}`}
                />
                <p className="text-muted mt-1">
                  {t("runHte.intervalLimitation")}
                </p>
              </>
            ) : (
              <StatusLine
                label={t("runHte.inferenceStatus")}
                value={`${summary.inference_status}: ${summary.inference_reason}`}
              />
            )}
          </>
        )}
        <StatusLine
          label={t("runHte.computedScope")}
          value={relation.computed_scope ?? relation.computed_scope_status}
        />
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <div className="bg-canvas/30 border-line rounded-lg border p-3">
          <p className="text-muted text-xs font-semibold uppercase">
            {t("runHte.targetRelation")}
          </p>
          <StatusLine
            label={t("runHte.requestedScope")}
            value={relation.requested_scope ?? relation.requested_scope_status}
          />
          <StatusLine
            label={t("runHte.scopeDisposition")}
            value={relation.scope_disposition}
          />
          <StatusLine
            label={t("runHte.requestedGuarantee")}
            value={
              relation.requested_guarantee ??
              relation.requested_guarantee_status
            }
          />
          <StatusLine
            label={t("runHte.computedGuarantee")}
            value={
              relation.computed_guarantee ?? relation.computed_guarantee_status
            }
          />
          <StatusLine
            label={t("runHte.guaranteeDisposition")}
            value={relation.guarantee_disposition}
          />
          <StatusLine
            label={t("runHte.overallDisposition")}
            value={relation.overall_disposition}
          />
          <StatusLine
            label={t("runHte.sourceIdentity")}
            value={relation.estimand_status}
          />
        </div>

        <div className="bg-canvas/30 border-line rounded-lg border p-3">
          <p className="text-muted text-xs font-semibold uppercase">
            {t("runHte.resourcePolicy")}
          </p>
          <StatusLine
            label={t("runHte.policyRevision")}
            value={`${resource.owner_policy_revision} · ${resource.owner_policy_schema_version}`}
          />
          <StatusLine
            label={t("runHte.method")}
            value={resource.owner_policy_method_profile_id}
          />
          <StatusLine
            label={t("runHte.executionScope")}
            value={resource.owner_policy_execution_scope}
          />
          <StatusLine
            label={t("runHte.declaredCaps")}
            value={`${t("runHte.maxJobs")} ${resource.owner_policy_max_jobs}; ${t("runHte.estimatorJobs")} ${resource.owner_policy_required_estimator_n_jobs ?? t("runHte.notApplicable")}`}
          />
          <hr className="border-line my-2" />
          <StatusLine
            label={t("runHte.executionObservation")}
            value={resource.execution_status}
          />
          <StatusLine
            label={t("runHte.estimatorObservation")}
            value={`${resource.estimator_observation_status} · ${resource.estimator_before_n_jobs ?? "—"} → ${resource.estimator_after_n_jobs ?? "—"}`}
          />
          <StatusLine
            label={t("runHte.joblibObservation")}
            value={`${resource.joblib_observation_status} · ${resource.joblib_entry_effective_jobs ?? "—"} → ${resource.joblib_exit_effective_jobs ?? "—"}`}
          />
          <StatusLine
            label={t("runHte.physicalThreads")}
            value={resource.physical_thread_limit_status}
          />
        </div>
      </div>

      {summary.materialization_binding_ref ? (
        <p>
          <span className="text-muted">
            {t("runHte.materializationBinding")}:{" "}
          </span>
          <ReferenceLink reference={summary.materialization_binding_ref} />
        </p>
      ) : null}

      {summary.limitations.length > 0 ? (
        <ul className="text-muted list-disc space-y-1 pl-5">
          {summary.limitations.map((limitation) => (
            <li key={limitation}>{limitation}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
