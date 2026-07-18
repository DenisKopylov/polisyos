import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
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
import { useI18n } from "@/shared/i18n/LocaleProvider";
import {
  cn,
  formatCurrency,
  formatDate,
  formatNumber,
} from "@/shared/lib/utils";
import { PrefetchLink } from "@/app/routes/PrefetchLink";
import { Glyph } from "@/shared/brand/Glyph";
import type { GlyphName } from "@/shared/brand/glyph-vocabulary";
import {
  Badge,
  Button,
  Input,
  Label,
  PanelSkeleton,
  Radio,
  Select,
  Textarea,
} from "@polisyos/atlas-ui";
import { ApiErrorAlert } from "@/shared/ui";
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

const CAPABILITY_GLYPHS: Record<string, GlyphName> = {
  auto_materialization: "evidence",
  multimodel_nl: "counterfactual",
  promotion_lane: "transport",
  required_preflight: "governance-pass",
};

function providerBadge(provider: string) {
  const normalized = provider.toLowerCase();
  if (normalized === "openai") return "bg-green-500/10 text-green-700";
  if (normalized === "anthropic") return "bg-amber-500/10 text-amber-700";
  if (normalized === "google") return "bg-sky-500/10 text-sky-700";
  if (normalized === "gonka") return "bg-orange-500/10 text-orange-700";
  return "bg-text/10 text-text";
}

function resolveCapabilityGlyph(key: string): GlyphName {
  return CAPABILITY_GLYPHS[key] ?? "intervention";
}

function resolveLaunchBadgeKind(
  status: string,
): "ok" | "warn" | "fail" | "neutral" {
  const normalized = status.trim().toLowerCase();
  if (["accepted", "completed", "success", "succeeded"].includes(normalized)) {
    return "ok";
  }
  if (["blocked", "error", "failed", "rejected"].includes(normalized)) {
    return "fail";
  }
  if (["pending", "queued", "review"].includes(normalized)) {
    return "warn";
  }
  return "neutral";
}

function AtlasFormSection({
  children,
  description,
  eyebrow,
  glyph,
  title,
  tone = "default",
  trailing,
}: {
  children: ReactNode;
  description?: string;
  eyebrow: string;
  glyph: GlyphName;
  title: string;
  tone?: "accent" | "default";
  trailing?: ReactNode;
}) {
  return (
    <section
      className={cn(
        "rounded-[28px] border p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.55)] md:p-6",
        tone === "accent"
          ? "border-[rgba(28,139,130,0.14)] bg-[linear-gradient(145deg,rgba(28,139,130,0.12),rgba(181,139,43,0.07)),rgba(255,255,255,0.76)]"
          : "border-[rgba(23,25,29,0.08)] bg-white/70",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-3xl space-y-3">
          <div className="flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-full bg-[rgba(23,25,29,0.06)]">
              <Glyph decorative name={glyph} size={16} />
            </span>
            <div>
              <p className="eyebrow">{eyebrow}</p>
              <h3 className="text-xl font-semibold tracking-[-0.03em]">
                {title}
              </h3>
            </div>
          </div>
          {description ? (
            <p className="text-muted text-sm leading-6">{description}</p>
          ) : null}
        </div>
        {trailing}
      </div>
      <div className="mt-5 space-y-4">{children}</div>
    </section>
  );
}

function AtlasMetricTile({
  hint,
  label,
  value,
}: {
  hint?: string;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-[22px] border border-[rgba(23,25,29,0.07)] bg-white/64 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.55)]">
      <span className="text-muted block text-xs tracking-[0.12em] uppercase">
        {label}
      </span>
      <strong className="mt-2 block text-2xl font-semibold tracking-[-0.04em]">
        {value}
      </strong>
      {hint ? (
        <p className="text-muted mt-2 text-sm leading-6">{hint}</p>
      ) : null}
    </div>
  );
}

function AtlasRail({ children }: { children: ReactNode }) {
  return (
    <aside className="xl:sticky xl:top-6">
      <div className="space-y-5 rounded-[30px] bg-[linear-gradient(180deg,rgba(38,49,58,0.98),rgba(20,22,26,0.96))] p-5 text-[#f5f0e6] shadow-[0_26px_40px_rgba(23,25,29,0.18)] md:p-6">
        {children}
      </div>
    </aside>
  );
}

function AtlasRailSection({
  children,
  eyebrow,
  title,
}: {
  children: ReactNode;
  eyebrow: string;
  title: string;
}) {
  return (
    <section className="space-y-3 border-t border-white/10 pt-5 first:border-t-0 first:pt-0">
      <div>
        <p className="font-mono text-[11px] tracking-[0.12em] text-white/52 uppercase">
          {eyebrow}
        </p>
        <h4 className="mt-2 text-lg font-semibold tracking-[-0.03em] text-[#fff8ef]">
          {title}
        </h4>
      </div>
      {children}
    </section>
  );
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
    <div className="rounded-[18px] border border-white/10 bg-white/5 p-3 text-sm">
      <div className="flex items-center justify-between gap-2">
        <PrefetchLink
          to={`/runs/${runId}/overview`}
          prefetch="intent"
          className="font-mono text-xs text-white/88 hover:text-white hover:underline"
        >
          {runId}
        </PrefetchLink>
        <Badge
          kind={resolveLaunchBadgeKind(status)}
          className="px-2 py-1 text-[10px]"
        >
          {status}
        </Badge>
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
        "w-full rounded-[22px] border p-4 text-left transition-colors",
        selected
          ? "border-[rgba(28,139,130,0.35)] bg-[linear-gradient(180deg,rgba(28,139,130,0.16),rgba(255,255,255,0.78))]"
          : "border-[rgba(23,25,29,0.07)] bg-white/68 hover:border-[rgba(28,139,130,0.22)]",
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
    <Button type="button" onClick={onAdd} size="sm" variant="ghost">
      {label}
    </Button>
  );
}

function AtlasRadioCard({
  checked,
  id,
  label,
  meta,
  name,
  onChange,
  value,
}: {
  checked: boolean;
  id: string;
  label: string;
  meta?: string;
  name?: string;
  onChange: () => void;
  value: string;
}) {
  return (
    <Label
      htmlFor={id}
      className="atlas-choice-card"
      data-selected={checked ? "true" : "false"}
    >
      <Radio
        id={id}
        name={name}
        value={value}
        checked={checked}
        onChange={onChange}
      />
      <span className="atlas-choice-card__body">
        <span className="atlas-choice-card__title">{label}</span>
        {meta ? <span className="atlas-choice-card__meta">{meta}</span> : null}
      </span>
    </Label>
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
            className="grid gap-3 rounded-[22px] border border-[rgba(23,25,29,0.06)] bg-white/58 p-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]"
          >
            <div>
              <Label htmlFor={keyInputId} className="text-muted text-xs">
                {keyPlaceholder}
              </Label>
              <Input
                id={keyInputId}
                {...register(`customParams.${index}.key`)}
                aria-label={`${keyPlaceholder} ${index + 1}`}
                placeholder={keyPlaceholder}
                className="mt-1"
              />
            </div>
            <div>
              <Label htmlFor={valueInputId} className="text-muted text-xs">
                {valuePlaceholder}
              </Label>
              <Input
                id={valueInputId}
                {...register(`customParams.${index}.value`)}
                aria-label={`${valuePlaceholder} ${index + 1}`}
                placeholder={valuePlaceholder}
                className="mt-1"
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
  description,
  baseId,
  descriptionPlaceholder,
  eyebrow,
  fields,
  kindPlaceholder,
  labelText,
  onAppend,
  onRemove,
  register,
  removeLabel,
}: {
  addLabel: string;
  description: string;
  baseId: string;
  descriptionPlaceholder: string;
  eyebrow: string;
  fields: Array<{ id: string }>;
  kindPlaceholder: string;
  labelText: string;
  onAppend: () => void;
  onRemove: (index: number) => void;
  register: UseFormRegister<TFieldValues>;
  removeLabel: string;
}) {
  return (
    <AtlasFormSection
      eyebrow={eyebrow}
      glyph="evidence"
      title={labelText}
      description={description}
      trailing={
        <div className="flex items-center gap-2">
          <Badge kind="neutral" className="px-2 py-1 text-[10px]">
            {formatNumber(fields.length)}
          </Badge>
          <ArrayActions onAdd={onAppend} label={addLabel} />
        </div>
      }
    >
      <div className="space-y-3">
        {fields.map((field, index) => {
          const kindId = `${baseId}-kind-${index}`;
          const descriptionId = `${baseId}-description-${index}`;
          return (
            <div
              key={field.id}
              className="grid gap-3 rounded-[22px] border border-[rgba(23,25,29,0.06)] bg-white/58 p-4 md:grid-cols-[220px_minmax(0,1fr)_auto]"
            >
              <div>
                <Label htmlFor={kindId} className="text-muted text-xs">
                  {kindPlaceholder}
                </Label>
                <Input
                  id={kindId}
                  {...register(`expectedOutputs.${index}.kind` as never)}
                  placeholder={kindPlaceholder}
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor={descriptionId} className="text-muted text-xs">
                  {descriptionPlaceholder}
                </Label>
                <Textarea
                  id={descriptionId}
                  {...register(`expectedOutputs.${index}.description` as never)}
                  rows={2}
                  placeholder={descriptionPlaceholder}
                  className="mt-1"
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
    </AtlasFormSection>
  );
}

function GovernanceConstraintsEditor<TFieldValues extends ComposerDraftValues>({
  addLabel,
  description,
  baseId,
  eyebrow,
  fields,
  labelFn,
  labelText,
  onAppend,
  onRemove,
  register,
  removeLabel,
  rulePlaceholder,
  severityLabel,
  scopePlaceholder,
}: {
  addLabel: string;
  description: string;
  baseId: string;
  eyebrow: string;
  fields: Array<{ id: string }>;
  labelFn: ReturnType<typeof useI18n>["label"];
  labelText: string;
  onAppend: () => void;
  onRemove: (index: number) => void;
  register: UseFormRegister<TFieldValues>;
  removeLabel: string;
  rulePlaceholder: string;
  severityLabel: string;
  scopePlaceholder: string;
}) {
  return (
    <AtlasFormSection
      eyebrow={eyebrow}
      glyph="governance-pass"
      title={labelText}
      description={description}
      trailing={
        <div className="flex items-center gap-2">
          <Badge kind="neutral" className="px-2 py-1 text-[10px]">
            {formatNumber(fields.length)}
          </Badge>
          <ArrayActions onAdd={onAppend} label={addLabel} />
        </div>
      }
    >
      <div className="space-y-3">
        {fields.map((field, index) => {
          const scopeId = `${baseId}-scope-${index}`;
          const ruleId = `${baseId}-rule-${index}`;
          const severityId = `${baseId}-severity-${index}`;
          return (
            <div
              key={field.id}
              className="grid gap-6 rounded-[22px] border border-[rgba(23,25,29,0.06)] bg-white/58 p-4 md:grid-cols-[160px_minmax(0,1fr)_160px_auto]"
            >
              <div>
                <Label htmlFor={scopeId} className="text-muted text-xs">
                  {scopePlaceholder}
                </Label>
                <Input
                  id={scopeId}
                  {...register(`governanceConstraints.${index}.scope` as never)}
                  placeholder={scopePlaceholder}
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor={ruleId} className="text-muted text-xs">
                  {rulePlaceholder}
                </Label>
                <Input
                  id={ruleId}
                  {...register(`governanceConstraints.${index}.rule` as never)}
                  placeholder={rulePlaceholder}
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor={severityId} className="text-muted text-xs">
                  {severityLabel}
                </Label>
                <Select
                  id={severityId}
                  {...register(
                    `governanceConstraints.${index}.severity` as never,
                  )}
                  className="mt-1"
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
                </Select>
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
    </AtlasFormSection>
  );
}

function RecentLaunchesSection({
  recentLaunches,
}: {
  recentLaunches: RecentLaunch[];
}) {
  const { t } = useI18n();

  return (
    <AtlasRailSection
      eyebrow={t("pages.composer.steps.launch")}
      title={t("pages.composer.recentLaunches")}
    >
      <div className="space-y-2">
        {recentLaunches.map((launch) => (
          <LaunchReceipt key={launch.runId} {...launch} />
        ))}
        {recentLaunches.length === 0 ? (
          <p className="text-sm text-white/72">
            {t("pages.composer.noLaunchReceipts")}
          </p>
        ) : null}
      </div>
    </AtlasRailSection>
  );
}

function CapabilityHighlightsSection({
  capabilityHighlights,
}: {
  capabilityHighlights: CapabilityHighlight[];
}) {
  const { t } = useI18n();

  return (
    <AtlasRailSection
      eyebrow={t("pages.composer.capabilityContext")}
      title={t("pages.composer.runtimeSignalsTitle")}
    >
      <div className="space-y-2">
        {capabilityHighlights.map((feature) => (
          <div
            key={feature.key}
            className="rounded-[18px] border border-white/10 bg-white/5 p-3"
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <span className="grid size-8 place-items-center rounded-full bg-white/8">
                  <Glyph
                    decorative
                    intent="verified"
                    name={resolveCapabilityGlyph(feature.key)}
                    size={14}
                  />
                </span>
                <strong className="block text-[#fff8ef]">
                  {feature.label}
                </strong>
              </div>
              <Badge kind="neutral" className="bg-white/10 text-white/70">
                {feature.key}
              </Badge>
            </div>
            <span className="mt-2 block text-sm leading-6 text-white/70">
              {feature.description || feature.key}
            </span>
          </div>
        ))}
      </div>
    </AtlasRailSection>
  );
}

function SummaryCards({
  constraintCount,
  expectedOutputsCount,
  preflightEnabled,
}: {
  constraintCount: number;
  expectedOutputsCount: number;
  preflightEnabled: boolean;
}) {
  const { t } = useI18n();

  return (
    <AtlasRailSection
      eyebrow={t("pages.composer.summaryTitle")}
      title={t("pages.composer.summaryHeading")}
    >
      <div className="grid gap-3">
        <div className="rounded-[20px] border border-white/10 bg-white/5 p-4">
          <span className="block font-mono text-[11px] tracking-[0.12em] text-white/52 uppercase">
            {t("pages.composer.plan")}
          </span>
          <strong className="mt-2 block text-lg font-semibold text-[#fff8ef]">
            {preflightEnabled
              ? t("pages.composer.preflightRequired")
              : t("pages.composer.preflightOptional")}
          </strong>
        </div>
        <div className="rounded-[20px] border border-white/10 bg-white/5 p-4">
          <span className="block font-mono text-[11px] tracking-[0.12em] text-white/52 uppercase">
            {t("pages.composer.expectedOutputs")}
          </span>
          <strong className="mt-2 block text-lg font-semibold text-[#fff8ef]">
            {formatNumber(expectedOutputsCount)}
          </strong>
        </div>
        <div className="rounded-[20px] border border-white/10 bg-white/5 p-4">
          <span className="block font-mono text-[11px] tracking-[0.12em] text-white/52 uppercase">
            {t("pages.composer.governanceConstraints")}
          </span>
          <strong className="mt-2 block text-lg font-semibold text-[#fff8ef]">
            {formatNumber(constraintCount)}
          </strong>
        </div>
      </div>
    </AtlasRailSection>
  );
}

function ModelSelectionRail({
  addCustomModel,
  formError,
  llmModelInput,
  llmProfiles,
  llmProfilesError,
  llmProfilesLoading,
  onModelInputChange,
  selectedLlmModels,
  selectedProfiles,
  toggleModel,
}: {
  addCustomModel: () => void;
  formError?: string;
  llmModelInput: string;
  llmProfiles: ModelProfileInfo[];
  llmProfilesError: unknown;
  llmProfilesLoading: boolean;
  onModelInputChange: (value: string) => void;
  selectedLlmModels: string[];
  selectedProfiles: ModelProfileInfo[];
  toggleModel: (modelId: string) => void;
}) {
  const { t } = useI18n();

  return (
    <AtlasRailSection
      eyebrow={t("pages.composer.selectedProfileSummary")}
      title={t("pages.composer.modelComparison")}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm text-white/72">
          {t("pages.composer.selectedProfiles", {
            selected: formatNumber(selectedProfiles.length),
            available: formatNumber(llmProfiles.length),
          })}
        </span>
        <Badge kind="neutral" className="bg-white/10 text-white/70">
          {formatNumber(selectedLlmModels.length)}
        </Badge>
      </div>
      <div className="flex gap-2">
        <Input
          type="text"
          value={llmModelInput}
          onChange={(event) => onModelInputChange(event.target.value)}
          aria-label={t("pages.composer.modelComparison")}
          placeholder={t("pages.composer.modelPlaceholder")}
          className="border-white/10 bg-white/10 text-white placeholder:text-white/40"
        />
        <Button type="button" onClick={addCustomModel} variant="ghost">
          {t("pages.composer.addModel")}
        </Button>
      </div>
      {formError ? <p className="text-danger text-xs">{formError}</p> : null}
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
    </AtlasRailSection>
  );
}

function ComposerSectionHeader({
  actions,
  eyebrow,
  subtitle,
  title,
}: {
  actions: ReactNode;
  eyebrow: string;
  subtitle: string;
  title: string;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="max-w-3xl">
        <p className="eyebrow">{eyebrow}</p>
        <h2 className="mt-2 text-[clamp(1.8rem,3vw,2.6rem)] leading-[0.98] font-extrabold tracking-[-0.05em]">
          {title}
        </h2>
        <p className="topbar-subtitle mt-3">{subtitle}</p>
      </div>
      <div className="topbar-actions">{actions}</div>
    </div>
  );
}

function ComposerActionRow({
  action,
  help,
}: {
  action: ReactNode;
  help: string;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-[24px] border border-[rgba(23,25,29,0.08)] bg-white/70 px-5 py-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.55)]">
      <p className="text-muted text-sm leading-6">{help}</p>
      {action}
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
    <div className="rounded-[24px] border border-[rgba(181,139,43,0.26)] bg-[linear-gradient(180deg,rgba(181,139,43,0.12),rgba(255,255,255,0.76))] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.55)]">
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
  const [restoredDraft, setRestoredDraft] =
    useState<ComposerDraftRecord | null>(null);

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
    activeDraft: drafts[draftKey] ?? restoredDraft ?? null,
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
  const workflowCheckpointPolicy = useWatch({
    control: form.control,
    name: "checkpointPolicy",
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
      <div className="space-y-5">
        <ComposerSectionHeader
          eyebrow={t("pages.composer.workflow")}
          title={t("pages.composer.workflowHeading")}
          subtitle={t("pages.composer.subtitle")}
          actions={
            <>
              <Badge kind={isDirty ? "warn" : "ok"}>
                {isDirty
                  ? t("pages.composer.unsavedChanges")
                  : t("pages.composer.savedState")}
              </Badge>
              <Button type="button" onClick={resetForm} variant="ghost">
                {t("pages.composer.reset")}
              </Button>
            </>
          }
        />

        <DraftNotice activeDraft={activeDraft} onDiscard={discardDraft} />

        <form className="space-y-5" onSubmit={submit}>
          <AtlasFormSection
            eyebrow={t("pages.composer.steps.workflow")}
            glyph="intervention"
            title={t("pages.composer.operatorBrief")}
            description={t("pages.composer.stepBodies.workflow")}
            tone="accent"
          >
            <div className="grid gap-5 lg:grid-cols-2">
              <div className="rounded-[22px] border border-[rgba(23,25,29,0.06)] bg-white/58 p-4">
                <Label htmlFor="workflow-operator-brief" className="eyebrow">
                  {t("pages.composer.operatorBrief")}
                </Label>
                <Textarea
                  id="workflow-operator-brief"
                  {...form.register("executionIntent")}
                  data-testid="composer-operator-brief"
                  rows={4}
                  placeholder={t("pages.composer.operatorBriefPlaceholder")}
                  className="mt-3"
                />
              </div>
              <div className="rounded-[22px] border border-[rgba(23,25,29,0.06)] bg-white/58 p-4">
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
                    <AtlasRadioCard
                      key={value}
                      id={`workflow-data-source-${value}`}
                      name="workflow-data-source"
                      value={value}
                      label={itemLabel}
                      checked={dataSourceType === value}
                      onChange={() =>
                        form.setValue("dataSourceType", value, {
                          shouldDirty: true,
                        })
                      }
                    />
                  ))}
                </div>
                <Label
                  htmlFor="workflow-data-source-ref"
                  className="text-muted mt-4 block text-xs"
                >
                  {t("pages.composer.dataSourceBinding")}
                </Label>
                <Input
                  id="workflow-data-source-ref"
                  {...form.register("dataSourceRef")}
                  placeholder={t("pages.composer.placeholders.sha256")}
                  className="atlas-input--mono mt-1"
                />
                <FieldError
                  message={form.formState.errors.dataSourceRef?.message}
                />
              </div>
            </div>
          </AtlasFormSection>

          <AtlasFormSection
            eyebrow={t("pages.composer.steps.evidence")}
            glyph="evidence"
            title={t("pages.composer.plan")}
            description={t("pages.composer.stepBodies.evidence")}
          >
            <div className="grid gap-3 md:grid-cols-3">
              <AtlasMetricTile
                label={t("pages.composer.checkpointPolicy")}
                value={
                  workflowCheckpointPolicy === "lenient"
                    ? t("pages.composer.checkpointOptions.lenient")
                    : workflowCheckpointPolicy === "disabled"
                      ? t("pages.composer.checkpointOptions.disabled")
                      : t("pages.composer.checkpointOptions.strict")
                }
              />
              <AtlasMetricTile
                label={t("pages.composer.expectedOutputs")}
                value={formatNumber(workflowOutputs.fields.length)}
              />
              <AtlasMetricTile
                label={t("pages.composer.governanceConstraints")}
                value={formatNumber(workflowConstraints.fields.length)}
              />
            </div>
            <div className="grid gap-3 lg:grid-cols-3">
              <div className="rounded-[22px] border border-[rgba(23,25,29,0.06)] bg-white/58 p-4">
                <Label
                  htmlFor="workflow-trinity-ref"
                  className="text-sm font-semibold"
                >
                  {t("pages.composer.trinityBundleRef")}
                </Label>
                <Input
                  id="workflow-trinity-ref"
                  {...form.register("trinityRef")}
                  placeholder={t("pages.composer.placeholders.trinity")}
                  className="atlas-input--mono mt-3"
                />
              </div>
              <div className="rounded-[22px] border border-[rgba(23,25,29,0.06)] bg-white/58 p-4">
                <Label
                  htmlFor="workflow-policy-spec-ref"
                  className="text-sm font-semibold"
                >
                  {t("pages.composer.policySpecRef")}
                </Label>
                <Input
                  id="workflow-policy-spec-ref"
                  {...form.register("policySpecRef")}
                  placeholder={t("pages.composer.placeholders.policySpec")}
                  className="atlas-input--mono mt-3"
                />
              </div>
              <div className="rounded-[22px] border border-[rgba(23,25,29,0.06)] bg-white/58 p-4">
                <Label
                  htmlFor="workflow-model-spec-ref"
                  className="text-sm font-semibold"
                >
                  {t("pages.composer.modelSpecRef")}
                </Label>
                <Input
                  id="workflow-model-spec-ref"
                  {...form.register("modelSpecRef")}
                  placeholder={t("pages.composer.placeholders.modelSpec")}
                  className="atlas-input--mono mt-3"
                />
              </div>
            </div>
          </AtlasFormSection>

          <AtlasFormSection
            eyebrow={t("pages.composer.steps.guardrails")}
            glyph="governance-pass"
            title={t("pages.composer.checkpointPolicy")}
            description={t("pages.composer.stepBodies.guardrails")}
          >
            <div className="grid gap-3 md:grid-cols-[minmax(0,240px)_minmax(0,1fr)]">
              <div className="rounded-[22px] border border-[rgba(23,25,29,0.06)] bg-white/58 p-4">
                <Label
                  htmlFor="workflow-checkpoint-policy"
                  className="text-sm font-semibold"
                >
                  {t("pages.composer.checkpointPolicy")}
                </Label>
                <Select
                  id="workflow-checkpoint-policy"
                  {...form.register("checkpointPolicy")}
                  className="mt-3"
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
                </Select>
              </div>
              <div className="rounded-[22px] border border-[rgba(23,25,29,0.06)] bg-white/58 p-4">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-semibold">
                    {t("pages.composer.customParams")}
                  </span>
                  <ArrayActions
                    onAdd={() => workflowParams.append({ key: "", value: "" })}
                    label={t("pages.composer.addParam")}
                  />
                </div>
                <div className="mt-4">
                  <WorkflowParamList
                    fields={
                      workflowParams.fields as Array<
                        { id: string } & ParamFormValue
                      >
                    }
                    register={form.register}
                    onRemove={workflowParams.remove}
                    removeLabel={t("common.remove")}
                    keyPlaceholder={t("pages.composer.paramKey")}
                    valuePlaceholder={t("pages.composer.paramValue")}
                  />
                </div>
              </div>
            </div>
          </AtlasFormSection>

          <ExpectedOutputsEditor
            addLabel={t("pages.composer.addOutput")}
            baseId="workflow-output"
            description={t("pages.composer.stepBodies.evidence")}
            descriptionPlaceholder={t(
              "pages.composer.expectedOutputDescriptionPlaceholder",
            )}
            eyebrow={t("pages.composer.steps.evidence")}
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
            description={t("pages.composer.stepBodies.guardrails")}
            eyebrow={t("pages.composer.steps.guardrails")}
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
            severityLabel={t("pages.composer.severity")}
            scopePlaceholder={t("pages.composer.constraintScopePlaceholder")}
          />

          {launchRunMutation.error ? (
            <ApiErrorAlert error={launchRunMutation.error} />
          ) : null}
          <ComposerActionRow
            help={t("pages.composer.workflowHelp")}
            action={
              <Button
                type="submit"
                data-testid="composer-launch-workflow"
                disabled={
                  launchRunMutation.isPending || !form.formState.isValid
                }
                variant="primary"
              >
                {launchRunMutation.isPending
                  ? t("pages.composer.launchingWorkflow")
                  : t("pages.composer.launchWorkflow")}
              </Button>
            }
          />
        </form>
      </div>

      <AtlasRail>
        <SummaryCards
          constraintCount={workflowConstraints.fields.length}
          expectedOutputsCount={workflowOutputs.fields.length}
          preflightEnabled={preflightEnabled}
        />
        <CapabilityHighlightsSection
          capabilityHighlights={capabilityHighlights}
        />
        <RecentLaunchesSection recentLaunches={recentLaunches} />
      </AtlasRail>
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
      <div className="space-y-5">
        <ComposerSectionHeader
          eyebrow={t("pages.composer.naturalLanguage")}
          title={t("pages.composer.nlHeading")}
          subtitle={t("pages.composer.subtitle")}
          actions={
            <>
              <Badge kind={isDirty ? "warn" : "ok"}>
                {isDirty
                  ? t("pages.composer.unsavedChanges")
                  : t("pages.composer.savedState")}
              </Badge>
              <Button type="button" onClick={resetForm} variant="ghost">
                {t("pages.composer.reset")}
              </Button>
            </>
          }
        />

        <DraftNotice activeDraft={activeDraft} onDiscard={discardDraft} />

        <form className="space-y-5" onSubmit={submit}>
          <AtlasFormSection
            eyebrow={t("pages.composer.steps.workflow")}
            glyph="counterfactual"
            title={t("pages.composer.nlBrief")}
            description={t("pages.composer.stepBodies.workflow")}
            tone="accent"
          >
            <div className="rounded-[22px] border border-[rgba(23,25,29,0.06)] bg-white/58 p-4">
              <Label htmlFor="composer-nl-brief" className="eyebrow">
                {t("pages.composer.nlBrief")}
              </Label>
              <Textarea
                id="composer-nl-brief"
                {...form.register("nlRequest")}
                data-testid="composer-nl-brief"
                rows={5}
                maxLength={10_000}
                placeholder={t("pages.composer.nlBriefPlaceholder")}
                className="mt-3"
              />
              <div className="text-muted mt-2 flex items-center justify-between gap-3 text-xs">
                <FieldError
                  message={form.formState.errors.nlRequest?.message}
                />
                <span>{(nlRequest ?? "").length}/10000</span>
              </div>
            </div>
          </AtlasFormSection>

          <AtlasFormSection
            eyebrow={t("pages.composer.steps.evidence")}
            glyph="evidence"
            title={t("pages.composer.operatorBrief")}
            description={t("pages.composer.stepBodies.evidence")}
          >
            <div className="grid gap-5 lg:grid-cols-2">
              <div className="rounded-[22px] border border-[rgba(23,25,29,0.06)] bg-white/58 p-4">
                <Label htmlFor="nl-operator-brief" className="eyebrow">
                  {t("pages.composer.operatorBrief")}
                </Label>
                <Textarea
                  id="nl-operator-brief"
                  {...form.register("executionIntent")}
                  rows={4}
                  placeholder={t("pages.composer.operatorBriefPlaceholder")}
                  className="mt-3"
                />
              </div>
              <div className="rounded-[22px] border border-[rgba(23,25,29,0.06)] bg-white/58 p-4">
                <Label
                  htmlFor="nl-domain-hint"
                  className="text-sm font-semibold"
                >
                  {t("pages.composer.domainHint")}
                </Label>
                <Select
                  id="nl-domain-hint"
                  {...form.register("domainHint")}
                  className="mt-3"
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
                </Select>
                <Label
                  htmlFor="composer-nl-data-snapshot"
                  className="text-muted mt-4 block text-xs"
                >
                  {t("pages.composer.dataSourceBinding")}
                </Label>
                <Input
                  id="composer-nl-data-snapshot"
                  {...form.register("nlDataSourceRef")}
                  data-testid="composer-nl-data-snapshot"
                  placeholder={t("pages.composer.placeholders.dataSnapshot")}
                  className="atlas-input--mono mt-1"
                />
              </div>
            </div>
          </AtlasFormSection>

          <AtlasFormSection
            eyebrow={t("pages.composer.steps.nl")}
            glyph="transport"
            title={t("pages.composer.orchestration")}
            description={t("pages.composer.stepBodies.nl")}
          >
            <div className="grid gap-3 md:grid-cols-4">
              <div className="rounded-[22px] border border-[rgba(23,25,29,0.06)] bg-white/58 p-4">
                <Label
                  htmlFor="nl-max-iterations"
                  className="text-sm font-semibold"
                >
                  {t("pages.composer.maxIterations")}
                </Label>
                <Input
                  id="nl-max-iterations"
                  type="number"
                  min={1}
                  max={maxIterationsConstraint}
                  {...form.register("maxIterations", { valueAsNumber: true })}
                  className="mt-3"
                />
              </div>
              <div className="rounded-[22px] border border-[rgba(23,25,29,0.06)] bg-white/58 p-4">
                <Label
                  htmlFor="nl-max-parallel-models"
                  className="text-sm font-semibold"
                >
                  {t("pages.composer.maxParallelModels")}
                </Label>
                <Input
                  id="nl-max-parallel-models"
                  type="number"
                  min={1}
                  max={maxParallelConstraint}
                  disabled={!multimodelEnabled}
                  {...form.register("maxParallelModels", {
                    valueAsNumber: true,
                  })}
                  className="mt-3"
                />
              </div>
              <div className="rounded-[22px] border border-[rgba(23,25,29,0.06)] bg-white/58 p-4">
                <Label
                  htmlFor="nl-run-budget"
                  className="text-sm font-semibold"
                >
                  {t("pages.composer.runBudgetUsd")}
                </Label>
                <Input
                  id="nl-run-budget"
                  {...form.register("runBudgetUsd")}
                  type="number"
                  min={0}
                  step="0.01"
                  className="mt-3"
                />
              </div>
              <div className="rounded-[22px] border border-[rgba(23,25,29,0.06)] bg-white/58 p-4">
                <Label
                  htmlFor="nl-per-model-budget"
                  className="text-sm font-semibold"
                >
                  {t("pages.composer.perModelBudgetUsd")}
                </Label>
                <Input
                  id="nl-per-model-budget"
                  {...form.register("perModelBudgetUsd")}
                  type="number"
                  min={0}
                  step="0.01"
                  className="mt-3"
                />
              </div>
            </div>
            <div className="grid gap-3 md:grid-cols-3">
              <AtlasMetricTile
                label={t("pages.composer.expectedOutputs")}
                value={formatNumber(nlOutputs.fields.length)}
              />
              <AtlasMetricTile
                label={t("pages.composer.governanceConstraints")}
                value={formatNumber(nlConstraints.fields.length)}
              />
              <AtlasMetricTile
                label={t("pages.composer.maxParallelModels")}
                value={
                  multimodelEnabled
                    ? formatNumber(form.watch("maxParallelModels") ?? 1)
                    : t("common.disabled")
                }
              />
            </div>
          </AtlasFormSection>

          <ExpectedOutputsEditor
            addLabel={t("pages.composer.addOutput")}
            baseId="nl-output"
            description={t("pages.composer.stepBodies.evidence")}
            descriptionPlaceholder={t(
              "pages.composer.expectedOutputDescriptionPlaceholder",
            )}
            eyebrow={t("pages.composer.steps.evidence")}
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
            description={t("pages.composer.stepBodies.guardrails")}
            eyebrow={t("pages.composer.steps.guardrails")}
            fields={nlConstraints.fields}
            labelFn={label}
            labelText={t("pages.composer.governanceConstraints")}
            onAppend={() => nlConstraints.append(EMPTY_GOVERNANCE_CONSTRAINT)}
            onRemove={removeConstraint}
            register={form.register}
            removeLabel={t("common.remove")}
            rulePlaceholder={t("pages.composer.constraintRulePlaceholder")}
            severityLabel={t("pages.composer.severity")}
            scopePlaceholder={t("pages.composer.constraintScopePlaceholder")}
          />

          {launchNlMutation.error ? (
            <ApiErrorAlert error={launchNlMutation.error} />
          ) : null}
          <ComposerActionRow
            help={t("pages.composer.nlHelp")}
            action={
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
            }
          />
        </form>
      </div>

      <AtlasRail>
        <SummaryCards
          constraintCount={nlConstraints.fields.length}
          expectedOutputsCount={nlOutputs.fields.length}
          preflightEnabled={preflightEnabled}
        />
        <ModelSelectionRail
          addCustomModel={addCustomModel}
          formError={form.formState.errors.selectedLlmModels?.message}
          llmModelInput={llmModelInput}
          llmProfiles={llmProfiles}
          llmProfilesError={llmProfilesError}
          llmProfilesLoading={llmProfilesLoading}
          onModelInputChange={setLlmModelInput}
          selectedLlmModels={selectedLlmModels}
          selectedProfiles={selectedProfiles}
          toggleModel={toggleModel}
        />
        <CapabilityHighlightsSection
          capabilityHighlights={capabilityHighlights}
        />
        <RecentLaunchesSection recentLaunches={recentLaunches} />
      </AtlasRail>
    </section>
  );
}
