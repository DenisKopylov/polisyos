import { ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@polisyos/atlas-ui";

import type {
  LineageGraphNode,
  LineageGraphView,
  ProfileBindingContext,
  QuantityValue,
  TemporalRef,
} from "./quantity.types";

type ProvenanceDeepDiveDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  quantity: QuantityValue;
  lineage?: LineageGraphView | null;
  temporalScope?: TemporalRef | null;
  profileBindingContext?: ProfileBindingContext | null;
};

export function ProvenanceDeepDiveDialog({
  open,
  onOpenChange,
  quantity,
  lineage,
  temporalScope,
  profileBindingContext,
}: ProvenanceDeepDiveDialogProps) {
  const { t } = useI18n();
  const graph = lineage ?? lineageFromQuantity(quantity);
  const boundProfileContext =
    profileBindingContext !== undefined
      ? profileBindingContext
      : (quantity.profile_binding_context ?? null);
  const rawSources = graph.nodes?.filter(isRawSourceNode) ?? [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-h-[86vh] max-w-4xl overflow-y-auto"
        closeLabel={t("common.close")}
      >
        <DialogHeader>
          <DialogTitle>{t("shared.ui.quantity.deepDive.title")}</DialogTitle>
          <DialogDescription>
            {t("shared.ui.quantity.deepDive.description", {
              metric: quantity.metric_id ?? quantity.label ?? graph.id,
            })}
          </DialogDescription>
        </DialogHeader>

        <section className="grid gap-3 md:grid-cols-[minmax(0,1fr)_220px]">
          <div className="border-border rounded-md border">
            <div className="border-border bg-muted/30 grid grid-cols-[minmax(0,1fr)_120px_120px] gap-2 border-b px-3 py-2 text-xs font-semibold">
              <span>{t("shared.ui.quantity.deepDive.node")}</span>
              <span>{t("shared.ui.quantity.deepDive.kind")}</span>
              <span>{t("shared.ui.quantity.deepDive.timestamp")}</span>
            </div>
            <div className="divide-border divide-y">
              {(graph.nodes ?? []).map((node) => (
                <div
                  key={node.id}
                  className="grid grid-cols-[minmax(0,1fr)_120px_120px] gap-2 px-3 py-2 text-xs"
                >
                  <span className="min-w-0 truncate font-medium">
                    {node.label}
                  </span>
                  <span className="text-muted truncate">{node.kind}</span>
                  <span className="text-muted truncate">
                    {node.timestamp
                      ? new Date(node.timestamp).toLocaleString()
                      : t("common.unknown")}
                  </span>
                </div>
              ))}
              {(graph.nodes ?? []).length ===
              /* policyos-quantity: layout */ 0 ? (
                <p className="text-muted p-3 text-sm">
                  {t("shared.ui.quantity.deepDive.emptyGraph")}
                </p>
              ) : null}
            </div>
          </div>

          <aside className="space-y-3">
            <InfoBlock
              title={t("shared.ui.quantity.deepDive.verification")}
              value={graph.status}
            />
            <InfoBlock
              title={t("shared.ui.quantity.deepDive.freshness")}
              value={graph.freshness}
            />
            <InfoBlock
              title={t("shared.ui.quantity.deepDive.hash")}
              value={graph.hash ?? t("common.unavailable")}
            />
          </aside>
        </section>

        {boundProfileContext ? (
          <section
            className="space-y-2"
            data-testid="provenance-profile-context"
          >
            <h3 className="text-sm font-semibold">
              {t("shared.ui.trustView.selectedProfile")}
            </h3>
            <dl className="grid grid-cols-[8rem_minmax(0,1fr)] gap-x-3 gap-y-2 text-xs">
              <dt className="text-muted-foreground">
                {t("shared.ui.trustView.profileBindingStatus")}
              </dt>
              <dd data-testid="provenance-profile-binding-status">
                {boundProfileContext.status}
              </dd>
              <dt className="text-muted-foreground">
                {t("shared.ui.trustView.profileLineage")}
              </dt>
              <dd data-testid="provenance-profile-lineage">
                {boundProfileContext.lineageId}
              </dd>
              <dt className="text-muted-foreground">
                {t("shared.ui.trustView.selectedArtifact")}
              </dt>
              <dd
                className="min-w-0 break-all"
                data-testid="provenance-profile-selected-artifact-ref"
              >
                {JSON.stringify(boundProfileContext.selectedArtifactRef)}
              </dd>
              <dt className="text-muted-foreground">
                {t("shared.ui.trustView.profileOrigin")}
              </dt>
              <dd data-testid="provenance-profile-origin">
                {boundProfileContext.origin}
              </dd>
              <dt className="text-muted-foreground">
                {t("shared.ui.trustView.sourceRun")}
              </dt>
              <dd data-testid="provenance-profile-source-run">
                {boundProfileContext.sourceRunId}
              </dd>
              <dt className="text-muted-foreground">
                {t("shared.ui.trustView.temporal")}
              </dt>
              <dd
                className="min-w-0 break-all"
                data-testid="provenance-profile-time"
              >
                {formatTemporalScope(boundProfileContext.temporalScope)}
              </dd>
            </dl>
          </section>
        ) : null}

        <section>
          <h3 className="text-sm font-semibold">
            {t("shared.ui.quantity.deepDive.rawSources")}
          </h3>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            {rawSources.map((node) => (
              <RawSourceLink key={node.id} node={node} />
            ))}
            {rawSources.length === /* policyos-quantity: layout */ 0 ? (
              <p className="text-muted text-sm">
                {t("shared.ui.quantity.deepDive.noRawSources")}
              </p>
            ) : null}
          </div>
        </section>

        <section>
          <h3 className="text-sm font-semibold">
            {t("shared.ui.quantity.deepDive.exports")}
          </h3>
          {boundProfileContext ? (
            <p
              className="text-muted mt-1 text-xs"
              data-testid="provenance-profile-export-generic"
            >
              {t("shared.ui.trustView.profileBindingExportGeneric")}
            </p>
          ) : null}
          <div className="mt-2 flex flex-wrap gap-2">
            <ExportLink
              href={withTemporalQuery(graph.exports.openlineage, temporalScope)}
              label={t("shared.ui.quantity.deepDive.openlineage")}
            />
            <ExportLink
              href={withTemporalQuery(graph.exports.prov, temporalScope)}
              label={t("shared.ui.quantity.deepDive.prov")}
            />
          </div>
        </section>
      </DialogContent>
    </Dialog>
  );
}

function InfoBlock({ title, value }: { title: string; value: string }) {
  return (
    <div className="border-border rounded-md border p-3">
      <div className="text-muted text-xs font-semibold">{title}</div>
      <div className="mt-1 text-sm font-medium break-words">{value}</div>
    </div>
  );
}

function RawSourceLink({ node }: { node: LineageGraphNode }) {
  const artifactId = artifactIdFromNode(node);
  const content = (
    <>
      <span className="min-w-0 truncate">{node.label}</span>
      <ExternalLink className="size-3.5 shrink-0" aria-hidden="true" />
    </>
  );
  const className =
    "border-border hover:bg-muted/40 focus:ring-ring flex min-w-0 items-center gap-2 rounded-md border px-3 py-2 text-sm focus:ring-2 focus:outline-none";

  if (artifactId) {
    return (
      <Link className={className} to={`/artifacts/${artifactId}`}>
        {content}
      </Link>
    );
  }
  return (
    <a className={className} href={`#${node.id}`}>
      {content}
    </a>
  );
}

function ExportLink({ href, label }: { href: string; label: string }) {
  return (
    <a
      className={cn(
        "border-border hover:bg-muted/40 focus:ring-ring inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium focus:ring-2 focus:outline-none",
        !href && "pointer-events-none opacity-50",
      )}
      href={href || "#"}
    >
      {label}
      <ExternalLink className="size-3.5" aria-hidden="true" />
    </a>
  );
}

function lineageFromQuantity(quantity: QuantityValue): LineageGraphView {
  return {
    id: quantity.lineage.id,
    status: quantity.lineage.status,
    freshness: quantity.lineage.freshness,
    compact_summary: quantity.lineage.compact_summary ?? [],
    nodes: [],
    edges: [],
    exports: {
      openlineage: "",
      prov: "",
    },
    metadata: quantity.lineage.summary ?? {},
  };
}

function isRawSourceNode(node: LineageGraphNode) {
  const kind = node.kind.toLowerCase();
  return (
    kind.includes("source") ||
    kind.includes("dataset") ||
    kind.includes("artifact")
  );
}

function artifactIdFromNode(node: LineageGraphNode) {
  const metadataArtifactId = node.metadata?.artifact_id;
  if (typeof metadataArtifactId === "string") {
    return metadataArtifactId;
  }
  if (node.id.startsWith("artifact:")) {
    return node.id.slice("artifact:".length);
  }
  if (node.id.startsWith("sha256:")) {
    return node.id;
  }
  return null;
}

function withTemporalQuery(
  href: string,
  temporalScope: TemporalRef | null | undefined,
) {
  if (!href) {
    return "";
  }
  const query = new URLSearchParams();
  Object.entries(temporalScope ?? {}).forEach(([key, value]) => {
    if (!value) {
      return;
    }
    if (key === "valid_at" || key === "tx_at") {
      const instant = new Date(value);
      if (!Number.isNaN(instant.getTime())) {
        query.set(key, instant.toISOString());
      }
      return;
    }
    query.set(key, value);
  });
  const suffix = query.toString();
  if (!suffix) {
    return href;
  }
  return `${href}${href.includes("?") ? "&" : "?"}${suffix}`;
}

function formatTemporalScope(value: TemporalRef | null): string {
  if (value === null) return "null";
  return JSON.stringify({
    valid_at: value.valid_at ?? null,
    tx_at: value.tx_at ?? null,
    branch: value.branch ?? null,
    snapshot_id: value.snapshot_id ?? null,
    scenario_id: value.scenario_id ?? null,
  });
}
