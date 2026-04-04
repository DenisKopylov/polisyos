import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useSuspenseArtifactContent } from "@/api/hooks/useArtifactContent";
import { renderArtifactViewer } from "@/features/artifacts";
import { useRunInspector } from "@/features/runs/context/RunInspectorContext";
import { MetricCard } from "@/features/runs/components/MetricCard";
import { useI18n } from "@/i18n/LocaleProvider";
import { cn, formatBytes } from "@/lib/utils";
import { FeatureAsyncBoundary } from "@/shared/components/FeatureAsyncBoundary";
import { EmptyState, PanelSkeleton } from "@/shared/ui";

function ArtifactPreviewContent({ artifactId }: { artifactId: string }) {
  const { t, label } = useI18n();
  const artifactQuery = useSuspenseArtifactContent(artifactId, {
    maxBytes: 256 * 1024,
  });
  const selectedArtifact = artifactQuery.data.artifact;

  return (
    <>
      <div className="grid gap-3 md:grid-cols-4">
        <MetricCard
          label={t("pages.runs.decisionKind")}
          value={label(
            "artifactKinds",
            selectedArtifact.kind,
            selectedArtifact.kind,
          )}
        />
        <MetricCard
          label={t("pages.runs.decisionMode")}
          value={selectedArtifact.mode}
        />
        <MetricCard
          label={t("pages.runs.decisionSize")}
          value={formatBytes(selectedArtifact.size_bytes)}
        />
        <MetricCard
          label={t("pages.runs.decisionTruncated")}
          value={selectedArtifact.truncated ? t("common.yes") : t("common.no")}
        />
      </div>
      {renderArtifactViewer({
        kind: selectedArtifact.kind,
        preview: selectedArtifact.preview,
      })}
      <div className="flex justify-end">
        <Link
          to={`/artifacts/${artifactId}`}
          className="text-accent text-xs font-semibold underline"
        >
          {t("common.openArtifact")}
        </Link>
      </div>
    </>
  );
}

export default function ArtifactsTab() {
  const { t, label } = useI18n();
  const summary = useRunInspector();
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(
    summary.artifactRefs[0]?.artifact_id ?? null,
  );

  useEffect(() => {
    const ids = summary.artifactRefs.map((ref) => ref.artifact_id);
    setSelectedArtifactId((current) =>
      current && ids.includes(current) ? current : (ids[0] ?? null),
    );
  }, [summary.artifactRefs]);

  if (summary.artifactRefs.length === 0) {
    return (
      <EmptyState
        title={t("pages.runs.artifactEmptyTitle")}
        body={t("pages.runs.artifactEmptyBody")}
      />
    );
  }

  return (
    <div
      className="grid gap-5 xl:grid-cols-[320px,1fr]"
      data-testid="run-tab-artifacts"
    >
      <div className="space-y-2">
        {summary.artifactRefs.map((ref) => (
          <button
            key={ref.artifact_id}
            type="button"
            data-testid={`artifact-card-${ref.artifact_id}`}
            onClick={() => setSelectedArtifactId(ref.artifact_id)}
            className={cn(
              "w-full rounded-2xl border p-3 text-left transition",
              selectedArtifactId === ref.artifact_id
                ? "border-accent/30 bg-accent/10"
                : "bg-surface/70 border-line hover:bg-surface",
            )}
          >
            <p className="truncate text-sm font-semibold">
              {label(
                "artifactKinds",
                ref.kind,
                ref.kind ?? t("pages.runs.noArtifactKind"),
              )}
            </p>
            <p className="text-muted mt-1 truncate font-mono text-[11px]">
              {ref.artifact_id}
            </p>
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {selectedArtifactId ? (
          <FeatureAsyncBoundary
            feature="runs.artifacts.preview"
            title={t("pages.runs.artifactLoadError")}
            body={t("common.pageErrorBody")}
            loading={<PanelSkeleton rows={5} />}
            resetKeys={[selectedArtifactId]}
          >
            <ArtifactPreviewContent artifactId={selectedArtifactId} />
          </FeatureAsyncBoundary>
        ) : (
          <EmptyState
            title={t("pages.runs.artifactEmptyTitle")}
            body={t("pages.runs.artifactEmptyBody")}
          />
        )}
      </div>
    </div>
  );
}
