import { useEffect } from "react";
import { Copy, ExternalLink, X } from "lucide-react";

import { useI18n } from "@/shared/i18n/LocaleProvider";

import { DisputeBadge } from "./DisputeBadge";
import { HashChip } from "./HashChip";
import { TemporalScopeChip } from "./TemporalScopeChip";
import { issueTrustPresentation } from "./trust-glyphs";
import { useMaybeTrustView } from "./TrustViewBridge";
import { VerificationStatus } from "./VerificationStatus";

export function TrustInspector() {
  const trustView = useMaybeTrustView();
  const { t } = useI18n();
  const closeInspector = trustView?.closeInspector;
  const inspectorSubject = trustView?.inspectorSubject ?? null;

  useEffect(() => {
    if (!inspectorSubject) {
      return;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeInspector?.();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [closeInspector, inspectorSubject]);

  if (!inspectorSubject) {
    return null;
  }

  const metadata = inspectorSubject.trustMetadata ?? null;
  const profileContext = inspectorSubject.selectedProfileContext ?? null;
  const presentation = issueTrustPresentation(metadata);
  const hash = metadata?.hash ?? inspectorSubject.hash;
  const lineageId =
    inspectorSubject.kind === "quantity" || inspectorSubject.kind === "lineage"
      ? inspectorSubject.id
      : null;
  const canOpenLineage = Boolean(lineageId);
  const deepDiveHref = lineageId
    ? `/api/v1/lineage/${encodeURIComponent(lineageId)}`
    : null;
  const exportHref = lineageId
    ? `/api/v1/lineage/${encodeURIComponent(lineageId)}/export/prov`
    : null;

  return (
    <aside
      className="trust-inspector"
      role="dialog"
      aria-label={t("shared.ui.trustView.inspectorTitle")}
    >
      <div className="trust-inspector-header">
        <div className="min-w-0">
          <p className="text-muted-foreground text-xs font-semibold">
            {t("shared.ui.trustView.label")}
          </p>
          <h2 className="truncate text-base font-semibold">
            {inspectorSubject.label ?? inspectorSubject.id}
          </h2>
        </div>
        <button
          type="button"
          className="trust-inspector-close"
          aria-label={t("common.close")}
          onClick={() => closeInspector?.()}
        >
          <X className="size-4" aria-hidden="true" />
        </button>
      </div>

      <div className="space-y-4 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <VerificationStatus presentation={presentation} />
          <DisputeBadge presentation={presentation} />
        </div>

        {hash ? (
          <HashChip
            hash={hash}
            interactive={false}
            subjectId={inspectorSubject.id}
            subjectKind={inspectorSubject.kind}
            trustMetadata={metadata}
          />
        ) : null}

        <dl className="grid grid-cols-[8rem_minmax(0,1fr)] gap-x-3 gap-y-2 text-sm">
          <dt className="text-muted-foreground">
            {t("shared.ui.trustView.subject")}
          </dt>
          <dd
            className="min-w-0 truncate"
            data-testid="trust-inspector-subject-id"
          >
            {inspectorSubject.id}
          </dd>
          <dt className="text-muted-foreground">
            {t("shared.ui.trustView.kind")}
          </dt>
          <dd>{t(`shared.ui.trustView.kindValue.${inspectorSubject.kind}`)}</dd>
          <dt className="text-muted-foreground">
            {t("shared.ui.trustView.verifiedBy")}
          </dt>
          <dd className="min-w-0 truncate">
            {metadata?.verified_by ?? t("common.unknown")}
          </dd>
          <dt className="text-muted-foreground">
            {t("shared.ui.trustView.verifiedAt")}
          </dt>
          <dd className="min-w-0 truncate">
            {metadata?.verified_at ?? t("common.unknown")}
          </dd>
          <dt className="text-muted-foreground">
            {t("shared.ui.trustView.method")}
          </dt>
          <dd className="min-w-0 truncate">
            {metadata?.verification_method ?? t("common.unknown")}
          </dd>
          <dt className="text-muted-foreground">
            {t("shared.ui.trustView.temporal")}
          </dt>
          <dd>
            <TemporalScopeChip
              scope={
                metadata?.temporal_scope ??
                inspectorSubject.temporalScope ??
                null
              }
            />
          </dd>
        </dl>

        {!profileContext ? (
          <p
            className="text-muted-foreground text-xs"
            data-testid="trust-inspector-generic-binding-notice"
          >
            {t("shared.ui.trustView.genericBindingNotice")}
          </p>
        ) : null}

        {profileContext ? (
          <section
            className="space-y-2"
            data-testid="trust-inspector-profile-context"
          >
            <h3 className="text-sm font-semibold">
              {t("shared.ui.trustView.selectedProfile")}
            </h3>
            <dl className="grid grid-cols-[8rem_minmax(0,1fr)] gap-x-3 gap-y-2 text-sm">
              <dt className="text-muted-foreground">
                {t("shared.ui.trustView.profileBindingStatus")}
              </dt>
              <dd data-testid="trust-inspector-profile-binding-status">
                {profileContext.status}
              </dd>
              <dt className="text-muted-foreground">
                {t("shared.ui.trustView.profileLineage")}
              </dt>
              <dd data-testid="trust-inspector-profile-lineage">
                {profileContext.lineageId}
              </dd>
              <dt className="text-muted-foreground">
                {t("shared.ui.trustView.selectedArtifact")}
              </dt>
              <dd
                className="min-w-0 break-all"
                data-testid="trust-inspector-selected-artifact-ref"
              >
                {JSON.stringify(profileContext.selectedArtifactRef)}
              </dd>
              <dt className="text-muted-foreground">
                {t("shared.ui.trustView.profileOrigin")}
              </dt>
              <dd data-testid="trust-inspector-profile-origin">
                {profileContext.origin}
              </dd>
              <dt className="text-muted-foreground">
                {t("shared.ui.trustView.sourceRun")}
              </dt>
              <dd data-testid="trust-inspector-source-run">
                {profileContext.sourceRunId}
              </dd>
              <dt className="text-muted-foreground">
                {t("shared.ui.trustView.temporal")}
              </dt>
              <dd
                className="min-w-0 break-all"
                data-testid="trust-inspector-profile-time"
              >
                {formatTemporalScope(profileContext.temporalScope)}
              </dd>
            </dl>
            <p
              className="text-muted-foreground text-xs"
              data-testid="trust-inspector-follow-on-generic"
            >
              {t("shared.ui.trustView.profileBindingFollowOnGeneric")}
            </p>
          </section>
        ) : null}

        {inspectorSubject.summary ? (
          <p className="border-border bg-muted/30 rounded-md border p-3 text-sm">
            {inspectorSubject.summary}
          </p>
        ) : null}

        <div className="border-border flex flex-wrap gap-2 border-t pt-3">
          <button
            type="button"
            className="trust-inspector-action"
            onClick={() => copyAuditLink(inspectorSubject.id)}
          >
            {t("shared.ui.trustView.copyAuditLink")}
            <Copy className="size-3.5" aria-hidden="true" />
          </button>
          <button
            type="button"
            className="trust-inspector-action"
            disabled={!canOpenLineage}
            title={
              canOpenLineage
                ? undefined
                : t("shared.ui.trustView.lineageActionUnavailable")
            }
            onClick={() => {
              if (deepDiveHref) {
                window.open(deepDiveHref, "_blank", "noopener,noreferrer");
              }
            }}
          >
            {t("shared.ui.trustView.openDeepDive")}
            <ExternalLink className="size-3.5" aria-hidden="true" />
          </button>
          <button
            type="button"
            className="trust-inspector-action"
            disabled={!canOpenLineage}
            title={
              canOpenLineage
                ? undefined
                : t("shared.ui.trustView.lineageActionUnavailable")
            }
            onClick={() => {
              if (exportHref) {
                window.open(exportHref, "_blank", "noopener,noreferrer");
              }
            }}
          >
            {t("shared.ui.trustView.exportAudit")}
          </button>
        </div>
      </div>
    </aside>
  );
}

function copyAuditLink(subjectId: string) {
  const url = new URL(window.location.href);
  url.searchParams.set("trust", "expanded");
  url.searchParams.set("trust_subject", subjectId);
  void navigator.clipboard?.writeText(url.toString());
}

function formatTemporalScope(value: unknown): string {
  if (value === null) return "null";
  if (value === undefined) return "unknown";
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return "unknown";
  }
  const scope = value as Record<string, unknown>;
  return JSON.stringify({
    valid_at: typeof scope.valid_at === "string" ? scope.valid_at : null,
    tx_at: typeof scope.tx_at === "string" ? scope.tx_at : null,
    branch: typeof scope.branch === "string" ? scope.branch : null,
    snapshot_id:
      typeof scope.snapshot_id === "string" ? scope.snapshot_id : null,
    scenario_id:
      typeof scope.scenario_id === "string" ? scope.scenario_id : null,
  });
}
