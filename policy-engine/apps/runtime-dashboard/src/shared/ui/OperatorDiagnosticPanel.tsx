import type {
  OperatorDiagnostic,
  RunOperatorDiagnostic,
} from "@polisyos/runtime-api-client";
import { useId } from "react";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";
import {
  AuthorityBadge,
  Badge,
  createOpaqueAuthorityPresentation,
  createOperatorBlockingCausePresentation,
  createOperatorProjectionPresentation,
  EvidenceLink,
} from "@polisyos/atlas-ui";

export type OperatorDiagnosticView = OperatorDiagnostic | RunOperatorDiagnostic;

type OperatorDiagnosticPanelProps = {
  className?: string;
  diagnostic: OperatorDiagnosticView;
};

function valueEntries(record: Record<string, string> | undefined) {
  return Object.entries(record ?? {}).filter(([, value]) => Boolean(value));
}

function referenceHref(reference: string) {
  return reference.startsWith("https://") ||
    reference.startsWith("http://") ||
    reference.startsWith("/")
    ? reference
    : undefined;
}

export function OperatorDiagnosticPanel({
  className,
  diagnostic,
}: OperatorDiagnosticPanelProps) {
  const { t } = useI18n();
  const authorityRefs = valueEntries(diagnostic.authority_refs);
  const evidenceRefs = diagnostic.evidence_refs ?? [];
  const labels = diagnostic.projection_labels ?? [];
  const instanceId = useId();
  const authorityRefsId = `operator-authority-refs-${instanceId}`;
  const evidenceRefsId = `operator-evidence-refs-${instanceId}`;

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
        <h3>
          <AuthorityBadge
            presentation={createOperatorBlockingCausePresentation(diagnostic)}
          />
        </h3>
        <AuthorityBadge
          presentation={createOpaqueAuthorityPresentation(
            diagnostic.authoritative_runtime_state,
          )}
        />
        <Badge
          data-projection-source={diagnostic.projection_source}
          kind="neutral"
        >
          {diagnostic.projection_source}
        </Badge>
        <Badge kind={diagnostic.blocker_overridable ? "warn" : "neutral"}>
          {diagnostic.blocker_overridable
            ? t("operatorDiagnostic.overridable")
            : t("operatorDiagnostic.notOverridable")}
        </Badge>
      </div>

      {labels.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-2">
          {labels.map((item) => (
            <AuthorityBadge
              key={`${item.state}:${item.authority}`}
              presentation={createOperatorProjectionPresentation(
                diagnostic,
                item,
              )}
            />
          ))}
          {[...new Set(labels.map((item) => item.authority))].map(
            (authority) => (
              <Badge
                data-projection-authority={authority}
                key={authority}
                kind="neutral"
              >
                {authority.replaceAll("_", " ")}
              </Badge>
            ),
          )}
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

      <code className="mt-2 block font-mono text-xs break-all">
        {diagnostic.next_diagnostic_command}
      </code>

      {authorityRefs.length > 0 ? (
        <div className="mt-2 space-y-1 text-xs text-[var(--slate)]">
          <p className="font-semibold" id={authorityRefsId}>
            {t("operatorDiagnostic.authorityRefs")}
          </p>
          <ul aria-labelledby={authorityRefsId} className="space-y-1">
            {authorityRefs.map(([key, value]) => (
              <li key={key}>
                <EvidenceLink
                  evidenceRef={value}
                  href={referenceHref(value)}
                  label={`${key}:`}
                />
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {evidenceRefs.length > 0 ? (
        <div className="mt-2 space-y-1 text-xs text-[var(--slate)]">
          <p className="font-semibold" id={evidenceRefsId}>
            {t("operatorDiagnostic.evidenceRefs")}
          </p>
          <ul aria-labelledby={evidenceRefsId} className="space-y-1">
            {evidenceRefs.map((ref) => (
              <li key={ref}>
                <EvidenceLink evidenceRef={ref} href={referenceHref(ref)} />
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
