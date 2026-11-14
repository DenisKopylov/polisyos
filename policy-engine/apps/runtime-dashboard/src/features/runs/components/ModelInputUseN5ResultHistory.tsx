import { useEffect, useState } from "react";

import { Card } from "@polisyos/atlas-ui";

import { useRunModelInputUseN5Result } from "@/api/hooks/useRunModelInputUseN5Result";
import type {
  RunModelInputUseActionsProjection,
  RunModelInputUseN5SuccessorProjection,
} from "@/api/validators";
import { useI18n } from "@/shared/i18n/LocaleProvider";

function modelInputUseRefs(projection: RunModelInputUseN5SuccessorProjection) {
  if (
    projection.schema_version ===
    "policyos.runtime.run_model_input_use_n5_successor_projection.v1"
  ) {
    return {
      blocked_source: projection.blocked_source,
      n5_execution_ref: projection.n5_execution_ref,
      semantic_successor_ref: projection.semantic_successor_ref,
      simulation_result_ref: projection.simulation_result_ref,
    };
  }

  return {
    blocked_source: projection.blocked_source,
    current_action_phase_ref: projection.current_action_phase_ref,
    current_authority_decision_ref: projection.current_authority_decision_ref,
    current_basis_ref: projection.current_basis_ref,
    current_semantic_successor_ref: projection.current_semantic_successor_ref,
    current_use_decision_ref: projection.current_use_decision_ref,
    original_action_job_id: projection.original_action_job_id,
    original_execution_ref: projection.original_execution_ref,
    original_input_ref: projection.original_input_ref,
    original_result_ref: projection.original_result_ref,
    original_semantic_successor_ref: projection.original_semantic_successor_ref,
    frontier_ref: projection.frontier_ref,
    selected_basis_ref: projection.selected_basis_ref,
  };
}

function ResultCard({
  projection,
}: {
  projection: RunModelInputUseN5SuccessorProjection;
}) {
  const { t } = useI18n();
  const [bodyExpanded, setBodyExpanded] = useState(false);
  const isV2 =
    projection.schema_version ===
    "policyos.runtime.run_model_input_use_n5_successor_projection.v2";
  const frontierSelection = isV2
    ? (projection.frontier_selection ?? "not_established")
    : "not_established";
  const limitations = [
    projection.limitation_code,
    ...projection.semantic_input_limitation_codes,
    ...(isV2 ? projection.current_basis_limitations : []),
    ...(isV2 ? projection.selected_basis_limitations : []),
  ].filter((code): code is string => Boolean(code));
  const refs = modelInputUseRefs(projection);

  return (
    <article
      className="space-y-2 border-t pt-3"
      data-testid="model-input-use-result-row"
      data-frontier-selection={frontierSelection}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h5 className="font-semibold">
          {t("pages.runs.modelInputUse.action", {
            actionJobId: projection.action_job_id,
          })}
        </h5>
        <span className="rounded-full border px-2 py-1 text-xs">
          {t("pages.runs.modelInputUse.actionStatus", {
            status: projection.action_status,
          })}
        </span>
      </div>
      {isV2 ? (
        <p data-testid="model-input-use-frontier-selection">
          {t("pages.runs.modelInputUse.frontier", {
            status: frontierSelection,
            revision: String(projection.frontier_revision ?? "unknown"),
          })}
        </p>
      ) : (
        <p data-testid="model-input-use-frontier-selection">
          {t("pages.runs.modelInputUse.selectionNotEstablished")}
        </p>
      )}
      {isV2 && projection.evaluation_provenance ? (
        <p data-testid="model-input-use-evaluation-provenance">
          {t("pages.runs.modelInputUse.provenance", {
            provenance: projection.evaluation_provenance,
          })}
        </p>
      ) : null}
      {isV2 && projection.basis_comparison_result ? (
        <p data-testid="model-input-use-basis-comparison">
          {t("pages.runs.modelInputUse.basisComparison", {
            result: projection.basis_comparison_result,
            provenance: projection.predicate_provenance ?? "not_established",
          })}
        </p>
      ) : null}
      <p data-testid="model-input-use-result-status">
        {t("pages.runs.modelInputUse.resultStatus", {
          status: projection.result_status,
        })}
      </p>
      <p data-testid="model-input-use-currentness">
        {t("pages.runs.modelInputUse.currentness", {
          status: t("epochChrome.status.not_established"),
        })}
      </p>
      <p data-testid="model-input-use-units-not-supplied">
        {t("pages.runs.modelInputUse.resultUnitNotSupplied")}
      </p>
      <p className="text-muted text-sm" data-testid="model-input-use-scope">
        {t("pages.runs.modelInputUse.candidateScope")}
      </p>
      {limitations.length > 0 ? (
        <ul
          className="list-disc space-y-1 pl-5 text-sm"
          data-testid="model-input-use-limitations"
        >
          {[...new Set(limitations)].map((code) => (
            <li key={code}>{code}</li>
          ))}
        </ul>
      ) : null}
      <details className="text-sm">
        <summary className="cursor-pointer font-medium">
          {t("pages.runs.modelInputUse.references")}
        </summary>
        <pre
          className="bg-muted mt-2 max-h-64 overflow-auto rounded p-3 text-xs"
          data-testid="model-input-use-references"
        >
          {JSON.stringify(refs, null, 2)}
        </pre>
      </details>
      {projection.result_status === "resolved" && projection.result_body ? (
        <details
          className="text-sm"
          onToggle={(event) => setBodyExpanded(event.currentTarget.open)}
        >
          <summary className="cursor-pointer font-medium">
            {t("pages.runs.modelInputUse.resultBody")}
          </summary>
          {bodyExpanded ? (
            <pre
              className="bg-muted mt-2 max-h-96 overflow-auto rounded p-3 text-xs"
              data-testid="model-input-use-result-body"
            >
              {JSON.stringify(projection.result_body, null, 2)}
            </pre>
          ) : null}
        </details>
      ) : (
        <p data-testid="model-input-use-body-unavailable">
          {t("pages.runs.genericCycleSimulation.bodyUnavailable")}
        </p>
      )}
    </article>
  );
}

export function ModelInputUseN5ResultHistory({
  inventory,
}: {
  inventory: RunModelInputUseActionsProjection | undefined;
}) {
  const { t } = useI18n();
  const [selectedActionJobId, setSelectedActionJobId] = useState<string | null>(
    null,
  );
  const selectedAction = inventory?.actions.find(
    (action) => action.action_job_id === selectedActionJobId,
  );
  const resultQuery = useRunModelInputUseN5Result(
    inventory,
    selectedActionJobId,
  );

  useEffect(() => {
    if (selectedActionJobId !== null && !selectedAction) {
      setSelectedActionJobId(null);
    }
  }, [selectedAction, selectedActionJobId]);

  if (!inventory) {
    return null;
  }

  const isLimited =
    inventory.inventory_status === "limited" || inventory.inventory_truncated;

  return (
    <Card className="space-y-4" data-testid="model-input-use-history">
      <div className="panel-header">
        <div>
          <h4>{t("pages.runs.modelInputUse.title")}</h4>
        </div>
      </div>
      <p className="text-muted text-sm">
        {t("pages.runs.modelInputUse.discoveryScope")}
      </p>
      <p className="text-sm" data-testid="model-input-use-source-job">
        {t("pages.runs.modelInputUse.runSource", {
          runId: inventory.run_id,
          sourceJobId: inventory.source_job_id,
        })}
      </p>
      {isLimited ? (
        <div role="status" data-testid="model-input-use-inventory-limited">
          <p>{t("pages.runs.modelInputUse.inventoryLimited")}</p>
          {inventory.limitation_codes.length > 0 ? (
            <ul className="list-disc pl-5">
              {inventory.limitation_codes.map((code) => (
                <li key={code}>{code}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      {inventory.actions.length === 0 ? (
        <p data-testid="model-input-use-history-empty">
          {isLimited
            ? t("pages.runs.modelInputUse.noActionsLimited")
            : t("pages.runs.modelInputUse.noActions")}
        </p>
      ) : (
        <>
          <ul className="space-y-2" data-testid="model-input-use-action-list">
            {inventory.actions.map((action) => {
              const isExpanded = selectedActionJobId === action.action_job_id;
              return (
                <li key={action.action_job_id}>
                  <button
                    type="button"
                    className="flex w-full items-center justify-between gap-3 rounded border px-3 py-2 text-left"
                    aria-expanded={isExpanded}
                    data-testid="model-input-use-action-selector"
                    data-action-job-id={action.action_job_id}
                    onClick={() =>
                      setSelectedActionJobId(
                        isExpanded ? null : action.action_job_id,
                      )
                    }
                  >
                    <span>
                      {t("pages.runs.modelInputUse.action", {
                        actionJobId: action.action_job_id,
                      })}
                    </span>
                    <span className="text-muted text-sm">
                      {t("pages.runs.modelInputUse.actionStatus", {
                        status: action.job_state,
                      })}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
          {selectedAction ? (
            <section
              className="space-y-3"
              data-testid="model-input-use-selected-action"
            >
              {resultQuery.isPending ? (
                <p role="status" data-testid="model-input-use-result-loading">
                  {t("common.loading")} {selectedAction.action_job_id}
                </p>
              ) : resultQuery.isError || !resultQuery.data ? (
                <p
                  role="status"
                  data-testid="model-input-use-result-unavailable"
                >
                  {t("pages.runs.modelInputUse.resultUnavailable", {
                    actionJobId: selectedAction.action_job_id,
                    jobState: selectedAction.job_state,
                  })}
                </p>
              ) : (
                <ResultCard projection={resultQuery.data} />
              )}
            </section>
          ) : (
            <p data-testid="model-input-use-action-not-selected">
              {t("pages.runs.modelInputUse.chooseAction")}
            </p>
          )}
        </>
      )}
    </Card>
  );
}
