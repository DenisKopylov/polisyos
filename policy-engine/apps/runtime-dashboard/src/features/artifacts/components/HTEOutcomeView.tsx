import { buildArtifactHref } from "@/features/artifacts/domain/searchParams";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { formatNumber } from "@/shared/lib/utils";

import type {
  DecisionPacketHTEProjection,
  HTEArtifactRef,
  HTETargetRelationDisplay,
} from "../domain/decisionPacketHte";

export type {
  HTEIntervalOutcomeDisplay,
  HTEOutcomeDisplayModel,
  HTEPointOutcomeDisplay,
  HTERefusalOutcomeDisplay,
  HTETargetRelationDisplay,
} from "../domain/decisionPacketHte";

type HTEOutcomeViewProps = {
  outcome: DecisionPacketHTEProjection;
};

function displayValue(
  value: string | null,
  t: ReturnType<typeof useI18n>["t"],
) {
  return value ?? t("pages.artifacts.hteOutcome.notEstablished");
}

function dispositionLabel(
  disposition: HTETargetRelationDisplay["overall_disposition"],
  t: ReturnType<typeof useI18n>["t"],
) {
  const labelKeys = {
    satisfied: "satisfied",
    requested_claim_not_satisfied: "requestedClaimNotSatisfied",
    not_established: "notEstablished",
  } as const;
  return t(`pages.artifacts.hteOutcome.dispositions.${labelKeys[disposition]}`);
}

function ReferenceLink({
  label,
  reference,
}: {
  label: string;
  reference: HTEArtifactRef;
}) {
  const href = buildArtifactHref(reference.artifact_id, {
    artifactRef: reference,
  });

  return (
    <li>
      <a className="underline decoration-dotted underline-offset-2" href={href}>
        {label}
      </a>
    </li>
  );
}

export function InvalidHTEOutcomeView() {
  const { t } = useI18n();
  return (
    <section
      aria-labelledby="hte-outcome-heading"
      className="border-line bg-panel rounded-xl border p-4"
      data-hte-outcome-kind="invalid"
      data-testid="hte-outcome-invalid"
    >
      <h4 className="text-base font-semibold" id="hte-outcome-heading">
        {t("pages.artifacts.hteOutcome.title")}
      </h4>
      <p className="text-muted mt-1 text-sm">
        {t("pages.artifacts.hteOutcome.invalidSummary")}
      </p>
    </section>
  );
}

export default function HTEOutcomeView({ outcome }: HTEOutcomeViewProps) {
  const { t } = useI18n();
  if (outcome.kind === "legacy_limited") {
    if (outcome.availability === "unavailable") {
      if (outcome.parse_warning !== "hte_result_parse_failed") {
        return <InvalidHTEOutcomeView />;
      }
      return (
        <section
          aria-labelledby="hte-outcome-heading"
          className="border-line bg-panel rounded-xl border p-4"
          data-hte-availability="unavailable"
          data-hte-outcome-kind="legacy_limited"
          data-testid="hte-outcome-unavailable"
          role="status"
        >
          <h4 className="text-base font-semibold" id="hte-outcome-heading">
            {t("pages.artifacts.hteOutcome.title")}
          </h4>
          <p className="text-muted mt-1 text-sm">
            {t("pages.artifacts.hteOutcome.legacyUnavailableTitle")}
          </p>
          <p className="mt-2 text-sm">
            {t("pages.artifacts.hteOutcome.legacyUnavailableSummary", {
              parseWarning: outcome.parse_warning,
            })}
          </p>
        </section>
      );
    }

    const legacyQuantity = (value: number | null) =>
      value === null
        ? t("pages.artifacts.hteOutcome.notEstablished")
        : formatNumber(value, { maximumFractionDigits: 4 });

    return (
      <section
        aria-labelledby="hte-outcome-heading"
        className="border-line bg-panel rounded-xl border p-4"
        data-hte-outcome-kind="legacy_limited"
        data-testid="hte-outcome"
      >
        <h4 className="text-base font-semibold" id="hte-outcome-heading">
          {t("pages.artifacts.hteOutcome.title")}
        </h4>
        <p className="text-muted mt-1 text-sm">
          {t("pages.artifacts.hteOutcome.legacyTitle")}
        </p>
        <div className="mt-4 space-y-2 text-sm">
          <p>
            <span className="text-muted">
              {t("pages.artifacts.hteOutcome.legacyAte")}:{" "}
            </span>
            <span data-testid="hte-legacy-ate">
              {legacyQuantity(outcome.ate)}
            </span>
          </p>
          <div data-testid="hte-legacy-bounds">
            <p className="text-muted">
              {t("pages.artifacts.hteOutcome.legacyBounds")}
            </p>
            <p>
              {legacyQuantity(outcome.ate_ci_lower)} –{" "}
              {legacyQuantity(outcome.ate_ci_upper)}
            </p>
          </div>
          <p data-testid="hte-legacy-limitations">
            {t("pages.artifacts.hteOutcome.legacyLimitations")}
          </p>
          {outcome.warnings.length > 0 ? (
            <aside
              aria-label={t("pages.artifacts.hteOutcome.legacyWarningsTitle")}
              className="border-line mt-3 rounded-lg border p-3"
              data-testid="hte-legacy-warnings"
              role="note"
            >
              <h5 className="font-medium">
                {t("pages.artifacts.hteOutcome.legacyWarningsTitle")}
              </h5>
              <ul className="mt-1 list-disc pl-5">
                {outcome.warnings.map((warning, index) => (
                  <li key={warning + String(index)}>{warning}</li>
                ))}
              </ul>
            </aside>
          ) : null}
        </div>
      </section>
    );
  }

  const isRefusal = outcome.kind === "refusal";
  const resource = outcome.resource_evidence;
  const resourceObservations: Array<{
    kind: "estimator" | "joblib" | "unobserved";
    text: string;
  }> = [];

  if (resource.execution_status === "not_started") {
    resourceObservations.push({
      kind: "unobserved",
      text: t("pages.artifacts.hteOutcome.resource.unobserved"),
    });
  } else {
    if (resource.estimator_observation_status === "recomputed") {
      resourceObservations.push({
        kind: "estimator",
        text: t("pages.artifacts.hteOutcome.resource.estimator", {
          beforeEstimator: resource.estimator_before_class_fqn ?? "",
          afterEstimator: resource.estimator_after_class_fqn ?? "",
          beforeJobs: resource.estimator_before_n_jobs ?? "",
          afterJobs: resource.estimator_after_n_jobs ?? "",
          beforeDigest: resource.estimator_before_params_sha256 ?? "",
          afterDigest: resource.estimator_after_params_sha256 ?? "",
        }),
      });
    }

    if (resource.joblib_observation_status === "recomputed") {
      resourceObservations.push({
        kind: "joblib",
        text: t("pages.artifacts.hteOutcome.resource.joblib", {
          status: resource.joblib_exit_status,
          entryVersion: resource.joblib_entry_implementation_version ?? "",
          exitVersion: resource.joblib_exit_implementation_version ?? "",
          entryJobs: resource.joblib_entry_effective_jobs ?? "",
          exitJobs: resource.joblib_exit_effective_jobs ?? "",
          entryBackend: resource.joblib_entry_backend_fqn ?? "",
          exitBackend: resource.joblib_exit_backend_fqn ?? "",
          entryDigest: resource.joblib_entry_config_sha256 ?? "",
          exitDigest: resource.joblib_exit_config_sha256 ?? "",
        }),
      });
    }

    if (resourceObservations.length === 0) {
      resourceObservations.push({
        kind: "unobserved",
        text: t("pages.artifacts.hteOutcome.resource.unobserved"),
      });
    }
  }
  const references = [
    {
      label: t("pages.artifacts.hteOutcome.refs.sourceData"),
      reference: outcome.source_data_ref,
    },
    {
      label: t("pages.artifacts.hteOutcome.refs.ownedAttempt"),
      reference: outcome.owned_attempt_anchor_ref,
    },
    {
      label: t("pages.artifacts.hteOutcome.refs.hteOutcome"),
      reference: outcome.hte_outcome_ref,
    },
    {
      label: t("pages.artifacts.hteOutcome.refs.methodResult"),
      reference: outcome.method_result_ref,
    },
    {
      label: t("pages.artifacts.hteOutcome.refs.methodEvidence"),
      reference: outcome.method_evidence_ref,
    },
    {
      label: t("pages.artifacts.hteOutcome.refs.resourcePolicy"),
      reference: resource.owner_policy_ref,
    },
    ...(outcome.kind === "point_estimate"
      ? [
          {
            label: t("pages.artifacts.hteOutcome.refs.pointResult"),
            reference: outcome.point_result_ref,
          },
        ]
      : []),
    ...(outcome.kind === "interval_estimate"
      ? [
          {
            label: t("pages.artifacts.hteOutcome.refs.hteResult"),
            reference: outcome.hte_result_ref,
          },
          {
            label: t("pages.artifacts.hteOutcome.refs.inferenceBasis"),
            reference: outcome.inference_basis_ref,
          },
        ]
      : []),
    ...(outcome.kind === "refusal"
      ? [
          {
            label: t("pages.artifacts.hteOutcome.refs.refusalDiagnostic"),
            reference: outcome.refusal_diagnostic_ref,
          },
        ]
      : []),
  ];

  return (
    <section
      aria-labelledby="hte-outcome-heading"
      className="border-line bg-panel rounded-xl border p-4"
      data-hte-outcome-kind={outcome.kind}
      data-testid="hte-outcome"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h4 className="text-base font-semibold" id="hte-outcome-heading">
            {t("pages.artifacts.hteOutcome.title")}
          </h4>
          <p className="text-muted mt-1 text-sm">
            {isRefusal
              ? t("pages.artifacts.hteOutcome.refused")
              : outcome.kind === "point_estimate"
                ? t("pages.artifacts.hteOutcome.pointOnly")
                : t("pages.artifacts.hteOutcome.intervalAvailable")}
          </p>
          <p className="text-muted text-xs">
            {isRefusal
              ? t("pages.artifacts.hteOutcome.authority.refusal")
              : t("pages.artifacts.hteOutcome.authority.candidate")}
          </p>
        </div>
      </div>

      {isRefusal ? (
        <div
          className="mt-4 space-y-2 text-sm"
          data-testid="hte-outcome-refusal"
        >
          <p>
            <span className="text-muted">
              {t("pages.artifacts.hteOutcome.refusalStage")}:{" "}
            </span>
            {outcome.refusal_stage}
          </p>
          <p>
            <span className="text-muted">
              {t("pages.artifacts.hteOutcome.refusalReason")}:{" "}
            </span>
            {outcome.refusal_reason}
          </p>
          <p>
            <span className="text-muted">
              {t("pages.artifacts.hteOutcome.diagnosticCode")}:{" "}
            </span>
            {outcome.refusal_diagnostic_code}
          </p>
        </div>
      ) : (
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <div className="bg-canvas/30 border-line rounded-lg border p-3">
            <p className="text-muted text-xs uppercase">
              {t("pages.artifacts.hteOutcome.point")}
            </p>
            <p
              className="mt-1 text-lg font-semibold"
              data-testid="hte-outcome-point-value"
            >
              {formatNumber(outcome.point_estimate, {
                maximumFractionDigits: 4,
              })}
              {outcome.measure_unit_status === "established" &&
              outcome.measure_unit
                ? ` ${outcome.measure_unit}`
                : ""}
            </p>
            <p className="text-muted mt-1 text-xs">
              {t("pages.artifacts.hteOutcome.computedScope")}:{" "}
              {displayValue(outcome.computed_target_scope, t)}
            </p>
            <p className="text-muted text-xs">
              {t("pages.artifacts.hteOutcome.computedEstimand")}:{" "}
              {displayValue(outcome.computed_estimand, t)}
            </p>
            <p className="text-muted text-xs">
              {t("pages.artifacts.hteOutcome.measureUnit")}:{" "}
              {outcome.measure_unit_status === "established"
                ? displayValue(outcome.measure_unit, t)
                : t("pages.artifacts.hteOutcome.unitNotEstablished")}
            </p>
          </div>

          <div className="bg-canvas/30 border-line rounded-lg border p-3 text-sm">
            <p className="text-muted text-xs uppercase">
              {t("pages.artifacts.hteOutcome.requestedClaim")}
            </p>
            <p className="mt-1">
              {t("pages.artifacts.hteOutcome.requestedScope")}:{" "}
              {displayValue(outcome.request_target_scope, t)}
            </p>
            <p>
              {t("pages.artifacts.hteOutcome.requestedEstimand")}:{" "}
              {displayValue(outcome.request_estimand, t)}
            </p>
            <p>
              {t("pages.artifacts.hteOutcome.outcomeVariable")}:{" "}
              {displayValue(outcome.outcome_variable_id, t)}
            </p>
            <p>
              {t("pages.artifacts.hteOutcome.treatmentVariable")}:{" "}
              {displayValue(outcome.treatment_variable_id, t)}
            </p>
            <p>
              {t("pages.artifacts.hteOutcome.requestedAlpha")}:{" "}
              {outcome.requested_alpha === null
                ? t("pages.artifacts.hteOutcome.notEstablished")
                : formatNumber(outcome.requested_alpha, {
                    maximumFractionDigits: 4,
                  })}
            </p>
            <p>
              {t("pages.artifacts.hteOutcome.contrast")}:{" "}
              {outcome.request_contrast_status === "declared"
                ? `${formatNumber(outcome.control_value ?? 0, { maximumFractionDigits: 4 })} → ${formatNumber(outcome.treated_value ?? 0, { maximumFractionDigits: 4 })}`
                : t("pages.artifacts.hteOutcome.notEstablished")}
            </p>
            <p>
              {t("pages.artifacts.hteOutcome.requestedGuarantee")}:{" "}
              {displayValue(outcome.requested_guarantee, t)}
            </p>
            <p>
              {t("pages.artifacts.hteOutcome.computedGuarantee")}:{" "}
              {displayValue(outcome.computed_guarantee, t)}
            </p>
            <p className="text-muted mt-2 text-xs">
              {outcome.n_selected_rows === null
                ? t("pages.artifacts.hteOutcome.selectedRowsUnknown")
                : t("pages.artifacts.hteOutcome.selectedRows", {
                    count: outcome.n_selected_rows,
                  })}
            </p>
          </div>

          <div
            className="border-line bg-canvas/30 rounded-lg border p-3 text-sm md:col-span-2"
            data-overall-disposition={
              outcome.target_relation.overall_disposition
            }
            data-testid="hte-target-relation"
          >
            <p className="font-semibold">
              {t("pages.artifacts.hteOutcome.claimDisposition")}:{" "}
              {dispositionLabel(outcome.target_relation.overall_disposition, t)}
            </p>
            <p className="text-muted mt-1 text-xs">
              {t("pages.artifacts.hteOutcome.scopeDisposition")}:{" "}
              {dispositionLabel(outcome.target_relation.scope_disposition, t)}
              {" · "}
              {t("pages.artifacts.hteOutcome.guaranteeDisposition")}:{" "}
              {dispositionLabel(
                outcome.target_relation.guarantee_disposition,
                t,
              )}
            </p>
          </div>

          {outcome.kind === "interval_estimate" ? (
            <div
              className="border-line bg-canvas/30 rounded-lg border p-3 md:col-span-2"
              data-testid="hte-outcome-interval"
            >
              <p className="text-muted text-xs font-semibold uppercase">
                {t("pages.artifacts.hteOutcome.conditionalInterval")}
              </p>
              <p className="mt-1 font-semibold">
                [
                {formatNumber(outcome.lower_bound, {
                  maximumFractionDigits: 4,
                })}
                ,{" "}
                {formatNumber(outcome.upper_bound, {
                  maximumFractionDigits: 4,
                })}
                ]{" · "}
                {formatNumber(outcome.confidence_level * 100, {
                  maximumFractionDigits: 1,
                })}
                %
              </p>
              <p className="text-muted mt-1 text-sm">
                {t("pages.artifacts.hteOutcome.conditionalIntervalDescription")}
              </p>
            </div>
          ) : (
            <div className="border-line bg-canvas/30 rounded-lg border p-3 text-sm md:col-span-2">
              <p>
                <span className="text-muted">
                  {t("pages.artifacts.hteOutcome.inferenceStatus")}:{" "}
                </span>
                {outcome.inference_status}
              </p>
              <p>
                <span className="text-muted">
                  {t("pages.artifacts.hteOutcome.inferenceReason")}:{" "}
                </span>
                {outcome.inference_reason}
              </p>
            </div>
          )}
        </div>
      )}

      <div className="border-line mt-4 border-t pt-3 text-sm">
        <p className="text-muted text-xs font-semibold uppercase">
          {t("pages.artifacts.hteOutcome.inferenceLimitsTitle")}
        </p>
        <p className="mt-1">
          {t("pages.artifacts.hteOutcome.inferenceLimits")}
        </p>
        {outcome.limitations.length > 0 ? (
          <ul className="text-muted mt-2 list-disc space-y-1 pl-5">
            {outcome.limitations.map((limitation) => (
              <li key={limitation}>{limitation}</li>
            ))}
          </ul>
        ) : null}
      </div>

      <details className="border-line mt-4 border-t pt-3 text-sm">
        <summary className="cursor-pointer font-semibold">
          {t("pages.artifacts.hteOutcome.provenance")}
        </summary>
        <div className="text-muted mt-2 grid gap-3 sm:grid-cols-2">
          <p>
            {t("pages.artifacts.hteOutcome.method")}:{" "}
            <span className="text-ink">{outcome.method_fqn}</span>
          </p>
          <p>
            {t("pages.artifacts.hteOutcome.profile")}:{" "}
            <span className="text-ink">{outcome.method_profile_id}</span>
          </p>
          <p>
            {t("pages.artifacts.hteOutcome.methodAbiDigest")}:{" "}
            <code className="break-all">{outcome.method_abi_digest}</code>
          </p>
          <p>
            {t("pages.artifacts.hteOutcome.resolvedParamsDigest")}:{" "}
            <code className="break-all">{outcome.resolved_params_sha256}</code>
          </p>
          <p>
            {t("pages.artifacts.hteOutcome.selectedRowsDigest")}:{" "}
            <code className="break-all">
              {outcome.selected_rows_sha256 ??
                t("pages.artifacts.hteOutcome.notEstablished")}
            </code>
          </p>
          <p>
            {t("pages.artifacts.hteOutcome.rowOrderDigest")}:{" "}
            <code className="break-all">
              {outcome.selected_row_order_sha256 ??
                t("pages.artifacts.hteOutcome.notEstablished")}
            </code>
          </p>
          <p>
            {t("pages.artifacts.hteOutcome.selectedXDigest")}:{" "}
            <code className="break-all">
              {outcome.selected_x_sha256 ??
                t("pages.artifacts.hteOutcome.notEstablished")}
            </code>
          </p>
          <p>
            {t("pages.artifacts.hteOutcome.resource.policyDigest")}:{" "}
            <code className="break-all">{resource.owner_policy_digest}</code>
          </p>
          <p>
            {t("pages.artifacts.hteOutcome.resource.execution")}:{" "}
            {resource.execution_status}
          </p>
          <div
            className="sm:col-span-2"
            data-testid="hte-outcome-resource-observations"
          >
            {resourceObservations.map(({ kind, text }) => (
              <p
                className="text-muted mt-1 text-xs"
                data-testid={`hte-outcome-resource-${kind}`}
                key={kind}
              >
                {t("pages.artifacts.hteOutcome.resource.observation")}: {text}
              </p>
            ))}
          </div>
          <p>
            {t("pages.artifacts.hteOutcome.resource.physicalLimit")}:{" "}
            {t("pages.artifacts.hteOutcome.notEstablished")}
          </p>
        </div>
        <ul className="mt-3 grid gap-2 sm:grid-cols-2">
          {references.map(({ label, reference }) => (
            <ReferenceLink
              key={`${label}:${reference.artifact_id}`}
              label={label}
              reference={reference}
            />
          ))}
        </ul>
      </details>
    </section>
  );
}
