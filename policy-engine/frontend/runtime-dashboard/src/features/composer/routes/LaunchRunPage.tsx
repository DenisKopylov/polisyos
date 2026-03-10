import { useEffect, useMemo, useRef, useState } from "react";
import { useFieldArray, useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useCapabilities } from "@/api/hooks/useCapabilities";
import {
  useLlmProfiles,
  type ModelProfileInfo,
} from "@/api/hooks/useLlmProfiles";
import { useLaunchNlRun } from "@/api/hooks/useLaunchNlRun";
import { useLaunchRun } from "@/api/hooks/useLaunchRun";
import { useI18n } from "@/i18n/LocaleProvider";
import {
  getCapability,
  isCapabilityEnabled,
  readNumericConstraint,
} from "@/lib/capabilities";
import { cn, formatCurrency, formatNumber } from "@/lib/utils";
import { PrefetchLink } from "@/app/routes/PrefetchLink";
import {
  ApiErrorAlert,
  Badge,
  Button,
  Card,
  Input,
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
import { parseComposerSearchParams } from "../domain/searchParams";
import {
  buildComposerDraftKey,
  deleteComposerDraft,
  loadComposerDraft,
  saveComposerDraft,
} from "../state/composerDraftRepository";
import { useComposerDraftStore } from "../state/useComposerDraftStore";

type Mode = "workflow" | "nl";

function providerBadge(provider: string) {
  const normalized = provider.toLowerCase();
  if (normalized === "openai") return "bg-green-500/10 text-green-700";
  if (normalized === "anthropic") return "bg-amber-500/10 text-amber-700";
  if (normalized === "google") return "bg-sky-500/10 text-sky-700";
  if (normalized === "gonka") return "bg-orange-500/10 text-orange-700";
  return "bg-text/10 text-text";
}

function LaunchReceipt({ runId, status }: { runId: string; status: string }) {
  return (
    <div className="bg-surface/80 rounded-2xl border border-line p-3 text-sm">
      <div className="flex items-center justify-between gap-2">
        <PrefetchLink
          to={`/runs/${runId}/overview`}
          prefetch="intent"
          className="font-mono text-xs text-accent hover:underline"
        >
          {runId}
        </PrefetchLink>
        <span
          className={cn(
            "rounded-full px-2 py-1 text-[11px] font-semibold uppercase tracking-wide",
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
  profile: ModelProfileInfo;
  selected: boolean;
  onToggle: () => void;
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
          <p className="mt-1 font-mono text-[11px] text-muted">
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
      <p className="mt-2 text-sm text-muted">{profile.description}</p>
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted">
        {profile.input_cost_per_mtoken_usd != null ? (
          <span className="rounded-full border border-line px-2 py-1">
            {t("pages.composer.inputCostPerMillion", {
              cost: formatCurrency(profile.input_cost_per_mtoken_usd),
            })}
          </span>
        ) : null}
        {profile.output_cost_per_mtoken_usd != null ? (
          <span className="rounded-full border border-line px-2 py-1">
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
  return message ? <p className="mt-2 text-xs text-danger">{message}</p> : null;
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

function ArrayActions({ onAdd, label }: { onAdd: () => void; label: string }) {
  return (
    <button
      type="button"
      onClick={onAdd}
      className="text-xs font-semibold text-accent underline"
    >
      {label}
    </button>
  );
}

function WorkflowParamList({
  fields,
  register,
  onRemove,
  removeLabel,
  keyPlaceholder,
  valuePlaceholder,
}: {
  fields: Array<{ id: string } & ParamFormValue>;
  register: ReturnType<typeof useForm<WorkflowLaunchFormValues>>["register"];
  onRemove: (index: number) => void;
  removeLabel: string;
  keyPlaceholder: string;
  valuePlaceholder: string;
}) {
  return (
    <div className="space-y-3">
      {fields.map((field, index) => (
        <div
          key={field.id}
          className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]"
        >
          <input
            {...register(`customParams.${index}.key`)}
            aria-label={`${keyPlaceholder} ${index + 1}`}
            placeholder={keyPlaceholder}
            className="atlas-input"
          />
          <input
            {...register(`customParams.${index}.value`)}
            aria-label={`${valuePlaceholder} ${index + 1}`}
            placeholder={valuePlaceholder}
            className="atlas-input"
          />
          <Button type="button" onClick={() => onRemove(index)} variant="ghost">
            {removeLabel}
          </Button>
        </div>
      ))}
    </div>
  );
}

export default function LaunchRunPage() {
  const { locale, t, label } = useI18n();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const capabilitiesQuery = useCapabilities();
  const llmProfilesQuery = useLlmProfiles();
  const launchRunMutation = useLaunchRun();
  const launchNlMutation = useLaunchNlRun();
  const composerSearch = parseComposerSearchParams(searchParams);
  const fromRunId = composerSearch.fromRun;
  const [mode, setMode] = useState<Mode>(
    () => composerSearch.mode ?? (fromRunId ? "workflow" : "nl"),
  );
  const [recentLaunches, setRecentLaunches] = useState<
    Array<{ runId: string; status: string }>
  >([]);
  const [llmModelInput, setLlmModelInput] = useState("");

  const workflowDefaults = useMemo(
    () => buildWorkflowDefaults(t, fromRunId),
    [fromRunId, t],
  );
  const nlDefaults = useMemo(() => buildNaturalLanguageDefaults(t), [t]);

  const workflowForm = useForm<WorkflowLaunchFormValues>({
    defaultValues: workflowDefaults,
    mode: "onChange",
    resolver: zodResolver(workflowLaunchSchema),
  });
  const nlForm = useForm<NaturalLanguageLaunchFormValues>({
    defaultValues: nlDefaults,
    mode: "onChange",
    resolver: zodResolver(naturalLanguageLaunchSchema),
  });

  const workflowOutputs = useFieldArray({
    control: workflowForm.control,
    name: "expectedOutputs",
  });
  const workflowConstraints = useFieldArray({
    control: workflowForm.control,
    name: "governanceConstraints",
  });
  const workflowParams = useFieldArray({
    control: workflowForm.control,
    name: "customParams",
  });
  const nlOutputs = useFieldArray({
    control: nlForm.control,
    name: "expectedOutputs",
  });
  const nlConstraints = useFieldArray({
    control: nlForm.control,
    name: "governanceConstraints",
  });
  const workflowValues = useWatch({ control: workflowForm.control });
  const nlValues = useWatch({ control: nlForm.control });
  const workflowDraftKey = useMemo(
    () => buildComposerDraftKey("workflow", fromRunId),
    [fromRunId],
  );
  const nlDraftKey = useMemo(
    () => buildComposerDraftKey("nl", fromRunId),
    [fromRunId],
  );
  const { clearDraft, drafts, hydrateDraft, upsertDraft } = useComposerDraftStore();
  const hydratedKeysRef = useRef(new Set<string>());
  const [restoredDraftMode, setRestoredDraftMode] = useState<Mode | null>(null);

  const manifest = capabilitiesQuery.data;
  const llmProfiles = llmProfilesQuery.data?.profiles ?? [];
  const multimodelEnabled = isCapabilityEnabled(manifest, "multimodel_nl");
  const preflightEnabled = isCapabilityEnabled(manifest, "required_preflight");
  const autoMaterializationEnabled = isCapabilityEnabled(
    manifest,
    "auto_materialization",
  );
  const maxParallelConstraint = readNumericConstraint(
    manifest,
    "max_parallel_models",
    4,
  );
  const maxIterationsConstraint = readNumericConstraint(
    manifest,
    "max_nl_iterations",
    5,
  );
  const selectedLlmModels = nlForm.watch("selectedLlmModels");
  const selectedProfiles = useMemo(
    () =>
      llmProfiles.filter((profile) =>
        selectedLlmModels.includes(profile.model_id),
      ),
    [llmProfiles, selectedLlmModels],
  );
  const activeDirty =
    mode === "workflow"
      ? workflowForm.formState.isDirty
      : nlForm.formState.isDirty;
  const isPending = launchRunMutation.isPending || launchNlMutation.isPending;
  const activeDraft =
    drafts[mode === "workflow" ? workflowDraftKey : nlDraftKey] ?? null;

  useEffect(() => {
    let cancelled = false;

    void loadComposerDraft(workflowDraftKey).then((draft) => {
      if (cancelled) {
        return;
      }
      hydrateDraft(draft ?? null);
      workflowForm.reset(
        (draft?.values as WorkflowLaunchFormValues | undefined) ??
          workflowDefaults,
      );
      hydratedKeysRef.current.add(workflowDraftKey);
      setRestoredDraftMode((current) =>
        draft ? "workflow" : current === "workflow" ? null : current,
      );
    });

    return () => {
      cancelled = true;
    };
  }, [hydrateDraft, workflowDefaults, workflowDraftKey, workflowForm]);

  useEffect(() => {
    let cancelled = false;

    void loadComposerDraft(nlDraftKey).then((draft) => {
      if (cancelled) {
        return;
      }
      hydrateDraft(draft ?? null);
      nlForm.reset(
        (draft?.values as NaturalLanguageLaunchFormValues | undefined) ??
          nlDefaults,
      );
      hydratedKeysRef.current.add(nlDraftKey);
      setRestoredDraftMode((current) =>
        draft ? "nl" : current === "nl" ? null : current,
      );
    });

    return () => {
      cancelled = true;
    };
  }, [hydrateDraft, nlDefaults, nlDraftKey, nlForm]);

  useEffect(() => {
    if (
      !hydratedKeysRef.current.has(workflowDraftKey) ||
      !workflowForm.formState.isDirty
    ) {
      return;
    }

    const timer = window.setTimeout(() => {
      const draft = {
        fromRunId,
        key: workflowDraftKey,
        mode: "workflow" as const,
        updatedAt: Date.now(),
        values: workflowValues as WorkflowLaunchFormValues,
      };
      upsertDraft(draft);
      void saveComposerDraft(draft);
    }, 400);

    return () => window.clearTimeout(timer);
  }, [
    fromRunId,
    upsertDraft,
    workflowDraftKey,
    workflowForm.formState.isDirty,
    workflowValues,
  ]);

  useEffect(() => {
    if (!hydratedKeysRef.current.has(nlDraftKey) || !nlForm.formState.isDirty) {
      return;
    }

    const timer = window.setTimeout(() => {
      const draft = {
        fromRunId,
        key: nlDraftKey,
        mode: "nl" as const,
        updatedAt: Date.now(),
        values: nlValues as NaturalLanguageLaunchFormValues,
      };
      upsertDraft(draft);
      void saveComposerDraft(draft);
    }, 400);

    return () => window.clearTimeout(timer);
  }, [
    fromRunId,
    nlDraftKey,
    nlForm.formState.isDirty,
    nlValues,
    upsertDraft,
  ]);

  function addRecentLaunch(runId: string, status: string) {
    setRecentLaunches((previous) =>
      [{ runId, status }, ...previous].slice(0, 5),
    );
  }

  function discardDraft(nextMode: Mode) {
    const key = nextMode === "workflow" ? workflowDraftKey : nlDraftKey;
    clearDraft(key);
    void deleteComposerDraft(key);
    setRestoredDraftMode((current) => (current === nextMode ? null : current));
  }

  function toggleModel(modelId: string) {
    const current = nlForm.getValues("selectedLlmModels");
    const next = current.includes(modelId)
      ? current.filter((value) => value !== modelId)
      : [...current, modelId];
    nlForm.setValue("selectedLlmModels", next, {
      shouldDirty: true,
      shouldValidate: true,
    });
  }

  function addCustomModel() {
    const normalized = llmModelInput.trim();
    if (!normalized) {
      return;
    }
    const current = nlForm.getValues("selectedLlmModels");
    if (!current.includes(normalized)) {
      nlForm.setValue("selectedLlmModels", [...current, normalized], {
        shouldDirty: true,
        shouldValidate: true,
      });
    }
    setLlmModelInput("");
  }

  function resetActiveForm() {
    if (mode === "workflow") {
      discardDraft("workflow");
      workflowForm.reset(workflowDefaults);
      return;
    }
    discardDraft("nl");
    nlForm.reset(nlDefaults);
  }

  const capabilityHighlights = [
    getCapability(manifest, "multimodel_nl"),
    getCapability(manifest, "required_preflight"),
    getCapability(manifest, "auto_materialization"),
    getCapability(manifest, "promotion_lane"),
  ].filter((feature): feature is NonNullable<typeof feature> =>
    Boolean(feature),
  );

  const workflowSubmit = workflowForm.handleSubmit((values) => {
    const body = buildWorkflowLaunchRequest(values, {
      locale,
      preflightEnabled,
      autoMaterializationEnabled,
    });
    launchRunMutation.mutate(body, {
      onSuccess: (data) => {
        discardDraft("workflow");
        addRecentLaunch(data.run_id, data.status);
        navigate(`/runs/${data.run_id}/overview`);
      },
    });
  });

  const nlSubmit = nlForm.handleSubmit((values) => {
    const body = buildNaturalLanguageLaunchRequest(values, {
      locale,
      preflightEnabled,
      autoMaterializationEnabled,
      maxParallelConstraint,
      maxIterationsConstraint,
    });
    launchNlMutation.mutate(body, {
      onSuccess: (data) => {
        discardDraft("nl");
        addRecentLaunch(data.run_id, data.status);
        navigate(`/runs/${data.run_id}/overview`);
      },
    });
  });

  return (
    <div className="space-y-5" data-testid="composer-page">
      <h1 className="sr-only">{t("pages.composer.title")}</h1>

      <div className="grid gap-3 rounded-3xl border border-line bg-panel p-3 md:grid-cols-5">
        {(["workflow", "nl", "evidence", "guardrails", "launch"] as const).map(
          (step, index) => {
            const isActive =
              step === "workflow"
                ? mode === "workflow"
                : step === "nl"
                  ? mode === "nl"
                  : true;
            const labelKey = `pages.composer.steps.${step}`;
            return (
              <button
                key={step}
                type={
                  step === "workflow" || step === "nl" ? "button" : "button"
                }
                onClick={
                  step === "workflow" || step === "nl"
                    ? () => setMode(step)
                    : undefined
                }
                disabled={step !== "workflow" && step !== "nl"}
                data-testid={
                  step === "workflow"
                    ? "composer-mode-workflow"
                    : step === "nl"
                      ? "composer-mode-nl"
                      : undefined
                }
                className={cn(
                  "rounded-2xl border px-3 py-4 text-left",
                  isActive
                    ? "border-accent/35 bg-accent/10"
                    : "bg-surface/75 border-line",
                  step !== "workflow" && step !== "nl"
                    ? "cursor-default opacity-75"
                    : "",
                )}
              >
                <span className="block text-xs uppercase tracking-wide text-muted">
                  {index + 1}
                </span>
                <strong className="mt-2 block text-sm">{t(labelKey)}</strong>
              </button>
            );
          },
        )}
      </div>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.55fr)_360px]">
        <Card className="space-y-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="eyebrow">
                {mode === "workflow"
                  ? t("pages.composer.workflow")
                  : t("pages.composer.naturalLanguage")}
              </p>
              <h2>
                {mode === "workflow"
                  ? t("pages.composer.workflowHeading")
                  : t("pages.composer.nlHeading")}
              </h2>
              <p className="topbar-subtitle">{t("pages.composer.subtitle")}</p>
            </div>
            <div className="topbar-actions">
              <Badge kind={activeDirty ? "warn" : "ok"}>
                {activeDirty
                  ? t("pages.composer.unsavedChanges")
                  : t("pages.composer.savedState")}
              </Badge>
              <Button type="button" onClick={resetActiveForm} variant="ghost">
                {t("pages.composer.reset")}
              </Button>
            </div>
          </div>

          {restoredDraftMode === mode && activeDraft ? (
            <div className="bg-warning/5 border-warning/25 rounded-2xl border p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold">
                    {t("pages.composer.restoredDraftTitle")}
                  </p>
                  <p className="mt-1 text-sm text-muted">
                    {t("pages.composer.restoredDraftBody", {
                      updatedAt: new Date(activeDraft.updatedAt).toLocaleString(
                        locale,
                      ),
                    })}
                  </p>
                </div>
                <Button
                  type="button"
                  onClick={() => discardDraft(mode)}
                  variant="ghost"
                >
                  {t("pages.composer.discardDraft")}
                </Button>
              </div>
            </div>
          ) : null}

          {mode === "workflow" ? (
            <form className="space-y-5" onSubmit={workflowSubmit}>
              <div className="grid gap-5 lg:grid-cols-2">
                <div className="bg-surface/75 rounded-2xl border border-line p-4">
                  <p className="eyebrow">{t("pages.composer.operatorBrief")}</p>
                  <textarea
                    {...workflowForm.register("executionIntent")}
                    aria-label={t("pages.composer.operatorBrief")}
                    data-testid="composer-operator-brief"
                    rows={4}
                    placeholder={t("pages.composer.operatorBriefPlaceholder")}
                    className="atlas-textarea mt-3"
                  />
                </div>
                <div className="bg-surface/75 rounded-2xl border border-line p-4">
                  <p className="eyebrow">
                    {t("pages.composer.dataSourceBinding")}
                  </p>
                  <div className="mt-3 space-y-2">
                    {(
                      [
                        ["snapshot", t("pages.composer.dataSource.snapshot")],
                        ["bindings", t("pages.composer.dataSource.bindings")],
                        ["view", t("pages.composer.dataSource.view")],
                      ] as const
                    ).map(([value, itemLabel]) => (
                      <label
                        key={value}
                        className="flex items-center gap-2 text-sm"
                      >
                        <input
                          type="radio"
                          value={value}
                          checked={
                            workflowForm.watch("dataSourceType") === value
                          }
                          onChange={() =>
                            workflowForm.setValue("dataSourceType", value, {
                              shouldDirty: true,
                            })
                          }
                        />
                        <span>{itemLabel}</span>
                      </label>
                    ))}
                  </div>
                  <input
                    {...workflowForm.register("dataSourceRef")}
                    aria-label={t("pages.composer.dataSourceBinding")}
                    placeholder="sha256:..."
                    className="atlas-input atlas-input--mono mt-4"
                  />
                  <FieldError
                    message={
                      workflowForm.formState.errors.dataSourceRef?.message
                    }
                  />
                </div>
              </div>

              <div className="grid gap-3 lg:grid-cols-3">
                <div className="bg-surface/75 rounded-2xl border border-line p-4">
                  <label className="text-sm font-semibold">
                    {t("pages.composer.trinityBundleRef")}
                  </label>
                  <input
                    {...workflowForm.register("trinityRef")}
                    aria-label={t("pages.composer.trinityBundleRef")}
                    placeholder="sha256:trinity"
                    className="atlas-input atlas-input--mono mt-3"
                  />
                </div>
                <div className="bg-surface/75 rounded-2xl border border-line p-4">
                  <label className="text-sm font-semibold">
                    {t("pages.composer.policySpecRef")}
                  </label>
                  <input
                    {...workflowForm.register("policySpecRef")}
                    aria-label={t("pages.composer.policySpecRef")}
                    placeholder="sha256:policy-spec"
                    className="atlas-input atlas-input--mono mt-3"
                  />
                </div>
                <div className="bg-surface/75 rounded-2xl border border-line p-4">
                  <label className="text-sm font-semibold">
                    {t("pages.composer.modelSpecRef")}
                  </label>
                  <input
                    {...workflowForm.register("modelSpecRef")}
                    aria-label={t("pages.composer.modelSpecRef")}
                    placeholder="sha256:model-spec"
                    className="atlas-input atlas-input--mono mt-3"
                  />
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-3">
                <div className="bg-surface/75 rounded-2xl border border-line p-4">
                  <span className="text-sm font-semibold">
                    {t("pages.composer.checkpointPolicy")}
                  </span>
                  <select
                    {...workflowForm.register("checkpointPolicy")}
                    aria-label={t("pages.composer.checkpointPolicy")}
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
                <div className="bg-surface/75 rounded-2xl border border-line p-4">
                  <span className="text-sm font-semibold">
                    {t("pages.composer.expectedOutputs")}
                  </span>
                  <strong className="mt-3 block text-2xl font-semibold">
                    {formatNumber(workflowOutputs.fields.length)}
                  </strong>
                </div>
                <div className="bg-surface/75 rounded-2xl border border-line p-4">
                  <span className="text-sm font-semibold">
                    {t("pages.composer.governanceConstraints")}
                  </span>
                  <strong className="mt-3 block text-2xl font-semibold">
                    {formatNumber(workflowConstraints.fields.length)}
                  </strong>
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-lg font-semibold">
                    {t("pages.composer.expectedOutputs")}
                  </h3>
                  <ArrayActions
                    onAdd={() =>
                      workflowOutputs.append({ kind: "", description: "" })
                    }
                    label={t("pages.composer.addOutput")}
                  />
                </div>
                <div className="space-y-3">
                  {workflowOutputs.fields.map((field, index) => (
                    <div
                      key={field.id}
                      className="bg-surface/75 grid gap-3 rounded-2xl border border-line p-4 md:grid-cols-[220px_minmax(0,1fr)]"
                    >
                      <input
                        {...workflowForm.register(
                          `expectedOutputs.${index}.kind`,
                        )}
                        aria-label={`${t("pages.composer.expectedOutputs")} kind ${index + 1}`}
                        placeholder={t(
                          "pages.composer.expectedOutputKindPlaceholder",
                        )}
                        className="atlas-input"
                      />
                      <textarea
                        {...workflowForm.register(
                          `expectedOutputs.${index}.description`,
                        )}
                        aria-label={`${t("pages.composer.expectedOutputs")} description ${index + 1}`}
                        rows={2}
                        placeholder={t(
                          "pages.composer.expectedOutputDescriptionPlaceholder",
                        )}
                        className="atlas-textarea"
                      />
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-lg font-semibold">
                    {t("pages.composer.governanceConstraints")}
                  </h3>
                  <ArrayActions
                    onAdd={() =>
                      workflowConstraints.append({
                        scope: "",
                        rule: "",
                        severity: "warning",
                      })
                    }
                    label={t("pages.composer.addConstraint")}
                  />
                </div>
                <div className="space-y-3">
                  {workflowConstraints.fields.map((field, index) => (
                    <div
                      key={field.id}
                      className="bg-surface/75 grid gap-3 rounded-2xl border border-line p-4 md:grid-cols-[160px_minmax(0,1fr)_160px]"
                    >
                      <input
                        {...workflowForm.register(
                          `governanceConstraints.${index}.scope`,
                        )}
                        aria-label={`${t("pages.composer.governanceConstraints")} scope ${index + 1}`}
                        placeholder={t(
                          "pages.composer.constraintScopePlaceholder",
                        )}
                        className="atlas-input"
                      />
                      <input
                        {...workflowForm.register(
                          `governanceConstraints.${index}.rule`,
                        )}
                        aria-label={`${t("pages.composer.governanceConstraints")} rule ${index + 1}`}
                        placeholder={t(
                          "pages.composer.constraintRulePlaceholder",
                        )}
                        className="atlas-input"
                      />
                      <select
                        {...workflowForm.register(
                          `governanceConstraints.${index}.severity`,
                        )}
                        aria-label={`${t("pages.composer.governanceConstraints")} severity ${index + 1}`}
                        className="atlas-select"
                      >
                        <option value="info">
                          {label("governanceSeverity", "info", "info")}
                        </option>
                        <option value="warning">
                          {label("governanceSeverity", "warning", "warning")}
                        </option>
                        <option value="blocker">
                          {label("governanceSeverity", "blocker", "blocker")}
                        </option>
                      </select>
                    </div>
                  ))}
                </div>
              </div>

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
                  fields={
                    workflowParams.fields as Array<
                      { id: string } & ParamFormValue
                    >
                  }
                  register={workflowForm.register}
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
                <p className="text-sm text-muted">
                  {t("pages.composer.workflowHelp")}
                </p>
                <Button
                  type="submit"
                  data-testid="composer-launch-workflow"
                  disabled={isPending || !workflowForm.formState.isValid}
                  variant="primary"
                >
                  {launchRunMutation.isPending
                    ? t("pages.composer.launchingWorkflow")
                    : t("pages.composer.launchWorkflow")}
                </Button>
              </div>
            </form>
          ) : (
            <form className="space-y-5" onSubmit={nlSubmit}>
              <div className="bg-surface/75 rounded-2xl border border-line p-4">
                <p className="eyebrow">{t("pages.composer.nlBrief")}</p>
                <textarea
                  {...nlForm.register("nlRequest")}
                  aria-label={t("pages.composer.nlBrief")}
                  data-testid="composer-nl-brief"
                  rows={5}
                  maxLength={10_000}
                  placeholder={t("pages.composer.nlBriefPlaceholder")}
                  className="atlas-textarea mt-3"
                />
                <div className="mt-2 flex items-center justify-between gap-3 text-xs text-muted">
                  <FieldError
                    message={nlForm.formState.errors.nlRequest?.message}
                  />
                  <span>{(nlForm.watch("nlRequest") ?? "").length}/10000</span>
                </div>
              </div>

              <div className="grid gap-5 lg:grid-cols-2">
                <div className="bg-surface/75 rounded-2xl border border-line p-4">
                  <p className="eyebrow">{t("pages.composer.operatorBrief")}</p>
                  <textarea
                    {...nlForm.register("executionIntent")}
                    aria-label={t("pages.composer.operatorBrief")}
                    rows={4}
                    placeholder={t("pages.composer.operatorBriefPlaceholder")}
                    className="atlas-textarea mt-3"
                  />
                </div>
                <div className="bg-surface/75 rounded-2xl border border-line p-4">
                  <label className="text-sm font-semibold">
                    {t("pages.composer.domainHint")}
                  </label>
                  <select
                    {...nlForm.register("domainHint")}
                    aria-label={t("pages.composer.domainHint")}
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
                  <input
                    {...nlForm.register("nlDataSourceRef")}
                    aria-label={t("pages.composer.dataSourceBinding")}
                    data-testid="composer-nl-data-snapshot"
                    placeholder="sha256:data-snapshot"
                    className="atlas-input atlas-input--mono mt-4"
                  />
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-4">
                <div className="bg-surface/75 rounded-2xl border border-line p-4">
                  <span className="text-sm font-semibold">
                    {t("pages.composer.maxIterations")}
                  </span>
                  <input
                    type="number"
                    min={1}
                    max={maxIterationsConstraint}
                    aria-label={t("pages.composer.maxIterations")}
                    {...nlForm.register("maxIterations", {
                      valueAsNumber: true,
                    })}
                    className="atlas-input mt-3"
                  />
                </div>
                <div className="bg-surface/75 rounded-2xl border border-line p-4">
                  <span className="text-sm font-semibold">
                    {t("pages.composer.maxParallelModels")}
                  </span>
                  <input
                    type="number"
                    min={1}
                    max={maxParallelConstraint}
                    disabled={!multimodelEnabled}
                    aria-label={t("pages.composer.maxParallelModels")}
                    {...nlForm.register("maxParallelModels", {
                      valueAsNumber: true,
                    })}
                    className="atlas-input mt-3"
                  />
                </div>
                <div className="bg-surface/75 rounded-2xl border border-line p-4">
                  <span className="text-sm font-semibold">
                    {t("pages.composer.runBudgetUsd")}
                  </span>
                  <input
                    {...nlForm.register("runBudgetUsd")}
                    aria-label={t("pages.composer.runBudgetUsd")}
                    type="number"
                    min={0}
                    step="0.01"
                    className="atlas-input mt-3"
                  />
                </div>
                <div className="bg-surface/75 rounded-2xl border border-line p-4">
                  <span className="text-sm font-semibold">
                    {t("pages.composer.perModelBudgetUsd")}
                  </span>
                  <input
                    {...nlForm.register("perModelBudgetUsd")}
                    aria-label={t("pages.composer.perModelBudgetUsd")}
                    type="number"
                    min={0}
                    step="0.01"
                    className="atlas-input mt-3"
                  />
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-lg font-semibold">
                    {t("pages.composer.expectedOutputs")}
                  </h3>
                  <ArrayActions
                    onAdd={() =>
                      nlOutputs.append({ kind: "", description: "" })
                    }
                    label={t("pages.composer.addOutput")}
                  />
                </div>
                <div className="space-y-3">
                  {nlOutputs.fields.map((field, index) => (
                    <div
                      key={field.id}
                      className="bg-surface/75 grid gap-3 rounded-2xl border border-line p-4 md:grid-cols-[220px_minmax(0,1fr)]"
                    >
                      <input
                        {...nlForm.register(`expectedOutputs.${index}.kind`)}
                        aria-label={`${t("pages.composer.expectedOutputs")} kind ${index + 1}`}
                        placeholder={t(
                          "pages.composer.expectedOutputKindPlaceholder",
                        )}
                        className="atlas-input"
                      />
                      <textarea
                        {...nlForm.register(
                          `expectedOutputs.${index}.description`,
                        )}
                        aria-label={`${t("pages.composer.expectedOutputs")} description ${index + 1}`}
                        rows={2}
                        placeholder={t(
                          "pages.composer.expectedOutputDescriptionPlaceholder",
                        )}
                        className="atlas-textarea"
                      />
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-lg font-semibold">
                    {t("pages.composer.governanceConstraints")}
                  </h3>
                  <ArrayActions
                    onAdd={() =>
                      nlConstraints.append({
                        scope: "",
                        rule: "",
                        severity: "warning",
                      })
                    }
                    label={t("pages.composer.addConstraint")}
                  />
                </div>
                <div className="space-y-3">
                  {nlConstraints.fields.map((field, index) => (
                    <div
                      key={field.id}
                      className="bg-surface/75 grid gap-3 rounded-2xl border border-line p-4 md:grid-cols-[160px_minmax(0,1fr)_160px]"
                    >
                      <input
                        {...nlForm.register(
                          `governanceConstraints.${index}.scope`,
                        )}
                        aria-label={`${t("pages.composer.governanceConstraints")} scope ${index + 1}`}
                        placeholder={t(
                          "pages.composer.constraintScopePlaceholder",
                        )}
                        className="atlas-input"
                      />
                      <input
                        {...nlForm.register(
                          `governanceConstraints.${index}.rule`,
                        )}
                        aria-label={`${t("pages.composer.governanceConstraints")} rule ${index + 1}`}
                        placeholder={t(
                          "pages.composer.constraintRulePlaceholder",
                        )}
                        className="atlas-input"
                      />
                      <select
                        {...nlForm.register(
                          `governanceConstraints.${index}.severity`,
                        )}
                        aria-label={`${t("pages.composer.governanceConstraints")} severity ${index + 1}`}
                        className="atlas-select"
                      >
                        <option value="info">
                          {label("governanceSeverity", "info", "info")}
                        </option>
                        <option value="warning">
                          {label("governanceSeverity", "warning", "warning")}
                        </option>
                        <option value="blocker">
                          {label("governanceSeverity", "blocker", "blocker")}
                        </option>
                      </select>
                    </div>
                  ))}
                </div>
              </div>

              {launchNlMutation.error ? (
                <ApiErrorAlert error={launchNlMutation.error} />
              ) : null}
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-muted">
                  {t("pages.composer.nlHelp")}
                </p>
                <Button
                  type="submit"
                  data-testid="composer-launch-nl"
                  disabled={isPending || !nlForm.formState.isValid}
                  variant="primary"
                >
                  {launchNlMutation.isPending
                    ? t("pages.composer.launchingNaturalLanguage")
                    : t("pages.composer.launchNaturalLanguage")}
                </Button>
              </div>
            </form>
          )}
        </Card>

        <div className="space-y-5">
          <Card className="space-y-4">
            <div className="panel-header">
              <div>
                <p className="eyebrow">{t("pages.composer.summaryTitle")}</p>
                <h3>{t("pages.composer.summaryHeading")}</h3>
              </div>
            </div>
            <div className="space-y-3">
              <div className="bg-surface/75 rounded-2xl border border-line p-4">
                <span className="text-xs uppercase tracking-wide text-muted">
                  {t("pages.composer.plan")}
                </span>
                <strong className="mt-2 block text-lg font-semibold">
                  {preflightEnabled
                    ? t("pages.composer.preflightRequired")
                    : t("pages.composer.preflightOptional")}
                </strong>
              </div>
              <div className="bg-surface/75 rounded-2xl border border-line p-4">
                <span className="text-xs uppercase tracking-wide text-muted">
                  {t("pages.composer.modelComparison")}
                </span>
                <strong className="mt-2 block text-lg font-semibold">
                  {selectedProfiles.length > 0
                    ? t("pages.composer.selectedProfiles", {
                        selected: formatNumber(selectedProfiles.length),
                        available: formatNumber(llmProfiles.length),
                      })
                    : t("pages.composer.noModelProfiles")}
                </strong>
              </div>
              <div className="bg-surface/75 rounded-2xl border border-line p-4">
                <span className="text-xs uppercase tracking-wide text-muted">
                  {t("pages.composer.capabilityContext")}
                </span>
                <strong className="mt-2 block text-lg font-semibold">
                  {t("pages.composer.capabilitiesVisible", {
                    count: formatNumber(capabilityHighlights.length),
                  })}
                </strong>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <h4 className="text-lg font-semibold">
                  {t("pages.composer.modelComparison")}
                </h4>
                <span className="text-xs text-muted">
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
                message={nlForm.formState.errors.selectedLlmModels?.message}
              />
              {llmProfilesQuery.isLoading ? (
                <PanelSkeleton
                  rows={3}
                  className="border-0 bg-transparent p-0"
                />
              ) : null}
              {llmProfilesQuery.isError ? (
                <ApiErrorAlert
                  title={t("pages.composer.modelProfilesLoadError")}
                  error={llmProfilesQuery.error}
                />
              ) : null}
              {!llmProfilesQuery.isLoading && !llmProfilesQuery.isError ? (
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

            <div className="space-y-3">
              <h4 className="text-lg font-semibold">
                {t("pages.composer.runtimeSignalsTitle")}
              </h4>
              <div className="space-y-2">
                {capabilityHighlights.map((feature) => (
                  <div
                    key={feature.key}
                    className="bg-surface/75 rounded-2xl border border-line p-3"
                  >
                    <strong className="block">{feature.label}</strong>
                    <span className="mt-1 block text-sm text-muted">
                      {feature.description || feature.key}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-3">
              <h4 className="text-lg font-semibold">
                {t("pages.composer.recentLaunches")}
              </h4>
              <div className="space-y-2">
                {recentLaunches.map((launch) => (
                  <LaunchReceipt
                    key={launch.runId}
                    runId={launch.runId}
                    status={launch.status}
                  />
                ))}
                {recentLaunches.length === 0 ? (
                  <p className="text-sm text-muted">
                    {t("pages.composer.noLaunchReceipts")}
                  </p>
                ) : null}
              </div>
            </div>
          </Card>
        </div>
      </section>
    </div>
  );
}
