import { useMemo } from "react";

import { useRunFabricDecisionData } from "@/api/hooks/useRunFabricDecisionData";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Card } from "@polisyos/atlas-ui";
import { Quantity } from "@/shared/ui/quantity/Quantity";
import {
  admittedProfileBindingContext,
  alignLineageBatchResponses,
  lineageSelectorsFromQuantities,
  lineageSelectorKey,
  useProfileBindingAdmissions,
  useLineageBatch,
} from "@/shared/ui/quantity/useLineageBatch";
import type {
  LineageGraphView,
  QuantityValue,
  TemporalRef,
} from "@/shared/ui/quantity/quantity.types";

export function RunOverviewProfileLineage({ runId }: { runId: string }) {
  const { t } = useI18n();
  const fabricQuery = useRunFabricDecisionData(runId);
  const responseMatchesRun = fabricQuery.data?.run_id === runId;
  const quantities = responseMatchesRun
    ? (fabricQuery.data?.quantities ?? [])
    : [];
  const temporalScope = useMemo(
    () => temporalRef(fabricQuery.data?.temporal_scope),
    [fabricQuery.data?.temporal_scope],
  );
  const selectors = useMemo(
    () => lineageSelectorsFromQuantities(quantities),
    [quantities],
  );
  const lineageQuery = useLineageBatch(selectors, {
    enabled:
      responseMatchesRun &&
      !fabricQuery.isLoading &&
      temporalScope !== undefined,
    runId,
    temporalScope,
  });
  const admissions = useProfileBindingAdmissions(
    selectors,
    runId,
    temporalScope,
  );
  const admissionsBySelector = new Map(
    selectors.map((selector, index) => [
      lineageSelectorKey(selector),
      admissions[index],
    ]),
  );
  let lineageAlignmentError = false;
  if (lineageQuery.data && !lineageQuery.isError) {
    try {
      alignLineageBatchResponses(selectors, lineageQuery.data, {
        runId,
        temporalScope,
      });
    } catch {
      lineageAlignmentError = true;
    }
  }

  const values = quantities.map((quantity) => {
    const selector = lineageSelectorsFromQuantities([quantity])[0];
    const admission = selector
      ? admissionsBySelector.get(lineageSelectorKey(selector))
      : undefined;
    const currentGraph =
      admission?.outcome === "admitted" &&
      admission.graph?.profileBindingGeneration === admission.generation
        ? admission.graph
        : undefined;
    return profileBoundQuantity(
      quantity,
      selector,
      currentGraph?.lineage,
      runId,
      temporalScope,
      currentGraph?.temporal_scope,
      admission,
      currentGraph?.profileBindingGeneration,
    );
  });
  const hasUnestablishedBinding = values.some(
    (value) => value.profile_binding_status === "not_established",
  );

  return (
    <Card className="space-y-4" data-testid="overview-decision-quantities">
      <div className="panel-header">
        <div>
          <p className="eyebrow">{t("pages.runs.profileLineage.eyebrow")}</p>
          <h4>{t("pages.runs.profileLineage.title")}</h4>
        </div>
      </div>
      {fabricQuery.isLoading ? (
        <p role="status">{t("pages.runs.profileLineage.loading")}</p>
      ) : fabricQuery.isError ? (
        <p role="alert">{t("pages.runs.profileLineage.loadError")}</p>
      ) : !responseMatchesRun ? (
        <p role="alert" data-testid="overview-quantity-run-mismatch">
          {t("pages.runs.profileLineage.runMismatch")}
        </p>
      ) : quantities.length === 0 ? (
        <p data-testid="overview-quantity-empty">
          {t("pages.runs.profileLineage.empty")}
        </p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {values.map((quantity, index) => {
            const ref = quantity.lineage.artifact_ref;
            return (
              <div
                key={`${quantity.metric_id ?? quantity.label ?? "quantity"}-${index}`}
                data-testid="overview-decision-quantity"
                data-lineage-id={quantity.lineage.id}
                data-profile-binding-status={
                  quantity.profile_binding_status ?? "not_established"
                }
                data-selected-artifact-profile={
                  ref?.manifest_profile_sha256 ?? undefined
                }
                data-source-run-id={quantity.lineage.source_run_id ?? undefined}
                data-quantity-metric-id={quantity.metric_id ?? undefined}
                data-profile-origin={quantity.profile_binding_context?.origin}
                data-profile-temporal-scope={
                  quantity.profile_binding_context
                    ? JSON.stringify(
                        quantity.profile_binding_context.temporalScope,
                      )
                    : undefined
                }
              >
                <Quantity
                  value={quantity}
                  variant="table"
                  provenanceMode="always"
                  temporalScope={temporalScope}
                />
              </div>
            );
          })}
        </div>
      )}
      {lineageQuery.isError ||
      lineageAlignmentError ||
      hasUnestablishedBinding ? (
        <p className="text-muted-foreground text-xs" role="status">
          {t("pages.runs.profileLineage.bindingNotEstablished")}
        </p>
      ) : null}
    </Card>
  );
}

function profileBoundQuantity(
  quantity: QuantityValue,
  selector:
    | ReturnType<typeof lineageSelectorsFromQuantities>[number]
    | undefined,
  graph: LineageGraphView | undefined,
  runId: string,
  expectedScope: TemporalRef | null | undefined,
  responseScope: TemporalRef | null | undefined,
  admission: ReturnType<typeof useProfileBindingAdmissions>[number] | undefined,
  graphGeneration: number | undefined,
): QuantityValue {
  const profileBindingContext =
    selector && graph && admission
      ? admittedProfileBindingContext(
          selector,
          graph,
          {
            runId,
            temporalScope: expectedScope,
            responseTemporalScope: responseScope,
          },
          admission,
          graphGeneration,
        )
      : null;
  return {
    ...quantity,
    profile_binding_status: profileBindingContext
      ? "verified"
      : "not_established",
    profile_binding_temporal_scope: expectedScope,
    profile_binding_context: profileBindingContext ?? undefined,
    lineage: {
      ...quantity.lineage,
      trust_metadata:
        profileBindingContext && graph ? (graph.trust_metadata ?? null) : null,
    },
  };
}

function temporalRef(value: unknown): TemporalRef | null | undefined {
  if (value === undefined) return undefined;
  if (value === null) return null;
  if (!isRecord(value)) return undefined;
  const validAt = temporalString(value.valid_at);
  const txAt = temporalString(value.tx_at);
  const branch = temporalString(value.branch);
  const snapshotId = temporalString(value.snapshot_id);
  const scenarioId = temporalString(value.scenario_id);
  return {
    ...(validAt !== undefined ? { valid_at: validAt } : {}),
    ...(txAt !== undefined ? { tx_at: txAt } : {}),
    ...(branch !== undefined ? { branch } : {}),
    ...(snapshotId !== undefined ? { snapshot_id: snapshotId } : {}),
    ...(scenarioId !== undefined ? { scenario_id: scenarioId } : {}),
  };
}

function temporalString(value: unknown): string | null | undefined {
  if (value === undefined) return undefined;
  return typeof value === "string" || value === null ? value : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
