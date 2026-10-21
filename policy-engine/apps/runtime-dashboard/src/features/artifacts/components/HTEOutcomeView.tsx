import { buildArtifactHref } from "@/features/artifacts/domain/searchParams";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import type { EvidenceArtifactRef } from "@/shared/lib/domain/evidence";
import { formatNumber } from "@/shared/lib/utils";

/**
 * Bounded display model for the persisted HTE outcome union.
 *
 * The Runtime projection may carry additional provenance, but this component
 * deliberately accepts no per-row CATE vector. Those values remain behind the
 * CAS artifact boundary and are not part of a decision-packet GET.
 */
export type HTEOutcomeDisplayModelCommon = {
  schema_version: "1.0";
  authority_status: "candidate" | "refusal";
  method_fqn: string;
  method_abi: string;
  method_abi_digest: string;
  method_profile_id: string;
  input_profile_id: "all_source_rows_in_input_order@1.0";
  selected_input_sha256: string;
  selected_rows_sha256: string;
  selected_x_sha256: string;
  selected_row_order_sha256: string;
  resolved_params_sha256: string;
  n_selected_rows: number;
  source_data_ref: EvidenceArtifactRef;
  invocation_basis_ref: EvidenceArtifactRef | null;
  invocation_basis_status: "established" | "not_established";
  invocation_basis_reason:
    | "owner_selected_invocation_basis"
    | "no_invocation_basis_artifact_contract"
    | null;
  owned_attempt_anchor_ref: EvidenceArtifactRef;
  method_result_ref: EvidenceArtifactRef;
  method_evidence_ref: EvidenceArtifactRef;
  request_estimand_status: "declared" | "not_established";
  request_estimand: string | null;
  request_target_scope_status: "declared" | "not_established";
  request_target_scope: string | null;
  outcome_variable_status: "declared" | "not_established";
  outcome_variable_id: string | null;
  treatment_variable_status: "declared" | "not_established";
  treatment_variable_id: string | null;
  request_alpha_status: "declared" | "not_established";
  requested_alpha: number | null;
  contrast_status: "established" | "not_established";
  control_value: number | null;
  treated_value: number | null;
  limitations: string[];
};

export type HTEPointEstimateDisplay = {
  schema_version: "1.0";
  value: number;
  estimand: "mean_effect_over_selected_x";
  computed_target_scope_status: "recomputed";
  computed_target_scope: "selected_evaluation_rows";
  measure_unit_status: "established" | "not_established";
  measure_unit: string | null;
};

export type HTEPointOutcomeDisplay = HTEOutcomeDisplayModelCommon & {
  kind: "point_estimate";
  authority_status: "candidate";
  point_estimate: HTEPointEstimateDisplay;
  inference_status: "unavailable" | "unsupported" | "not_qualified";
  inference_reason:
    | "native_inference_unavailable"
    | "native_inference_invalid"
    | "method_profile_not_qualified"
    | "selection_uses_outcomes"
    | "contrast_not_established"
    | "request_alpha_not_established"
    | "runtime_origin_not_verified";
};

export type HTEIntervalOutcomeDisplay = HTEOutcomeDisplayModelCommon & {
  kind: "interval_estimate";
  authority_status: "candidate";
  point_estimate: HTEPointEstimateDisplay;
  lower_bound: number;
  upper_bound: number;
  confidence_level: number;
  interval_semantics: "native_mean_confidence_interval";
  inference_status: "native_ate_inference_validated";
  inference_basis_ref: EvidenceArtifactRef;
  hte_result_ref: EvidenceArtifactRef;
};

export type HTERefusalOutcomeDisplay = HTEOutcomeDisplayModelCommon & {
  kind: "refusal";
  authority_status: "refusal";
  refusal_stage: "prepare" | "fit" | "infer" | "origin_verification";
  refusal_reason:
    | "invalid_point_estimate"
    | "method_execution_failed"
    | "native_inference_invalid"
    | "runtime_origin_not_verified";
  diagnostic_code: string;
};

/** A bounded, typed display projection of one persisted HTE outcome. */
export type HTEOutcomeDisplayModel =
  | HTEPointOutcomeDisplay
  | HTEIntervalOutcomeDisplay
  | HTERefusalOutcomeDisplay;

type HTEOutcomeViewProps = {
  outcome: HTEOutcomeDisplayModel;
};

function displayStatus(value: string | null, status: string) {
  return value === null ? status : value;
}

function ReferenceLink({
  label,
  reference,
}: {
  label: string;
  reference: EvidenceArtifactRef;
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

export default function HTEOutcomeView({ outcome }: HTEOutcomeViewProps) {
  const { t } = useI18n();
  const isRefusal = outcome.kind === "refusal";

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
        </div>
        <span className="border-line rounded-full border px-2 py-1 text-xs font-semibold">
          {isRefusal
            ? t("pages.artifacts.hteOutcome.authority.refusal")
            : t("pages.artifacts.hteOutcome.authority.candidate")}
        </span>
      </div>

      {outcome.kind === "refusal" ? (
        <div
          className="mt-4 space-y-2 text-sm"
          data-testid="hte-outcome-refusal"
        >
          <p>
            <span className="text-muted">
              {t("pages.artifacts.hteOutcome.refusalStage")}:
            </span>
            <span>{outcome.refusal_stage}</span>
          </p>
          <p>
            <span className="text-muted">
              {t("pages.artifacts.hteOutcome.refusalReason")}:
            </span>
            <span>{outcome.refusal_reason}</span>
          </p>
          <p>
            <span className="text-muted">
              {t("pages.artifacts.hteOutcome.diagnosticCode")}:
            </span>
            <span>{outcome.diagnostic_code}</span>
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
              {formatNumber(outcome.point_estimate.value, {
                maximumFractionDigits: 4,
              })}
              {outcome.point_estimate.measure_unit_status === "established" &&
              outcome.point_estimate.measure_unit
                ? ` ${outcome.point_estimate.measure_unit}`
                : ""}
            </p>
            <p className="text-muted mt-1 text-xs">
              {t("pages.artifacts.hteOutcome.computedScope")}:
              {outcome.point_estimate.computed_target_scope}
            </p>
            <p className="text-muted text-xs">
              {t("pages.artifacts.hteOutcome.measureUnit")}:
              {outcome.point_estimate.measure_unit_status === "established"
                ? outcome.point_estimate.measure_unit
                : t("pages.artifacts.hteOutcome.unitNotEstablished")}
            </p>
          </div>

          <div className="bg-canvas/30 border-line rounded-lg border p-3 text-sm">
            <p className="text-muted text-xs uppercase">
              {t("pages.artifacts.hteOutcome.requestedClaim")}
            </p>
            <p className="mt-1">
              {t("pages.artifacts.hteOutcome.requestedScope")}:{" "}
              {displayStatus(
                outcome.request_target_scope,
                t("pages.artifacts.hteOutcome.notEstablished"),
              )}
            </p>
            <p>
              {t("pages.artifacts.hteOutcome.requestedEstimand")}:{" "}
              {displayStatus(
                outcome.request_estimand,
                t("pages.artifacts.hteOutcome.notEstablished"),
              )}
            </p>
            <p className="text-muted mt-2 text-xs">
              {t("pages.artifacts.hteOutcome.selectedRows", {
                count: outcome.n_selected_rows,
              })}
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
                  {t("pages.artifacts.hteOutcome.inferenceStatus")}:
                </span>
                {outcome.inference_status}
              </p>
              <p>
                <span className="text-muted">
                  {t("pages.artifacts.hteOutcome.inferenceReason")}:
                </span>
                {outcome.inference_reason}
              </p>
            </div>
          )}
        </div>
      )}

      {!isRefusal ? (
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
      ) : null}

      <details className="border-line mt-4 border-t pt-3 text-sm">
        <summary className="cursor-pointer font-semibold">
          {t("pages.artifacts.hteOutcome.provenance")}
        </summary>
        <div className="text-muted mt-2 grid gap-3 sm:grid-cols-2">
          <p>
            {t("pages.artifacts.hteOutcome.method")}:{" "}
            <span className="text-ink">{outcome.method_fqn}</span>
            {" · "}
            <span className="text-ink">{outcome.method_abi}</span>
          </p>
          <p>
            {t("pages.artifacts.hteOutcome.profile")}:{" "}
            <span className="text-ink">{outcome.method_profile_id}</span>
          </p>
          <p>
            {t("pages.artifacts.hteOutcome.rowOrderDigest")}:{" "}
            <code className="break-all">
              {outcome.selected_row_order_sha256}
            </code>
          </p>
          <p>
            {t("pages.artifacts.hteOutcome.selectedRowsDigest")}:{" "}
            <code className="break-all">{outcome.selected_rows_sha256}</code>
          </p>
        </div>
        <ul className="mt-3 grid gap-2 sm:grid-cols-2">
          <ReferenceLink
            label={t("pages.artifacts.hteOutcome.refs.sourceData")}
            reference={outcome.source_data_ref}
          />
          <ReferenceLink
            label={t("pages.artifacts.hteOutcome.refs.ownedAttempt")}
            reference={outcome.owned_attempt_anchor_ref}
          />
          <ReferenceLink
            label={t("pages.artifacts.hteOutcome.refs.methodResult")}
            reference={outcome.method_result_ref}
          />
          <ReferenceLink
            label={t("pages.artifacts.hteOutcome.refs.methodEvidence")}
            reference={outcome.method_evidence_ref}
          />
          {outcome.invocation_basis_ref ? (
            <ReferenceLink
              label={t("pages.artifacts.hteOutcome.refs.invocationBasis")}
              reference={outcome.invocation_basis_ref}
            />
          ) : null}
          {outcome.kind === "interval_estimate" ? (
            <>
              <ReferenceLink
                label={t("pages.artifacts.hteOutcome.refs.inferenceBasis")}
                reference={outcome.inference_basis_ref}
              />
              <ReferenceLink
                label={t("pages.artifacts.hteOutcome.refs.hteResult")}
                reference={outcome.hte_result_ref}
              />
            </>
          ) : null}
        </ul>
      </details>
    </section>
  );
}
