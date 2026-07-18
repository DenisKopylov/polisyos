import { ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";

import type { TemporalScope } from "@/app/providers/temporal-scope";
import { toApiTemporalParams } from "@/app/providers/temporal-scope";
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
  QuantityValue,
} from "./quantity.types";

type ProvenanceDeepDiveDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  quantity: QuantityValue;
  lineage?: LineageGraphView | null;
  temporalScope?: TemporalScope | null;
};

export function ProvenanceDeepDiveDialog({
  open,
  onOpenChange,
  quantity,
  lineage,
  temporalScope,
}: ProvenanceDeepDiveDialogProps) {
  const { t } = useI18n();
  const graph = lineage ?? lineageFromQuantity(quantity);
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
  temporalScope: TemporalScope | null | undefined,
) {
  if (!href) {
    return "";
  }
  const params = toApiTemporalParams(temporalScope);
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value) {
      query.set(key, value);
    }
  });
  const suffix = query.toString();
  if (!suffix) {
    return href;
  }
  return `${href}${href.includes("?") ? "&" : "?"}${suffix}`;
}
