import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useSuspenseArtifactContent } from "@/api/hooks/useArtifactContent";
import {
  renderArtifactViewer,
  resolveArtifactPreviewPayload,
} from "@/features/artifacts";
import { buildArtifactHref } from "@/features/artifacts/domain/searchParams";
import { useRunInspector } from "@/features/runs/context/RunInspectorContext";
import { MetricCard } from "@/features/runs/components/MetricCard";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import {
  evidenceArtifactRefKey,
  type EvidenceArtifactRef,
} from "@/shared/lib/domain/evidence";
import { cn, formatBytes } from "@/shared/lib/utils";
import { FeatureAsyncBoundary } from "@/shared/components/FeatureAsyncBoundary";
import { EmptyState, PanelSkeleton } from "@polisyos/atlas-ui";

function ArtifactPreviewContent({
  artifactRef,
}: {
  artifactRef: EvidenceArtifactRef;
}) {
  const { t, label } = useI18n();
  const artifactQuery = useSuspenseArtifactContent(artifactRef, {
    maxBytes: 256 * 1024,
  });
  const selectedArtifact = artifactQuery.data.artifact;
  if (
    selectedArtifact.artifact_id !== artifactRef.artifact_id ||
    (artifactRef.kind != null && selectedArtifact.kind !== artifactRef.kind) ||
    (artifactRef.media_type != null &&
      selectedArtifact.media_type !== artifactRef.media_type) ||
    (artifactRef.manifest_profile_sha256 != null &&
      selectedArtifact.manifest_profile_sha256 !==
        artifactRef.manifest_profile_sha256)
  ) {
    return (
      <p role="alert" data-testid="run-artifact-profile-mismatch">
        {t("pages.runs.artifactProfileMismatch")}
      </p>
    );
  }
  const resolvedPreview = resolveArtifactPreviewPayload(selectedArtifact);

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
      <p
        className="text-muted font-mono text-xs"
        data-testid="run-artifact-profile"
      >
        {t("pages.runs.manifestProfile")}:{" "}
        {artifactRef.manifest_profile_sha256 ??
          t("pages.runs.manifestProfileUnqualified")}
      </p>
      <p
        className="text-muted font-mono text-xs"
        data-testid="run-artifact-resolved-profile"
      >
        {t("pages.artifacts.resolvedManifestProfile")}:{" "}
        {selectedArtifact.manifest_profile_sha256 ??
          t("pages.runs.manifestProfileUnqualified")}
      </p>
      {renderArtifactViewer({
        kind: selectedArtifact.kind,
        preview: resolvedPreview,
      })}
      <div className="flex justify-end">
        <Link
          to={buildArtifactHref(artifactRef.artifact_id, {
            artifactRef,
          })}
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
  const [selectedArtifactKey, setSelectedArtifactKey] = useState<string | null>(
    summary.artifactRefs[0]
      ? evidenceArtifactRefKey(summary.artifactRefs[0])
      : null,
  );
  useEffect(() => {
    const availableArtifactKeys = summary.artifactRefs.map(
      evidenceArtifactRefKey,
    );
    setSelectedArtifactKey((current) =>
      current && availableArtifactKeys.includes(current)
        ? current
        : (availableArtifactKeys[0] ?? null),
    );
  }, [summary.artifactRefs]);

  const selectedArtifactRef =
    summary.artifactRefs.find(
      (ref) => evidenceArtifactRefKey(ref) === selectedArtifactKey,
    ) ?? null;

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
        {summary.artifactRefs.map((ref) => {
          const identityKey = evidenceArtifactRefKey(ref);
          const selected = selectedArtifactKey === identityKey;
          return (
            <button
              key={identityKey}
              type="button"
              data-testid={`artifact-card-${encodeURIComponent(identityKey)}`}
              aria-pressed={selected}
              onClick={() => setSelectedArtifactKey(identityKey)}
              className={cn(
                "w-full rounded-2xl border p-3 text-left transition",
                selected
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
              <p className="text-muted mt-1 truncate font-mono text-[10px]">
                {ref.manifest_profile_sha256 ??
                  t("pages.runs.manifestProfileUnqualified")}
              </p>
            </button>
          );
        })}
      </div>

      <div className="space-y-3">
        {selectedArtifactRef ? (
          <FeatureAsyncBoundary
            feature="runs.artifacts.preview"
            title={t("pages.runs.artifactLoadError")}
            body={t("common.pageErrorBody")}
            loading={<PanelSkeleton rows={5} />}
            resetKeys={[evidenceArtifactRefKey(selectedArtifactRef)]}
          >
            <ArtifactPreviewContent artifactRef={selectedArtifactRef} />
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
