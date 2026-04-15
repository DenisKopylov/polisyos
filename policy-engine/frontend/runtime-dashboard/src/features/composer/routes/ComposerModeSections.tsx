import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  useFieldArray,
  useForm,
  useFormState,
  useWatch,
  type UseFormRegister,
  type UseFormReturn,
} from "react-hook-form";
import { useNavigate } from "react-router-dom";

import { useLaunchNlRun } from "@/api/hooks/useLaunchNlRun";
import { useLaunchRun } from "@/api/hooks/useLaunchRun";
import type { ModelProfileInfo } from "@/api/hooks/useLlmProfiles";
import { useI18n } from "@/i18n/LocaleProvider";
import { cn, formatCurrency, formatDate, formatNumber } from "@/lib/utils";
import { PrefetchLink } from "@/app/routes/PrefetchLink";
import {
  ApiErrorAlert,
  Badge,
  Button,
  Card,
  Input,
  Label,
  PanelSkeleton,
} from "@/shared/ui";
import {
  buildNaturalLanguageLaunchRequest,
  buildWorkflowLaunchRequest,
  naturalLanguageLaunchSchema,
  type NaturalLanguageLaunchFormValues,
  type ParamFormValue,
  type WorkflowLaunchFormValues,
  workflowLaunchSchema,
} from "../domain/forms";
import {
  buildComposerDraftKey,
  deleteComposerDraft,
  loadComposerDraft,
  saveComposerDraft,
  type ComposerDraftMode,
  type ComposerDraftRecord,
  type ComposerDraftValues,
} from "../state/composerDraftRepository";
import { useComposerDraftStore } from "../state/useComposerDraftStore";

type CapabilityHighlight = {
  description?: string | null;
  key: string;
  label: string;
};

type RecentLaunch = {
  runId: string;
  status: string;
};

type SectionSharedProps = {
  autoMaterializationEnabled: boolean;
  capabilityHighlights: CapabilityHighlight[];
  fromRunId: string | null;
  onLaunchCreated: (runId: string, status: string) => void;
  preflightEnabled: boolean;
  recentLaunches: RecentLaunch[];
};

type NaturalLanguageComposerSectionProps = SectionSharedProps & {
  llmProfiles: ModelProfileInfo[];
  llmProfilesError: unknown;
  llmProfilesLoading: boolean;
  maxIterationsConstraint: number;
  maxParallelConstraint: number;
  multimodelEnabled: boolean;
};

const EMPTY_EXPECTED_OUTPUT = {
  description: "",
  kind: "",
};

const EMPTY_GOVERNANCE_CONSTRAINT = {
  rule: "",
  scope: "",
  severity: "warning",
};

function providerBadge(provider: string) {
  const normalized = provider.toLowerCase();
  if (normalized === "openai") return "bg-green-500/10 text-green-700";
  if (normalized === "anthropic") return "bg-amber-500/10 text-amber-700";
  if (normalized === "google") return "bg-sky-500/10 text-sky-700";
  if (normalized === "gonka") return "bg-orange-500/10 text-orange-700";
  return "bg-text/10 text-text";
}

function buildWorkflowDefaults(
  t: ReturnType<typeof useI18n>["t"],
  fromRunId: string | null,
): WorkflowLaunchFormValues {
  return {
    dataSourceType: "snapshot",
    dataSourceRef: "",
    trinityRef: "",
    policySpecRef: "",
    modelSpecRef: "",
    executionIntent: fromRunId
      ? t("pages.composer.replanIntent", { runId: fromRunId })
      : "",
    checkpointPolicy: "strict",
    expectedOutputs: [
      {
        kind: "decision_packet",
        description: t("pages.composer.defaults.decisionPacketDescription"),
      },
      {
        kind: "governance_summary",
        description: t("pages.composer.defaults.governanceSummaryDescription"),
      },
    ],
    governanceConstraints: [
      {
        scope: "legal",
        rule: t("pages.composer.defaults.legalConstraintRule"),
        severity: "blocker",
      },
      {
        scope: "budget",
        rule: t("pages.composer.defaults.budgetConstraintRule"),
        severity: "warning",
      },
    ],
    customParams: [],
  };
}

function buildNaturalLanguageDefaults(
  t: ReturnType<typeof useI18n>["t"],
): NaturalLanguageLaunchFormValues {
  return {
    nlRequest: "",
    executionIntent: "",
    domainHint: "custom",
    selectedLlmModels: [],
    maxParallelModels: 2,
    runBudgetUsd: "",
    perModelBudgetUsd: "",
    maxIterations: 3,
    checkpointPolicy: "strict",
    nlDataSourceRef: "",
    expectedOutputs: [
      {
        kind: "decision_packet",
        description: t("pages.composer.defaults.decisionPacketDescription"),
      },
      {
        kind: "governance_summary",
        description: t("pages.composer.defaults.governanceSummaryDescription"),
      },
    ],
    governanceConstraints: [
      {
        scope: "legal",
        rule: t("pages.composer.defaults.legalConstraintRule"),
        severity: "blocker",
      },
      {
        scope: "budget",
        rule: t("pages.composer.defaults.budgetConstraintRule"),
        severity: "warning",
      },
    ],
  };
}

function LaunchReceipt({ runId, status }: RecentLaunch) {
  return (
    <div className="bg-surface/80 border-line rounded-2xl border p-3 text-sm">
      <div className="flex items-center justify-between gap-2">
        <PrefetchLink
          to={`/runs/${runId}/overview`}
          prefetch="intent"
          className="text-accent font-mono text-xs hover:underline"
        >
          {runId}
        </PrefetchLink>
        <span
          className={cn(
            "rounded-full px-2 py-1 text-[11px] font-semibold tracking-wide uppercase",
            status === "accepted"
              ? "bg-green-500/10 text-green-600"
              : "bg-red-500/10 text-red-500",
          )}
        >
          {status}
        </span>
      </div>
    </div>
  );
}

function ModelProfileCard({
  profile,
  selected,
  onToggle,
}: {
  onToggle: () => void;
  profile: ModelProfileInfo;
  selected: boolean;
}) {
  const { t } = useI18n();

  return (
    <button
      type="button"
      onClick={onToggle}
      data-testid={`llm-profile-${profile.model_id}`}
      className={cn(
        "w-full rounded-2xl border p-3 text-left transition",
        selected
          ? "bg-accent/10 border-accent"
          : "bg-surface/80 hover:border-accent/40 border-line",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-semibold">{profile.display_name}</p>
          <p className="text-muted mt-1 font-mono text-[11px]">
            {profile.model_id}
          </p>
        </div>
        <span
          className={cn(
            "rounded-full px-2 py-1 text-[10px] font-semibold",
            providerBadge(profile.provider),
          )}
        >
          {profile.provider}
        </span>
      </div>
      <p className="text-muted mt-2 text-sm">{profile.description}</p>
      <div className="text-muted mt-3 flex flex-wrap gap-2 text-xs">
        {profile.input_cost_per_mtoken_usd != null ? (
          <span className="border-line rounded-full border px-2 py-1">
            {t("pages.composer.inputCostPerMillion", {
              cost: formatCurrency(profile.input_cost_per_mtoken_usd),
            })}
          </span>
        ) : null}
        {profile.output_cost_per_mtoken_usd != null ? (
          <span className="border-line rounded-full border px-2 py-1">
            {t("pages.composer.outputCostPerMillion", {
              cost: formatCurrency(profile.output_cost_per_mtoken_usd),
            })}
          </span>
        ) : null}
      </div>
    </button>
  );
}

function FieldError({ message }: { message?: string }) {
  return message ? <p className="text-danger mt-2 text-xs">{message}</p> : null;
}

function ArrayActions({ onAdd, label }: { label: string; onAdd: () => void }) {
  return (
    <button
      type="button"
      onClick={onAdd}
      className="text-accent text-xs font-semibold underline"
    >
      {label}
    </button>
  );
}

function WorkflowParamList({
  fields,
  keyPlaceholder,
  onRemove,
  register,
  removeLabel,
  valuePlaceholder,
}: {
  fields: Array<{ id: string } & ParamFormValue>;
  keyPlaceholder: string;
  onRemove: (index: number) => void;
  register: UseFormRegister<WorkflowLaunchFormValues>;
  removeLabel: string;
  valuePlaceholder: string;
}) {
  return (
    <div className="space-y-3">
      {fields.map((field, index) => {
        const keyInputId = `workflow-custom-param-key-${index}`;
        const valueInputId = `workflow-custom-param-value-${index}`;
        return (
          <div
            key={field.id}
            className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]"
          >
            <div>
              <Label htmlFor={keyInputId} className="text-muted text-xs">
                {keyPlaceholder}
              </Label>
              <input
                id={keyInputId}
                {...register(`customParams.${index}.key`)}
                aria-label={`${keyPlaceholder} ${index + 1}`}
                placeholder={keyPlaceholder}
                className="atlas-input mt-1"
              />
            </div>
            <div>
              <Label htmlFor={valueInputId} className="text-muted text-xs">
                {valuePlaceholder}
              </Label>
              <input
                id={valueInputId}
                {...register(`customParams.${index}.value`)}
                aria-label={`${valuePlaceholder} ${index + 1}`}
                placeholder={valuePlaceholder}
                className="atlas-input mt-1"
              />
            </div>
            <div className="flex items-end">
              <Button
                type="button"
                onClick={() => onRemove(index)}
                variant="ghost"
              >
                {removeLabel}
              </Button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ExpectedOutputsEditor<TFieldValues extends ComposerDraftValues>({
  addLabel,
  baseId,
  descriptionPlaceholder,
  fields,
  kindPlaceholder,
  labelText,
  onAppend,
  onRemove,
  register,
  removeLabel,
}: {
  addLabel: string;
  baseId: string;
  descriptionPlaceholder: string;
  fields: Array<{ id: string }>;
  kindPlaceholder: string;
  labelText: string;
  onAppend: () => void;
  onRemove: (index: number) => void;
  register: UseFormRegister<TFieldValues>;
  removeLabel: string;
}) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-lg font-semibold">{labelText}</h3>
        <ArrayActions onAdd={onAppend} label={addLabel} />
      </div>
      <div className="space-y-3">
        {fields.map((field, index) => {
          const kindId = `${baseId}-kind-${index}`;
          const descriptionId = `${baseId}-description-${index}`;
          return (
            <div
              key={field.id}
              className="bg-surface/75 border-line grid gap-3 rounded-2xl border p-4 md:grid-cols-[220px_minmax(0,1fr)_auto]"
            >
              <div>
                <Label htmlFor={kindId} className="text-muted text-xs">
                  {kindPlaceholder}
                </Label>
                <input
                  id={kindId}
                  {...register(`expectedOutputs.${index}.kind` as never)}
                  placeholder={kindPlaceholder}
                  className="atlas-input mt-1"
                />
              </div>
              <div>
                <Label htmlFor={descriptionId} className="text-muted text-xs">
                  {descriptionPlaceholder}
                </Label>
                <textarea
                  id={descriptionId}
                  {...register(
                    `expectedOutputs.${index}.description` as never,
                  )}
                  rows={2}
                  placeholder={descriptionPlaceholder}
                  className="atlas-textarea mt-1"
                />
              </div>
              <div className="flex items-end">
                <Button
                  type="button"
                  onClick={() => onRemove(index)}
                  variant="ghost"
                  aria-label={`${removeLabel} ${labelText} ${index + 1}`}
                >
                  {removeLabel}
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function GovernanceConstraintsEditor<TFieldValues extends ComposerDraftValues>({
  addLabel,
  baseId,
  fields,
  labelFn,
  labelText,
  onAppend,
  onRemove,
  register,
  removeLabel,
  rulePlaceholder,
  scopePlaceholder,
}: {
  addLabel: string;
  baseId: string;
  fields: Array<{ id: string }>;
  labelFn: ReturnType<typeof useI18n>["label"];
  labelText: string;
  onAppend: () => void;
  onRemove: (index: number) => void;
  register: UseFormRegister<TFieldValues>;
  removeLabel: string;
  rulePlaceholder: string;
  scopePlaceholder: string;
}) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-lg font-semibold">{labelText}</h3>
        <ArrayActions onAdd={onAppend} label={addLabel} />
      </div>
      <div className="space-y-3">
        {fields.map((field, index) => {
          const scopeId = `${baseId}-scope-${index}`;
          const ruleId = `${baseId}-rule-${index}`;
          const severityId = `${baseId}-severity-${index}`;
          return (
            <div
              key={field.id}
              className="bg-surface/75 border-line grid gap-3 rounded-2xl border p-4 md:grid-cols-[160px_minmax(0,1fr)_160px_auto]"
            >
              <div>
                <Label htmlFor={scopeId} className="text-muted text-xs">
                  {scopePlaceholder}
                </Label>
                <input
                  id={scopeId}
                  {...register(`governanceConstraints.${index}.scope` as never)}
                  placeholder={scopePlaceholder}
                  className="atlas-input mt-1"
                />
              </div>
              <div>
                <Label htmlFor={ruleId} className="text-muted text-xs">
                  {rulePlaceholder}
                </Label>
                <input
                  id={ruleId}
                  {...register(`governanceConstraints.${index}.rule` as never)}
                  placeholder={rulePlaceholder}
                  className="atlas-input mt-1"
                />
              </div>
              <div>
                <Label htmlFor={severityId} className="text-muted text-xs">
                  Severity
                </Label>
                <select
                  id={severityId}
                  {...register(
                    `governanceConstraints.${index}.severity` as never,
                  )}
                  className="atlas-select mt-1"
                >
                  <option value="info">
                    {labelFn("governanceSeverity", "info", "info")}
                  </option>
                  <option value="warning">
                    {labelFn("governanceSeverity", "warning", "warning")}
                  </option>
                  <option value="blocker">
                    {labelFn("governanceSeverity", "blocker", "blocker")}
                  </option>
                </select>
              </div>
              <div className="flex items-end">
                <Button
                  type="button"
                  onClick={() => onRemove(index)}
                  variant="ghost"
                  aria-label={`${removeLabel} ${labelText} ${index + 1}`}
                >
                  {removeLabel}
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function RecentLaunchesSection({
  recentLaunches,
}: {
  recentLaunches: RecentLaunch[];
}) {
  const { t } = useI18n();

  return (
    <div className="space-y-3">
      <h4 className="text-lg font-semibold">
        {t("pages.composer.recentLaunches")}
      </h4>
      <div className="space-y-2">
        {recentLaunches.map((launch) => (
          <LaunchReceipt key={launch.runId} {...launch} />
        ))}
        {recentLaunches.length === 0 ? (
          <p className="text-muted text-sm">
            {t("pages.composer.noLaunchReceipts")}
          </p>
        ) : null}
      </div>
    </div>
  );
}

function CapabilityHighlightsSection({
  capabilityHighlights,
}: {
  capabilityHighlights: CapabilityHighlight[];
}) {
  const { t } = useI18n();

  return (
    <div className="space-y-3">
      <h4 className="text-lg font-semibold">
        {t("pages.composer.runtimeSignalsTitle")}
      </h4>
      <div className="space-y-2">
        {capabilityHighlights.map((feature) => (
          <div
            key={feature.key}
            className="bg-surface/75 border-line rounded-2xl border p-3"
          >
            <strong className="block">{feature.label}</strong>
            <span className="text-muted mt-1 block text-sm">
              {feature.description || feature.key}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function SummaryCards({
  preflightEnabled,
  selectedProfiles,
  totalProfiles,
  capabilityCount,
}: {
  capabilityCount: number;
  preflightEnabled: boolean;
  selectedProfiles: number;
  totalProfiles: number;
}) {
  const { t } = useI18n();

  return (
    <div className="space-y-3">
      <div className="bg-surface/75 border-line rounded-2xl border p-4">
        <span className="text-muted text-xs tracking-wide uppercase">
          {t("pages.composer.plan")}
        </span>
        <strong className="mt-2 block text-lg font-semibold">
          {preflightEnabled
            ? t("pages.composer.preflightRequired")
            : t("pages.composer.preflightOptional")}
        </strong>
      </div>
      <div className="bg-surface/75 border-line rounded-2xl border p-4">
        <span className="text-muted text-xs tracking-wide uppercase">
          {t("pages.composer.modelComparison")}
        </span>
        <strong className="mt-2 block text-lg font-semibold">
          {selectedProfiles > 0
            ? t("pages.composer.selectedProfiles", {
                selected: formatNumber(selectedProfiles),
                available: formatNumber(totalProfiles),
              })
            : t("pages.composer.noModelProfiles")}
        </strong>
      </div>
      <div className="bg-surface/75 border-line rounded-2xl border p-4">
        <span className="text-muted text-xs tracking-wide uppercase">
          {t("pages.composer.capabilityContext")}
        </span>
        <strong className="mt-2 block text-lg font-semibold">
          {t("pages.composer.capabilitiesVisible", {
            count: formatNumber(capabilityCount),
          })}
        </strong>
      </div>
    </div>
  );
}

function DraftNotice({
  activeDraft,
  onDiscard,
}: {
  activeDraft: ComposerDraftRecord | null;
  onDiscard: () => void;
}) {
  const { locale, t } = useI18n();

  if (!activeDraft) {
    return null;
  }

  return (
    <div className="bg-warning/5 border-warning/25 rounded-2xl border p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">
            {t("pages.composer.restoredDraftTitle")}
          </p>
          <p className="text-muted mt-1 text-sm">
            {t("pages.composer.restoredDraftBody", {
              updatedAt: formatDate(activeDraft.updatedAt, locale),
            })}
          </p>
        </div>
        <Button type="button" onClick={onDiscard} variant="ghost">
          {t("pages.composer.discardDraft")}
        </Button>
      </div>
    </div>
  );
}

function useComposerDraftPersistence<TValues extends ComposerDraftValues>({
  defaults,
  draftKey,
  form,
  fromRunId,
  mode,
}: {
  defaults: TValues;
  draftKey: string;
  form: UseFormReturn<TValues>;
  fromRunId: string | null;
  mode: ComposerDraftMode;
}) {
  const { clearDraft, drafts, hydrateDraft, upsertDraft } =
    useComposerDraftStore();
  const hydratedRef = useRef(false);
  const latestValuesRef = useRef<TValues>(defaults);
  const saveTimerRef = useRef<number | null>(null);
  const persistenceDisabledRef = useRef(false);
  const { isDirty } = useFormState({ control: form.control });
  const dirtyRef = useRef(false);
  const [restoredDraft, setRestoredDraft] = useState<ComposerDraftRecord | null>(
    null,
  );

  useEffect(() => {
    dirtyRef.current = isDirty;
  }, [isDirty]);

  const persistLatest = useCallback(() => {
    const draft: ComposerDraftRecord = {
      fromRunId,
      key: draftKey,
      mode,
      updatedAt: Date.now(),
      values: latestValuesRef.current,
    };
    upsertDraft(draft);
    void saveComposerDraft(draft);
  }, [draftKey, fromRunId, mode, upsertDraft]);

  useEffect(() => {
    let cancelled = false;
    hydratedRef.current = false;
    persistenceDisabledRef.current = false;
    latestValuesRef.current = defaults;
    dirtyRef.current = false;

    void loadComposerDraft(draftKey).then((draft) => {
      if (cancelled) {
        return;
      }
      hydrateDraft(draft ?? null);
      const nextValues = (draft?.values as TValues | undefined) ?? defaults;
      latestValuesRef.current = nextValues;
      form.reset(nextValues);
      hydratedRef.current = true;
      setRestoredDraft(draft ?? null);
    });

    return () => {
      cancelled = true;
    };
  }, [defaults, draftKey, form, hydrateDraft]);

  useEffect(() => {
    const subscription = form.watch((values) => {
      latestValuesRef.current = values as TValues;
      if (!hydratedRef.current || !dirtyRef.current) {
        return;
      }
      persistenceDisabledRef.current = false;
      if (saveTimerRef.current !== null) {
        window.clearTimeout(saveTimerRef.current);
      }
      saveTimerRef.current = window.setTimeout(() => {
        persistLatest();
      }, 400);
    });

    return () => {
      subscription.unsubscribe();
      if (saveTimerRef.current !== null) {
        window.clearTimeout(saveTimerRef.current);
        saveTimerRef.current = null;
      }
      if (
        hydratedRef.current &&
        dirtyRef.current &&
        !persistenceDisabledRef.current
      ) {
        persistLatest();
      }
    };
  }, [form, persistLatest]);

  const discardDraft = useCallback(() => {
    persistenceDisabledRef.current = true;
    dirtyRef.current = false;
    if (saveTimerRef.current !== null) {
      window.clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    clearDraft(draftKey);
    void deleteComposerDraft(draftKey);
    setRestoredDraft(null);
  }, [clearDraft, draftKey]);

  const resetForm = useCallback(() => {
    discardDraft();
    latestValuesRef.current = defaults;
    dirtyRef.current = false;
    form.reset(defaults);
  }, [defaults, discardDraft, form]);

  return {
    activeDraft: (drafts[draftKey] ?? restoredDraft) ?? null,
    discardDraft,
    isDirty,
    resetForm,
  };
}

export function WorkflowComposerSection({
  autoMaterializationEnabled,
  capabilityHighlights,
  fromRunId,
  onLaunchCreated,
  preflightEnabled,
  recentLaunches,
}: SectionSharedProps) {
  const { locale, label, t } = useI18n();
  const navigate = useNavigate();
  const defaults = useMemo(
    () => buildWorkflowDefaults(t, fromRunId),
    [fromRunId, t],
  );
  const form = useForm<WorkflowLaunchFormValues>({
    defaultValues: defaults,
    mode: "onChange",
    resolver: zodResolver(workflowLaunchSchema),
  });
  const launchRunMutation = useLaunchRun();
  const workflowDraftKey = useMemo(
    () => buildComposerDraftKey("workflow", fromRunId),
    [fromRunId],
  );
  const { activeDraft, discardDraft, isDirty, resetForm } =
    useComposerDraftPersistence({
      defaults,
      draftKey: workflowDraftKey,
      form,
      fromRunId,
      mode: "workflow",
    });
  const workflowOutputs = useFieldArray({
    control: form.control,
    name: "expectedOutputs",
  });
  const workflowConstraints = useFieldArray({
    control: form.control,
    name: "governanceConstraints",
  });
  const workflowParams = useFieldArray({
    control: form.control,
    name: "customParams",
  });
  const dataSourceType = useWatch({
    control: form.control,
    name: "dataSourceType",
  });

  const removeOutput = useCallback(
    (index: number) => {
      if (workflowOutputs.fields.length === 1) {
        form.setValue("expectedOutputs.0", EMPTY_EXPECTED_OUTPUT, {
          shouldDirty: true,
          shouldValidate: true,
        });
        return;
      }
      workflowOutputs.remove(index);
    },
    [form, workflowOutputs],
  );

  const removeConstraint = useCallback(
    (index: number) => {
      if (workflowConstraints.fields.length === 1) {
        form.setValue("governanceConstraints.0", EMPTY_GOVERNANCE_CONSTRAINT, {
          shouldDirty: true,
          shouldValidate: true,
        });
        return;
      }
      workflowConstraints.remove(index);
    },
    [form, workflowConstraints],
  );

  const submit = form.handleSubmit((values) => {
    const body = buildWorkflowLaunchRequest(values, {
      locale,
      preflightEnabled,
      autoMaterializationEnabled,
    });
    launchRunMutation.mutate(body, {
      onSuccess: (data) => {
        discardDraft();
        onLaunchCreated(data.run_id, data.status);
        navigate(`/runs/${data.run_id}/overview`);
      },
    });
  });

  return (
    <section className="grid gap-5 xl:grid-cols-[minmax(0,1.55fr)_360px]">
      <Card className="space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="eyebrow">{t("pages.composer.workflow")}</p>
            <h2>{t("pages.composer.workflowHeading")}</h2>
            <p className="topbar-subtitle">{t("pages.composer.subtitle")}</p>
          </div>
          <div className="topbar-actions">
            <Badge kind={isDirty ? "warn" : "ok"}>
              {isDirty
                ? t("pages.composer.unsavedChanges")
                : t("pages.composer.savedState")}
            </Badge>
            <Button type="button" onClick={resetForm} variant="ghost">
              {t("pages.composer.reset")}
            </Button>
          </div>
        </div>

        <DraftNotice activeDraft={activeDraft} onDiscard={discardDraft} />

        <form className="space-y-5" onSubmit={submit}>
          <div className="grid gap-5 lg:grid-cols-2">
            <div className="bg-surface/75 border-line rounded-2xl border p-4">
              <Label htmlFor="workflow-operator-brief" className="eyebrow">
                {t("pages.composer.operatorBrief")}
              </Label>
              <textarea
                id="workflow-operator-brief"
                {...form.register("executionIntent")}
                data-testid="composer-operator-brief"
                rows={4}
                placeholder={t("pages.composer.operatorBriefPlaceholder")}
                className="atlas-textarea mt-3"
              />
            </div>
            <div className="bg-surface/75 border-line rounded-2xl border p-4">
              <p className="eyebrow">{t("pages.composer.dataSourceBinding")}</p>
              <div className="mt-3 space-y-2">
                {(
                  [
                    ["snapshot", t("pages.composer.dataSource.snapshot")],
                    ["bindings", t("pages.composer.dataSource.bindings")],
                    ["view", t("pages.composer.dataSource.view")],
                  ] as const
                ).map(([value, itemLabel]) => (
                  <Label
                    key={value}
                    htmlFor={`workflow-data-source-${value}`}
                    className="flex items-center gap-2 text-sm font-normal"
                  >
                    <input
                      id={`workflow-data-source-${value}`}
                      type="radio"
                      value={value}
                      checked={dataSourceType === value}
                      onChange={() =>
                        form.setValue("dataSourceType", value, {
                          shouldDirty: true,
                        })
                      }
                    />
                    <span>{itemLabel}</span>
                  </Label>
                ))}
              </div>
              <Label
                htmlFor="workflow-data-source-ref"
                className="text-muted mt-4 block text-xs"
              >
                {t("pages.composer.dataSourceBinding")}
              </Label>
              <input
                id="workflow-data-source-ref"
                {...form.register("dataSourceRef")}
                placeholder="sha256:..."
                className="atlas-input atlas-input--mono mt-1"
              />
              <FieldError message={form.formState.errors.dataSourceRef?.message} />
            </div>
          </div>

          <div className="grid gap-3 lg:grid-cols-3">
            <div className="bg-surface/75 border-line rounded-2xl border p-4">
              <Label htmlFor="workflow-trinity-ref" className="text-sm font-semibold">
                {t("pages.composer.trinityBundleRef")}
              </Label>
              <input
                id="workflow-trinity-ref"
                {...form.register("trinityRef")}
                placeholder="sha256:trinity"
                className="atlas-input atlas-input--mono mt-3"
              />
            </div>
            <div className="bg-surface/75 border-line rounded-2xl border p-4">
              <Label
                htmlFor="workflow-policy-spec-ref"
                className="text-sm font-semibold"
              >
                {t("pages.composer.policySpecRef")}
              </Label>
              <input
                id="workflow-policy-spec-ref"
                {...form.register("policySpecRef")}
                placeholder="sha256:policy-spec"
                className="atlas-input atlas-input--mono mt-3"
              />
            </div>
            <div className="bg-surface/75 border-line rounded-2xl border p-4">
              <Label
                htmlFor="workflow-model-spec-ref"
                className="text-sm font-semibold"
              >
                {t("pages.composer.modelSpecRef")}
              </Label>
              <input
                id="workflow-model-spec-ref"
                {...form.register("modelSpecRef")}
                placeholder="sha256:model-spec"
                className="atlas-input atlas-input--mono mt-3"
              />
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <div className="bg-surface/75 border-line rounded-2xl border p-4">
              <Label
                htmlFor="workflow-checkpoint-policy"
                className="text-sm font-semibold"
              >
                {t("pages.composer.checkpointPolicy")}
              </Label>
              <select
                id="workflow-checkpoint-policy"
                {...form.register("checkpointPolicy")}
                className="atlas-select mt-3"
              >
                <option value="strict">
                  {t("pages.composer.checkpointOptions.strict")}
                </option>
                <option value="lenient">
                  {t("pages.composer.checkpointOptions.lenient")}
                </option>
                <option value="disabled">
                  {t("pages.composer.checkpointOptions.disabled")}
                </option>
              </select>
            </div>
            <div className="bg-surface/75 border-line rounded-2xl border p-4">
              <span className="text-sm font-semibold">
                {t("pages.composer.expectedOutputs")}
              </span>
              <strong className="mt-3 block text-2xl font-semibold">
                {formatNumber(workflowOutputs.fields.length)}
              </strong>
            </div>
            <div className="bg-surface/75 border-line rounded-2xl border p-4">
              <span className="text-sm font-semibold">
                {t("pages.composer.governanceConstraints")}
              </span>
              <strong className="mt-3 block text-2xl font-semibold">
                {formatNumber(workflowConstraints.fields.length)}
              </strong>
            </div>
          </div>

          <ExpectedOutputsEditor
            addLabel={t("pages.composer.addOutput")}
            baseId="workflow-output"
            descriptionPlaceholder={t(
              "pages.composer.expectedOutputDescriptionPlaceholder",
            )}
            fields={workflowOutputs.fields}
            kindPlaceholder={t("pages.composer.expectedOutputKindPlaceholder")}
            labelText={t("pages.composer.expectedOutputs")}
            onAppend={() => workflowOutputs.append(EMPTY_EXPECTED_OUTPUT)}
            onRemove={removeOutput}
            register={form.register}
            removeLabel={t("common.remove")}
          />

          <GovernanceConstraintsEditor
            addLabel={t("pages.composer.addConstraint")}
            baseId="workflow-constraint"
            fields={workflowConstraints.fields}
            labelFn={label}
            labelText={t("pages.composer.governanceConstraints")}
            onAppend={() =>
              workflowConstraints.append(EMPTY_GOVERNANCE_CONSTRAINT)
            }
            onRemove={removeConstraint}
            register={form.register}
            removeLabel={t("common.remove")}
            rulePlaceholder={t("pages.composer.constraintRulePlaceholder")}
            scopePlaceholder={t("pages.composer.constraintScopePlaceholder")}
          />

          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-lg font-semibold">
                {t("pages.composer.customParams")}
              </h3>
              <ArrayActions
                onAdd={() => workflowParams.append({ key: "", value: "" })}
                label={t("pages.composer.addParam")}
              />
            </div>
            <WorkflowParamList
              fields={workflowParams.fields as Array<{ id: string } & ParamFormValue>}
              register={form.register}
              onRemove={workflowParams.remove}
              removeLabel={t("common.remove")}
              keyPlaceholder={t("pages.composer.paramKey")}
              valuePlaceholder={t("pages.composer.paramValue")}
            />
          </div>

          {launchRunMutation.error ? (
            <ApiErrorAlert error={launchRunMutation.error} />
          ) : null}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-muted text-sm">{t("pages.composer.workflowHelp")}</p>
            <Button
              type="submit"
              data-testid="composer-launch-workflow"
              disabled={launchRunMutation.isPending || !form.formState.isValid}
              variant="primary"
            >
              {launchRunMutation.isPending
                ? t("pages.composer.launchingWorkflow")
                : t("pages.composer.launchWorkflow")}
            </Button>
          </div>
        </form>
      </Card>

      <div className="space-y-5">
        <Card className="space-y-4">
          <div className="panel-header">
            <div>
              <p className="eyebrow">{t("pages.composer.summaryTitle")}</p>
              <h3>{t("pages.composer.summaryHeading")}</h3>
            </div>
          </div>
          <SummaryCards
            capabilityCount={capabilityHighlights.length}
            preflightEnabled={preflightEnabled}
            selectedProfiles={0}
            totalProfiles={0}
          />
          <CapabilityHighlightsSection capabilityHighlights={capabilityHighlights} />
          <RecentLaunchesSection recentLaunches={recentLaunches} />
        </Card>
      </div>
    </section>
  );
}

export function NaturalLanguageComposerSection({
  autoMaterializationEnabled,
  capabilityHighlights,
  fromRunId,
  llmProfiles,
  llmProfilesError,
  llmProfilesLoading,
  maxIterationsConstraint,
  maxParallelConstraint,
  multimodelEnabled,
  onLaunchCreated,
  preflightEnabled,
  recentLaunches,
}: NaturalLanguageComposerSectionProps) {
  const { locale, label, t } = useI18n();
  const navigate = useNavigate();
  const defaults = useMemo(() => buildNaturalLanguageDefaults(t), [t]);
  const form = useForm<NaturalLanguageLaunchFormValues>({
    defaultValues: defaults,
    mode: "onChange",
    resolver: zodResolver(naturalLanguageLaunchSchema),
  });
  const launchNlMutation = useLaunchNlRun();
  const nlDraftKey = useMemo(
    () => buildComposerDraftKey("nl", fromRunId),
    [fromRunId],
  );
  const { activeDraft, discardDraft, isDirty, resetForm } =
    useComposerDraftPersistence({
      defaults,
      draftKey: nlDraftKey,
      form,
      fromRunId,
      mode: "nl",
    });
  const nlOutputs = useFieldArray({
    control: form.control,
    name: "expectedOutputs",
  });
  const nlConstraints = useFieldArray({
    control: form.control,
    name: "governanceConstraints",
  });
  const selectedLlmModels =
    useWatch({
      control: form.control,
      name: "selectedLlmModels",
    }) ?? [];
  const nlRequest = useWatch({
    control: form.control,
    name: "nlRequest",
  });
  const [llmModelInput, setLlmModelInput] = useState("");
  const selectedProfiles = useMemo(
    () =>
      llmProfiles.filter((profile) =>
        selectedLlmModels.includes(profile.model_id),
      ),
    [llmProfiles, selectedLlmModels],
  );

  const removeOutput = useCallback(
    (index: number) => {
      if (nlOutputs.fields.length === 1) {
        form.setValue("expectedOutputs.0", EMPTY_EXPECTED_OUTPUT, {
          shouldDirty: true,
          shouldValidate: true,
        });
        return;
      }
      nlOutputs.remove(index);
    },
    [form, nlOutputs],
  );

  const removeConstraint = useCallback(
    (index: number) => {
      if (nlConstraints.fields.length === 1) {
        form.setValue("governanceConstraints.0", EMPTY_GOVERNANCE_CONSTRAINT, {
          shouldDirty: true,
          shouldValidate: true,
        });
        return;
      }
      nlConstraints.remove(index);
    },
    [form, nlConstraints],
  );

  function toggleModel(modelId: string) {
    const next = selectedLlmModels.includes(modelId)
      ? selectedLlmModels.filter((value) => value !== modelId)
      : [...selectedLlmModels, modelId];
    form.setValue("selectedLlmModels", next, {
      shouldDirty: true,
      shouldValidate: true,
    });
  }

  function addCustomModel() {
    const normalized = llmModelInput.trim();
    if (!normalized || selectedLlmModels.includes(normalized)) {
      setLlmModelInput("");
      return;
    }
    form.setValue("selectedLlmModels", [...selectedLlmModels, normalized], {
      shouldDirty: true,
      shouldValidate: true,
    });
    setLlmModelInput("");
  }

  const submit = form.handleSubmit((values) => {
    const body = buildNaturalLanguageLaunchRequest(values, {
      locale,
      preflightEnabled,
      autoMaterializationEnabled,
      maxParallelConstraint,
      maxIterationsConstraint,
    });
    launchNlMutation.mutate(body, {
      onSuccess: (data) => {
        discardDraft();
        onLaunchCreated(data.run_id, data.status);
        navigate(`/runs/${data.run_id}/overview`);
      },
    });
  });

  return (
    <section className="grid gap-5 xl:grid-cols-[minmax(0,1.55fr)_360px]">
      <Card className="space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="eyebrow">{t("pages.composer.naturalLanguage")}</p>
            <h2>{t("pages.composer.nlHeading")}</h2>
            <p className="topbar-subtitle">{t("pages.composer.subtitle")}</p>
          </div>
          <div className="topbar-actions">
            <Badge kind={isDirty ? "warn" : "ok"}>
              {isDirty
                ? t("pages.composer.unsavedChanges")
                : t("pages.composer.savedState")}
            </Badge>
            <Button type="button" onClick={resetForm} variant="ghost">
              {t("pages.composer.reset")}
            </Button>
          </div>
        </div>

        <DraftNotice activeDraft={activeDraft} onDiscard={discardDraft} />

        <form className="space-y-5" onSubmit={submit}>
          <div className="bg-surface/75 border-line rounded-2xl border p-4">
            <Label htmlFor="composer-nl-brief" className="eyebrow">
              {t("pages.composer.nlBrief")}
            </Label>
            <textarea
              id="composer-nl-brief"
              {...form.register("nlRequest")}
              data-testid="composer-nl-brief"
              rows={5}
              maxLength={10_000}
              placeholder={t("pages.composer.nlBriefPlaceholder")}
              className="atlas-textarea mt-3"
            />
            <div className="text-muted mt-2 flex items-center justify-between gap-3 text-xs">
              <FieldError message={form.formState.errors.nlRequest?.message} />
              <span>{(nlRequest ?? "").length}/10000</span>
            </div>
          </div>

          <div className="grid gap-5 lg:grid-cols-2">
            <div className="bg-surface/75 border-line rounded-2xl border p-4">
              <Label htmlFor="nl-operator-brief" className="eyebrow">
                {t("pages.composer.operatorBrief")}
              </Label>
              <textarea
                id="nl-operator-brief"
                {...form.register("executionIntent")}
                rows={4}
                placeholder={t("pages.composer.operatorBriefPlaceholder")}
                className="atlas-textarea mt-3"
              />
            </div>
            <div className="bg-surface/75 border-line rounded-2xl border p-4">
              <Label htmlFor="nl-domain-hint" className="text-sm font-semibold">
                {t("pages.composer.domainHint")}
              </Label>
              <select
                id="nl-domain-hint"
                {...form.register("domainHint")}
                className="atlas-select mt-3"
              >
                <option value="custom">
                  {t("pages.composer.domainOptions.custom")}
                </option>
                <option value="labor">
                  {t("pages.composer.domainOptions.labor")}
                </option>
                <option value="trade">
                  {t("pages.composer.domainOptions.trade")}
                </option>
                <option value="energy">
                  {t("pages.composer.domainOptions.energy")}
                </option>
                <option value="public_finance">
                  {t("pages.composer.domainOptions.public_finance")}
                </option>
              </select>
              <Label
                htmlFor="composer-nl-data-snapshot"
                className="text-muted mt-4 block text-xs"
              >
                {t("pages.composer.dataSourceBinding")}
              </Label>
              <input
                id="composer-nl-data-snapshot"
                {...form.register("nlDataSourceRef")}
                data-testid="composer-nl-data-snapshot"
                placeholder="sha256:data-snapshot"
                className="atlas-input atlas-input--mono mt-1"
              />
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-4">
            <div className="bg-surface/75 border-line rounded-2xl border p-4">
              <Label htmlFor="nl-max-iterations" className="text-sm font-semibold">
                {t("pages.composer.maxIterations")}
              </Label>
              <input
                id="nl-max-iterations"
                type="number"
                min={1}
                max={maxIterationsConstraint}
                {...form.register("maxIterations", { valueAsNumber: true })}
                className="atlas-input mt-3"
              />
            </div>
            <div className="bg-surface/75 border-line rounded-2xl border p-4">
              <Label
                htmlFor="nl-max-parallel-models"
                className="text-sm font-semibold"
              >
                {t("pages.composer.maxParallelModels")}
              </Label>
              <input
                id="nl-max-parallel-models"
                type="number"
                min={1}
                max={maxParallelConstraint}
                disabled={!multimodelEnabled}
                {...form.register("maxParallelModels", { valueAsNumber: true })}
                className="atlas-input mt-3"
              />
            </div>
            <div className="bg-surface/75 border-line rounded-2xl border p-4">
              <Label htmlFor="nl-run-budget" className="text-sm font-semibold">
                {t("pages.composer.runBudgetUsd")}
              </Label>
              <input
                id="nl-run-budget"
                {...form.register("runBudgetUsd")}
                type="number"
                min={0}
                step="0.01"
                className="atlas-input mt-3"
              />
            </div>
            <div className="bg-surface/75 border-line rounded-2xl border p-4">
              <Label
                htmlFor="nl-per-model-budget"
                className="text-sm font-semibold"
              >
                {t("pages.composer.perModelBudgetUsd")}
              </Label>
              <input
                id="nl-per-model-budget"
                {...form.register("perModelBudgetUsd")}
                type="number"
                min={0}
                step="0.01"
                className="atlas-input mt-3"
              />
            </div>
          </div>

          <ExpectedOutputsEditor
            addLabel={t("pages.composer.addOutput")}
            baseId="nl-output"
            descriptionPlaceholder={t(
              "pages.composer.expectedOutputDescriptionPlaceholder",
            )}
            fields={nlOutputs.fields}
            kindPlaceholder={t("pages.composer.expectedOutputKindPlaceholder")}
            labelText={t("pages.composer.expectedOutputs")}
            onAppend={() => nlOutputs.append(EMPTY_EXPECTED_OUTPUT)}
            onRemove={removeOutput}
            register={form.register}
            removeLabel={t("common.remove")}
          />

          <GovernanceConstraintsEditor
            addLabel={t("pages.composer.addConstraint")}
            baseId="nl-constraint"
            fields={nlConstraints.fields}
            labelFn={label}
            labelText={t("pages.composer.governanceConstraints")}
            onAppend={() => nlConstraints.append(EMPTY_GOVERNANCE_CONSTRAINT)}
            onRemove={removeConstraint}
            register={form.register}
            removeLabel={t("common.remove")}
            rulePlaceholder={t("pages.composer.constraintRulePlaceholder")}
            scopePlaceholder={t("pages.composer.constraintScopePlaceholder")}
          />

          {launchNlMutation.error ? (
            <ApiErrorAlert error={launchNlMutation.error} />
          ) : null}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-muted text-sm">{t("pages.composer.nlHelp")}</p>
            <Button
              type="submit"
              data-testid="composer-launch-nl"
              disabled={launchNlMutation.isPending || !form.formState.isValid}
              variant="primary"
            >
              {launchNlMutation.isPending
                ? t("pages.composer.launchingNaturalLanguage")
                : t("pages.composer.launchNaturalLanguage")}
            </Button>
          </div>
        </form>
      </Card>

      <div className="space-y-5">
        <Card className="space-y-4">
          <div className="panel-header">
            <div>
              <p className="eyebrow">{t("pages.composer.summaryTitle")}</p>
              <h3>{t("pages.composer.summaryHeading")}</h3>
            </div>
          </div>
          <SummaryCards
            capabilityCount={capabilityHighlights.length}
            preflightEnabled={preflightEnabled}
            selectedProfiles={selectedProfiles.length}
            totalProfiles={llmProfiles.length}
          />

          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <h4 className="text-lg font-semibold">
                {t("pages.composer.modelComparison")}
              </h4>
              <span className="text-muted text-xs">
                {t("pages.composer.selectedProfiles", {
                  selected: formatNumber(selectedProfiles.length),
                  available: formatNumber(llmProfiles.length),
                })}
              </span>
            </div>
            <div className="flex gap-2">
              <Input
                type="text"
                value={llmModelInput}
                onChange={(event) => setLlmModelInput(event.target.value)}
                aria-label={t("pages.composer.modelComparison")}
                placeholder="openai/gpt-5.4"
              />
              <Button type="button" onClick={addCustomModel} variant="ghost">
                {t("pages.composer.addModel")}
              </Button>
            </div>
            <FieldError
              message={form.formState.errors.selectedLlmModels?.message}
            />
            {llmProfilesLoading ? (
              <PanelSkeleton rows={3} className="border-0 bg-transparent p-0" />
            ) : null}
            {llmProfilesError ? (
              <ApiErrorAlert
                title={t("pages.composer.modelProfilesLoadError")}
                error={llmProfilesError}
              />
            ) : null}
            {!llmProfilesLoading && !llmProfilesError ? (
              <div className="space-y-2">
                {llmProfiles.slice(0, 4).map((profile) => (
                  <ModelProfileCard
                    key={profile.profile_id}
                    profile={profile}
                    selected={selectedLlmModels.includes(profile.model_id)}
                    onToggle={() => toggleModel(profile.model_id)}
                  />
                ))}
              </div>
            ) : null}
          </div>

          <CapabilityHighlightsSection capabilityHighlights={capabilityHighlights} />
          <RecentLaunchesSection recentLaunches={recentLaunches} />
        </Card>
      </div>
    </section>
  );
}
