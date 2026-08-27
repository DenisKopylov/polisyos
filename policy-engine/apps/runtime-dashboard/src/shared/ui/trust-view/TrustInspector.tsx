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
          <dd className="min-w-0 truncate">{inspectorSubject.id}</dd>
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
