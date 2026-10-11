import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { useArtifactContent } from "@/api/hooks/useArtifactContent";
import { useArtifactLineage } from "@/api/hooks/useArtifactLineage";
import { useArtifactManifest } from "@/api/hooks/useArtifactManifest";
import { useArtifactSchema } from "@/api/hooks/useArtifactSchema";
import {
  ARTIFACT_TABS,
  buildArtifactHref,
  type ArtifactTab,
  type ArtifactView,
  parseArtifactReferenceSelection,
  parseArtifactSearchParams,
} from "@/features/artifacts/domain/searchParams";
import { resolveArtifactPreviewPayload } from "@/features/artifacts/domain/typedPreview";
import {
  getArtifactViewerDescriptor,
  renderArtifactViewer,
} from "@/features/artifacts/components/ArtifactViewerRegistry";
import { BureaucraticArtifactView } from "@/features/artifacts/bureaucratic/BureaucraticArtifactView";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import {
  artifactRefMatchesResolvedView,
  evidenceArtifactRefKey,
  sameResolvedArtifactView,
} from "@/shared/lib/domain/evidence";
import { formatBytes, formatDate } from "@/shared/lib/utils";
import { Card, EmptyState } from "@polisyos/atlas-ui";
import { ApiErrorAlert, LineageGraph } from "@/shared/ui";

const PREVIEW_LIMITS = [64 * 1024, 256 * 1024, 1024 * 1024, 2_000_000] as const;

function nextPreviewLimit(current: number): number | null {
  for (const limit of PREVIEW_LIMITS) {
    if (limit > current) {
      return limit;
    }
  }
  return null;
}

export default function ArtifactInspector() {
  const { t, label } = useI18n();
  const { artifactId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [previewLimit, setPreviewLimit] = useState<number>(PREVIEW_LIMITS[0]);
  const referenceSelection = parseArtifactReferenceSelection(
    searchParams,
    artifactId,
  );
  const invalidReferenceSelection = referenceSelection.kind === "invalid";
  const expectedRef = invalidReferenceSelection
    ? undefined
    : referenceSelection.ref;
  const manifestProfileSha256 = expectedRef?.manifest_profile_sha256 ?? null;
  const queryArtifact = invalidReferenceSelection ? undefined : expectedRef;

  const { tab: activeTab, view: activeView } =
    parseArtifactSearchParams(searchParams);

  useEffect(() => {
    setPreviewLimit(PREVIEW_LIMITS[0]);
  }, [
    artifactId,
    expectedRef ? evidenceArtifactRefKey(expectedRef) : null,
    referenceSelection.kind,
  ]);

  const manifestQuery = useArtifactManifest(queryArtifact);
  const contentQuery = useArtifactContent(queryArtifact, {
    enabled: activeTab === "content",
    maxBytes: previewLimit,
  });
  const schemaQuery = useArtifactSchema(queryArtifact, activeTab === "schema");
  const lineageQuery = useArtifactLineage(
    queryArtifact,
    activeTab === "lineage",
  );

  const manifestResponse = manifestQuery.data?.artifact;
  const manifestReferenceMatches = Boolean(
    !invalidReferenceSelection &&
    expectedRef &&
    manifestResponse &&
    artifactRefMatchesResolvedView(expectedRef, manifestResponse),
  );
  const manifest = manifestReferenceMatches ? manifestResponse : undefined;

  const manifestSummary = useMemo(
    () => ({
      kind: manifest?.kind
        ? label("artifactKinds", manifest.kind, manifest.kind)
        : "-",
      created: formatDate(manifest?.created_at),
      producer: manifest?.producer_component ?? "-",
      size: manifest ? formatBytes(manifest.byte_size) : "-",
      schema:
        manifest?.schema_name && manifest?.schema_version
          ? `${manifest.schema_name}@${manifest.schema_version}`
          : "-",
    }),
    [manifest],
  );

  function updateSearch(
    updates: Partial<{ tab: ArtifactTab; view: ArtifactView }>,
  ) {
    const next = new URLSearchParams(searchParams);
    if (updates.tab) {
      next.set("tab", updates.tab);
    }
    if (updates.view === "reading") {
      next.set("view", updates.view);
    } else if (updates.view === "default") {
      next.delete("view");
    }
    setSearchParams(next);
  }

  function selectTab(tab: ArtifactTab) {
    updateSearch({ tab });
  }

  function selectView(view: ArtifactView) {
    updateSearch({ view });
  }

  if (!artifactId) {
    return <Card>{t("pages.artifacts.requiredArtifactId")}</Card>;
  }

  const contentResponse = contentQuery.data?.artifact;
  const contentReferenceMatches = Boolean(
    !invalidReferenceSelection &&
    expectedRef &&
    contentResponse &&
    artifactRefMatchesResolvedView(expectedRef, contentResponse) &&
    manifestResponse &&
    sameResolvedArtifactView(manifestResponse, contentResponse),
  );
  const content = contentReferenceMatches ? contentResponse : undefined;
  const schemaResponse = schemaQuery.data?.schema;
  const schemaReferenceMatches = Boolean(
    !invalidReferenceSelection &&
    expectedRef &&
    schemaResponse &&
    artifactRefMatchesResolvedView(expectedRef, schemaResponse) &&
    manifestResponse &&
    sameResolvedArtifactView(manifestResponse, schemaResponse),
  );
  const schemaView = schemaReferenceMatches ? schemaResponse : undefined;
  const lineageResponse = lineageQuery.data?.lineage;
  const lineageReferenceMatches = Boolean(
    !invalidReferenceSelection &&
    expectedRef &&
    manifestResponse &&
    (lineageResponse?.root_artifact_refs ?? []).some(
      (ref) =>
        artifactRefMatchesResolvedView(expectedRef, ref) &&
        sameResolvedArtifactView(manifestResponse, ref),
    ),
  );
  const lineageView = lineageReferenceMatches ? lineageResponse : undefined;
  const canLoadMore = content
    ? Boolean(content.truncated && nextPreviewLimit(previewLimit) !== null)
    : false;
  const resolvedPreview = resolveArtifactPreviewPayload(content);
  const viewerDescriptor = content
    ? getArtifactViewerDescriptor({
        kind: content.kind,
        preview: resolvedPreview,
      })
    : null;

  return (
    <div className="space-y-4" data-testid="artifact-page">
      <Card>
        <h2 className="mb-2 text-xl font-semibold">
          {t("pages.artifacts.title")}
        </h2>
        <p className="mb-3 font-mono text-xs">{artifactId}</p>
        <p
          className="text-muted mb-3 font-mono text-xs"
          data-testid="artifact-reference-selection"
        >
          {t("pages.artifacts.requestedReference")}:{" "}
          {invalidReferenceSelection
            ? t("pages.artifacts.profileInvalidSelection")
            : expectedRef?.kind || expectedRef?.media_type
              ? evidenceArtifactRefKey(expectedRef)
              : (manifestProfileSha256 ??
                t("pages.artifacts.profileUnqualified"))}
        </p>
        <p
          className="text-muted mb-3 font-mono text-xs"
          data-testid="artifact-resolved-profile"
        >
          {t("pages.artifacts.resolvedManifestProfile")}:{" "}
          {manifestResponse?.manifest_profile_sha256 ??
            t("pages.artifacts.profileUnqualified")}
        </p>

        {invalidReferenceSelection ? (
          <p role="alert" data-testid="artifact-profile-invalid-selection">
            {t("pages.artifacts.profileInvalidSelection")}
          </p>
        ) : null}

        {manifestQuery.data && !manifestReferenceMatches ? (
          <p role="alert" data-testid="artifact-profile-mismatch-manifest">
            {t("pages.artifacts.profileMismatch")}
          </p>
        ) : null}
        {manifestQuery.isLoading ? (
          <p className="text-muted text-sm">
            {t("pages.artifacts.loadingManifest")}
          </p>
        ) : null}
        {manifestQuery.isError ? (
          <ApiErrorAlert
            title={t("pages.artifacts.loadManifestError")}
            error={manifestQuery.error}
          />
        ) : null}

        {manifest ? (
          <dl className="grid grid-cols-1 gap-3 text-sm md:grid-cols-2 lg:grid-cols-5">
            <div>
              <dt className="text-muted">{t("pages.artifacts.fields.kind")}</dt>
              <dd>{manifestSummary.kind}</dd>
            </div>
            <div>
              <dt className="text-muted">
                {t("pages.artifacts.fields.created")}
              </dt>
              <dd>{manifestSummary.created}</dd>
            </div>
            <div>
              <dt className="text-muted">{t("pages.artifacts.fields.size")}</dt>
              <dd>{manifestSummary.size}</dd>
            </div>
            <div>
              <dt className="text-muted">
                {t("pages.artifacts.fields.producer")}
              </dt>
              <dd>{manifestSummary.producer}</dd>
            </div>
            <div>
              <dt className="text-muted">
                {t("pages.artifacts.fields.schema")}
              </dt>
              <dd className="font-mono text-xs">{manifestSummary.schema}</dd>
            </div>
          </dl>
        ) : null}
      </Card>

      <Card>
        <div className="mb-4 flex gap-2">
          {ARTIFACT_TABS.map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => selectTab(tab)}
              className={
                activeTab === tab
                  ? "border-text/20 bg-text rounded-lg border px-3 py-2 text-sm font-semibold text-white"
                  : "border-line bg-panel rounded-lg border px-3 py-2 text-sm font-semibold"
              }
            >
              {t(`pages.artifacts.${tab}`)}
            </button>
          ))}
        </div>

        {activeTab === "content" ? (
          <div className="space-y-3">
            {contentQuery.isLoading ? (
              <p className="text-muted text-sm">
                {t("pages.artifacts.loadingContent")}
              </p>
            ) : null}
            {contentQuery.isError ? (
              <ApiErrorAlert
                title={t("pages.artifacts.loadContentError")}
                error={contentQuery.error}
              />
            ) : null}

            {contentQuery.data && !contentReferenceMatches ? (
              <p role="alert" data-testid="artifact-profile-mismatch-content">
                {t("pages.artifacts.profileMismatch")}
              </p>
            ) : null}

            {!contentQuery.isLoading && !contentQuery.isError && content ? (
              <>
                <div className="grid gap-2 md:grid-cols-5">
                  <div className="border-line rounded-xl border p-2 text-sm">
                    <p className="text-muted text-xs uppercase">
                      {t("pages.artifacts.contentFields.mode")}
                    </p>
                    <p className="font-semibold">{content.mode}</p>
                  </div>
                  <div className="border-line rounded-xl border p-2 text-sm">
                    <p className="text-muted text-xs uppercase">
                      {t("pages.artifacts.contentFields.mediaType")}
                    </p>
                    <p className="font-semibold">{content.media_type}</p>
                  </div>
                  <div className="border-line rounded-xl border p-2 text-sm">
                    <p className="text-muted text-xs uppercase">
                      {t("pages.artifacts.contentFields.artifactSize")}
                    </p>
                    <p className="font-semibold">
                      {formatBytes(content.size_bytes)}
                    </p>
                  </div>
                  <div className="border-line rounded-xl border p-2 text-sm">
                    <p className="text-muted text-xs uppercase">
                      {t("pages.artifacts.contentFields.previewLimit")}
                    </p>
                    <p className="font-semibold">
                      {formatBytes(content.max_bytes)}
                    </p>
                  </div>
                  <div className="border-line rounded-xl border p-2 text-sm">
                    <p className="text-muted text-xs uppercase">
                      {t("pages.artifacts.contentFields.truncated")}
                    </p>
                    <p className="font-semibold">
                      {content.truncated ? t("common.yes") : t("common.no")}
                    </p>
                  </div>
                </div>

                {content.truncated ? (
                  <div className="border-warning/30 bg-warning/5 text-warning flex flex-wrap items-center gap-2 rounded-xl border p-3 text-sm">
                    <span>{t("pages.artifacts.previewTruncated")}</span>
                    {canLoadMore ? (
                      <button
                        type="button"
                        onClick={() => {
                          const nextLimit = nextPreviewLimit(previewLimit);
                          if (nextLimit !== null) {
                            setPreviewLimit(nextLimit);
                          }
                        }}
                        className="border-warning/30 bg-panel text-text rounded-lg border px-2 py-1 text-xs font-semibold"
                      >
                        {t("common.loadLargerPreview")}
                      </button>
                    ) : (
                      <span>{t("common.maxPreviewReached")}</span>
                    )}
                  </div>
                ) : null}

                {viewerDescriptor?.relatedRefs.length ? (
                  <div className="bg-surface/70 border-line rounded-xl border p-3">
                    <p className="text-muted mb-2 text-xs font-semibold uppercase">
                      {t("pages.artifacts.relatedRefs")}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {viewerDescriptor.relatedRefs.map((ref) => (
                        <Link
                          key={`${ref.label}:${ref.identityKey}`}
                          to={buildArtifactHref(ref.artifactId, {
                            artifactRef: ref.artifactRef,
                          })}
                          className="border-line bg-panel rounded-full border px-2 py-1 text-xs font-semibold"
                        >
                          {ref.label}
                        </Link>
                      ))}
                    </div>
                  </div>
                ) : null}

                {renderArtifactViewer({
                  kind: content.kind,
                  preview: resolvedPreview,
                  view: activeView,
                  onViewChange: selectView,
                })}

                {content.kind === "scientist.decision_packet" ||
                content.kind === "decision_packet" ? (
                  <BureaucraticArtifactView
                    artifactRef={expectedRef ?? { artifact_id: artifactId }}
                  />
                ) : null}
              </>
            ) : null}
          </div>
        ) : null}

        {activeTab === "schema" ? (
          <div className="space-y-3">
            {schemaQuery.isLoading ? (
              <p className="text-muted text-sm">
                {t("pages.artifacts.loadingSchema")}
              </p>
            ) : null}
            {schemaQuery.isError ? (
              <ApiErrorAlert
                title={t("pages.artifacts.loadSchemaError")}
                error={schemaQuery.error}
              />
            ) : null}

            {schemaQuery.data && !schemaReferenceMatches ? (
              <p role="alert" data-testid="artifact-profile-mismatch-schema">
                {t("pages.artifacts.profileMismatch")}
              </p>
            ) : null}

            {!schemaQuery.isLoading && !schemaQuery.isError && schemaView ? (
              <>
                <dl className="grid grid-cols-1 gap-3 text-sm md:grid-cols-2">
                  <div>
                    <dt className="text-muted">
                      {t("pages.artifacts.schemaFields.name")}
                    </dt>
                    <dd>{schemaView.schema_name ?? "-"}</dd>
                  </div>
                  <div>
                    <dt className="text-muted">
                      {t("pages.artifacts.schemaFields.version")}
                    </dt>
                    <dd>{schemaView.schema_version ?? "-"}</dd>
                  </div>
                </dl>

                {(schemaView.top_level_keys ?? []).length ? (
                  <div className="border-line rounded-xl border p-3">
                    <p className="text-muted mb-2 text-xs font-semibold uppercase">
                      {t("pages.artifacts.topLevelKeys")}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {(schemaView.top_level_keys ?? []).map((key) => (
                        <span
                          key={key}
                          className="border-line bg-panel rounded-lg border px-2 py-1 font-mono text-xs"
                        >
                          {key}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : (
                  <EmptyState
                    title={t("pages.artifacts.noSchemaKeysTitle")}
                    body={t("pages.artifacts.noSchemaKeysBody")}
                  />
                )}
              </>
            ) : null}
          </div>
        ) : null}

        {activeTab === "lineage" ? (
          <div className="space-y-3">
            {lineageQuery.isLoading ? (
              <p className="text-muted text-sm">
                {t("pages.artifacts.loadingLineage")}
              </p>
            ) : null}
            {lineageQuery.isError ? (
              <ApiErrorAlert
                title={t("pages.artifacts.loadLineageError")}
                error={lineageQuery.error}
              />
            ) : null}

            {lineageQuery.data && !lineageReferenceMatches ? (
              <p role="alert" data-testid="artifact-profile-mismatch-lineage">
                {t("pages.artifacts.profileMismatch")}
              </p>
            ) : null}

            {!lineageQuery.isLoading && !lineageQuery.isError && lineageView ? (
              <>
                <div className="grid gap-2 md:grid-cols-4">
                  <div className="border-line rounded-xl border p-2 text-sm">
                    <p className="text-muted text-xs uppercase">
                      {t("pages.artifacts.lineageFields.nodes")}
                    </p>
                    <p className="font-semibold">{lineageView.total_nodes}</p>
                  </div>
                  <div className="border-line rounded-xl border p-2 text-sm">
                    <p className="text-muted text-xs uppercase">
                      {t("pages.artifacts.lineageFields.edges")}
                    </p>
                    <p className="font-semibold">{lineageView.total_edges}</p>
                  </div>
                  <div className="border-line rounded-xl border p-2 text-sm">
                    <p className="text-muted text-xs uppercase">
                      {t("pages.artifacts.lineageFields.complete")}
                    </p>
                    <p className="font-semibold">
                      {lineageView.is_complete
                        ? t("common.yes")
                        : t("common.no")}
                    </p>
                  </div>
                  <div className="border-line rounded-xl border p-2 text-sm">
                    <p className="text-muted text-xs uppercase">
                      {t("pages.artifacts.lineageFields.size")}
                    </p>
                    <p className="font-semibold">
                      {formatBytes(lineageView.total_size_bytes)}
                    </p>
                  </div>
                </div>

                <LineageGraph
                  nodes={lineageView.nodes}
                  edges={lineageView.edges}
                  rootArtifactIds={lineageView.root_artifact_ids}
                  rootArtifactRefs={lineageView.root_artifact_refs}
                />

                {lineageView.missing_artifact_ids.length > 0 ? (
                  <p className="text-warning text-sm">
                    {t("pages.artifacts.missingArtifacts", {
                      artifacts: lineageView.missing_artifact_ids.join(", "),
                    })}
                  </p>
                ) : null}

                {lineageView.corrupted_artifact_ids.length > 0 ? (
                  <p className="text-danger text-sm">
                    {t("pages.artifacts.corruptedArtifacts", {
                      artifacts: lineageView.corrupted_artifact_ids.join(", "),
                    })}
                  </p>
                ) : null}
              </>
            ) : null}
          </div>
        ) : null}
      </Card>
    </div>
  );
}
