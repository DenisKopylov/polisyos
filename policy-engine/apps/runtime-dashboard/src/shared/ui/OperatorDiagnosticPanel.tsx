import type { components } from "@/api/types";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";
import { Badge } from "@polisyos/atlas-ui";

type ControlOperatorDiagnostic = NonNullable<
  components["schemas"]["ControlJobResponse"]["operator_diagnostic"]
>;
type RunOperatorDiagnostic = NonNullable<
  components["schemas"]["RunDetails"]["operator_diagnostic"]
>;

export type OperatorDiagnosticView =
  | ControlOperatorDiagnostic
  | RunOperatorDiagnostic;

type OperatorDiagnosticPanelProps = {
  className?: string;
  diagnostic: OperatorDiagnosticView;
};

function authorityLabel(value: string | null | undefined) {
  return value === "runtime_authority"
    ? "runtime authority"
    : "projection only";
}

function valueEntries(record: Record<string, string> | undefined) {
  return Object.entries(record ?? {}).filter(([, value]) => Boolean(value));
}

export function OperatorDiagnosticPanel({
  className,
  diagnostic,
}: OperatorDiagnosticPanelProps) {
  const { t } = useI18n();
  const authorityRefs = valueEntries(diagnostic.authority_refs);
  const evidenceRefs = diagnostic.evidence_refs ?? [];
  const labels = diagnostic.projection_labels ?? [];

  return (
    <section
      aria-label={t("operatorDiagnostic.ariaLabel")}
      className={cn(
        "border-l-2 border-[var(--color-status-rejected)] bg-[color-mix(in_srgb,var(--color-status-rejected)_6%,transparent)] px-3 py-2 text-sm",
        className,
      )}
      data-testid="operator-diagnostic-panel"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge kind="fail">{diagnostic.first_blocking_cause}</Badge>
        <Badge kind="neutral">{diagnostic.authoritative_runtime_state}</Badge>
        <Badge kind="neutral">{diagnostic.projection_source}</Badge>
        <Badge kind={diagnostic.blocker_overridable ? "warn" : "neutral"}>
          {diagnostic.blocker_overridable
            ? t("operatorDiagnostic.overridable")
            : t("operatorDiagnostic.notOverridable")}
        </Badge>
      </div>

      {labels.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-2">
          {labels.map((item) => (
            <Badge
              key={`${item.state}:${item.authority}`}
              kind={item.authority === "runtime_authority" ? "fail" : "neutral"}
            >
              {item.label}
            </Badge>
          ))}
          {[
            ...new Set(labels.map((item) => authorityLabel(item.authority))),
          ].map((label) => (
            <Badge key={label} kind="neutral">
              {label}
            </Badge>
          ))}
        </div>
      ) : null}

      <dl className="mt-2 grid gap-1 text-[13px] sm:grid-cols-2">
        <div>
          <dt className="font-semibold text-[var(--slate)]">
            {t("operatorDiagnostic.owner")}
          </dt>
          <dd>{diagnostic.owner}</dd>
        </div>
        <div>
          <dt className="font-semibold text-[var(--slate)]">
            {t("operatorDiagnostic.phase")}
          </dt>
          <dd>{diagnostic.phase}</dd>
        </div>
        {diagnostic.upstream_missing_input ? (
          <div>
            <dt className="font-semibold text-[var(--slate)]">
              {t("operatorDiagnostic.upstreamMissingInput")}
            </dt>
            <dd className="break-words">{diagnostic.upstream_missing_input}</dd>
          </div>
        ) : null}
        <div>
          <dt className="font-semibold text-[var(--slate)]">
            {t("operatorDiagnostic.downstreamImpact")}
          </dt>
          <dd className="break-words">{diagnostic.downstream_impact}</dd>
        </div>
      </dl>

      <p className="mt-2 font-mono text-xs break-all">
        {diagnostic.next_diagnostic_command}
      </p>

      {authorityRefs.length > 0 ? (
        <div className="mt-2 space-y-1 text-xs text-[var(--slate)]">
          <p className="font-semibold">
            {t("operatorDiagnostic.authorityRefs")}
          </p>
          {authorityRefs.map(([key, value]) => (
            <p key={key} className="break-all">
              {key}: {value}
            </p>
          ))}
        </div>
      ) : null}

      {evidenceRefs.length > 0 ? (
        <div className="mt-2 space-y-1 text-xs text-[var(--slate)]">
          <p className="font-semibold">
            {t("operatorDiagnostic.evidenceRefs")}
          </p>
          {evidenceRefs.map((ref) => (
            <p key={ref} className="break-all">
              {ref}
            </p>
          ))}
        </div>
      ) : null}
    </section>
  );
}
