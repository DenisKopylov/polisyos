import { useState } from "react";
import { Link } from "react-router-dom";

import { useSourceProfiles, type SourceProfileInfo } from "../api/hooks/useSourceProfiles";
import { useIngestData, type IngestRequest } from "../api/hooks/useIngestData";
import ApiErrorAlert from "../components/shared/ApiErrorAlert";
import { Card } from "../components/ui/card";
import { cn } from "../lib/utils";

const FAMILY_ALL = "__all__";

type IngestFormState = {
  datasetId: string;
  connectorId: string;
  countryFilter: string;
  dateStart: string;
  dateEnd: string;
  cachePolicy: string;
};

const initialForm: IngestFormState = {
  datasetId: "",
  connectorId: "",
  countryFilter: "",
  dateStart: "",
  dateEnd: "",
  cachePolicy: "default",
};

function availabilityBadge(profile: SourceProfileInfo) {
  if (profile.connector_available) {
    return (
      <span className="rounded-full bg-green-500/15 px-2 py-0.5 text-[10px] font-medium text-green-600">
        Available
      </span>
    );
  }
  return (
    <span className="rounded-full bg-gray-400/15 px-2 py-0.5 text-[10px] font-medium text-gray-500">
      Coming soon
    </span>
  );
}

export default function SourcesManagement() {
  const profilesQuery = useSourceProfiles();
  const ingestMutation = useIngestData();

  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);
  const [familyFilter, setFamilyFilter] = useState(FAMILY_ALL);
  const [form, setForm] = useState<IngestFormState>(initialForm);
  const [ingestResult, setIngestResult] = useState<{
    message: string;
    snapshotRef: string | null;
    evidenceRef: string | null;
    warnings: string[];
  } | null>(null);

  const profiles = profilesQuery.data?.profiles ?? [];

  // Derive unique families
  const families = Array.from(new Set(profiles.map((p) => p.connector_family))).sort();

  // Filter profiles by family
  const filteredProfiles =
    familyFilter === FAMILY_ALL
      ? profiles
      : profiles.filter((p) => p.connector_family === familyFilter);

  const selectedProfile = profiles.find((p) => p.profile_id === selectedProfileId) ?? null;

  function handleSelectProfile(profile: SourceProfileInfo) {
    if (!profile.connector_available) return;
    setSelectedProfileId(profile.profile_id);
    setForm({
      ...initialForm,
      connectorId: profile.connector_family,
    });
    setIngestResult(null);
  }

  function handleIngest() {
    if (!selectedProfile || !form.datasetId.trim()) return;

    const filters: Record<string, string[]> = {};
    if (form.countryFilter.trim()) {
      filters["country"] = form.countryFilter
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
    }

    // Build connector_id: use connector_family + known short_id pattern
    const connectorId = form.connectorId.trim() || selectedProfile.connector_family;

    const body: IngestRequest = {
      datasets: [
        {
          connector_id: connectorId,
          dataset_id: form.datasetId.trim(),
          filters,
          date_start: form.dateStart || null,
          date_end: form.dateEnd || null,
        },
      ],
      source: "sources-page",
      license_name: "open",
      cache_policy: form.cachePolicy,
      connection_profile: selectedProfile.profile_id,
      execution_mode: "batch_full",
      produce_data_snapshot: true,
    };

    ingestMutation.mutate(body, {
      onSuccess: (data) => {
        setIngestResult({
          message: data.message ?? "Done",
          snapshotRef: data.data_snapshot_ref ?? null,
          evidenceRef: data.evidence_bundle_ref ?? null,
          warnings: data.warnings ?? [],
        });
      },
    });
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Data Sources</h2>
        <p className="text-sm text-muted">
          Browse available source profiles, select a source, and fetch data into the local store.
        </p>
      </div>

      {/* Family filter tabs */}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setFamilyFilter(FAMILY_ALL)}
          className={cn(
            "rounded-lg border px-3 py-1.5 text-xs font-medium transition",
            familyFilter === FAMILY_ALL
              ? "border-accent bg-accent/10 text-accent"
              : "border-line text-muted hover:border-accent/50",
          )}
        >
          All ({profiles.length})
        </button>
        {families.map((fam) => {
          const count = profiles.filter((p) => p.connector_family === fam).length;
          return (
            <button
              key={fam}
              type="button"
              onClick={() => setFamilyFilter(fam)}
              className={cn(
                "rounded-lg border px-3 py-1.5 text-xs font-medium transition",
                familyFilter === fam
                  ? "border-accent bg-accent/10 text-accent"
                  : "border-line text-muted hover:border-accent/50",
              )}
            >
              {fam} ({count})
            </button>
          );
        })}
      </div>

      {/* Profiles grid */}
      <Card>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted">
          Source Profiles
        </h3>
        {profilesQuery.isLoading && <p className="text-sm text-muted">Loading profiles...</p>}
        {profilesQuery.error && <ApiErrorAlert error={profilesQuery.error} />}
        {filteredProfiles.length === 0 && !profilesQuery.isLoading && (
          <p className="text-sm text-muted">No profiles match the current filter.</p>
        )}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {filteredProfiles.map((profile) => (
            <button
              key={profile.profile_id}
              type="button"
              disabled={!profile.connector_available}
              onClick={() => handleSelectProfile(profile)}
              className={cn(
                "rounded-xl border p-3 text-left transition",
                selectedProfileId === profile.profile_id
                  ? "border-accent bg-accent/5"
                  : "border-line bg-surface hover:border-accent/50",
                !profile.connector_available && "cursor-not-allowed opacity-60",
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-sm">{profile.display_name}</span>
                {availabilityBadge(profile)}
              </div>
              <p className="mt-1 text-xs text-muted">{profile.source_organization}</p>
              <p className="mt-1 text-xs text-muted line-clamp-2">{profile.description}</p>
              <div className="mt-2 flex items-center gap-3 text-[10px] text-muted">
                <span className="rounded bg-text/5 px-1.5 py-0.5 font-mono">
                  {profile.connector_family}
                </span>
                {profile.estimated_datasets != null && (
                  <span>{profile.estimated_datasets.toLocaleString()} datasets</span>
                )}
              </div>
              {(profile.tags ?? []).length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {(profile.tags ?? []).slice(0, 4).map((tag) => (
                    <span
                      key={tag}
                      className="rounded bg-text/5 px-1.5 py-0.5 text-[10px] text-muted"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </button>
          ))}
        </div>
      </Card>

      {/* Ingest panel */}
      {selectedProfile && (
        <Card>
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted">
            Fetch Data from {selectedProfile.display_name}
          </h3>
          <div className="space-y-4">
            <div className="rounded-lg border border-accent/20 bg-accent/5 p-3">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-sm font-semibold">{selectedProfile.display_name}</span>
                  <span className="ml-2 text-xs text-muted">
                    {selectedProfile.source_organization}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedProfileId(null);
                    setIngestResult(null);
                  }}
                  className="text-xs text-muted hover:text-text"
                >
                  Clear
                </button>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs text-muted">Connector ID</label>
                <input
                  type="text"
                  value={form.connectorId}
                  onChange={(e) => setForm({ ...form, connectorId: e.target.value })}
                  placeholder={`${selectedProfile.connector_family}.wdi`}
                  className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-xs"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-muted">Dataset ID</label>
                <input
                  type="text"
                  value={form.datasetId}
                  onChange={(e) => setForm({ ...form, datasetId: e.target.value })}
                  placeholder="NY.GDP.MKTP.CD"
                  className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-xs"
                />
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              <div>
                <label className="mb-1 block text-xs text-muted">Country Filter</label>
                <input
                  type="text"
                  value={form.countryFilter}
                  onChange={(e) => setForm({ ...form, countryFilter: e.target.value })}
                  placeholder="USA, GBR, ..."
                  className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-xs"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-muted">Date Start</label>
                <input
                  type="text"
                  value={form.dateStart}
                  onChange={(e) => setForm({ ...form, dateStart: e.target.value })}
                  placeholder="2020-01-01"
                  className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-xs"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-muted">Date End</label>
                <input
                  type="text"
                  value={form.dateEnd}
                  onChange={(e) => setForm({ ...form, dateEnd: e.target.value })}
                  placeholder="2024-12-31"
                  className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-xs"
                />
              </div>
            </div>

            <div>
              <label className="mb-1 block text-xs text-muted">Cache Policy</label>
              <select
                value={form.cachePolicy}
                onChange={(e) => setForm({ ...form, cachePolicy: e.target.value })}
                className="rounded-lg border border-line bg-surface px-3 py-1.5 text-sm"
              >
                <option value="default">default</option>
                <option value="static">static (never expires)</option>
                <option value="volatile">volatile (always re-fetch)</option>
                <option value="smart">smart (adaptive)</option>
              </select>
            </div>

            <button
              type="button"
              disabled={ingestMutation.isPending || !form.datasetId.trim()}
              onClick={handleIngest}
              className="rounded-xl bg-accent px-6 py-2.5 text-sm font-semibold text-white transition hover:bg-accent/90 disabled:opacity-50"
            >
              {ingestMutation.isPending ? "Fetching..." : "Fetch & Store"}
            </button>

            {ingestMutation.error && <ApiErrorAlert error={ingestMutation.error} />}

            {ingestResult && (
              <div className="space-y-2 rounded-lg border border-line/50 bg-surface/50 p-3">
                <p className="text-sm text-green-500">{ingestResult.message}</p>
                {ingestResult.evidenceRef && (
                  <p className="text-xs text-muted">
                    Evidence:{" "}
                    <Link
                      to={`/artifacts/${ingestResult.evidenceRef}`}
                      className="font-mono text-accent underline"
                    >
                      {ingestResult.evidenceRef.slice(0, 16)}...
                    </Link>
                  </p>
                )}
                {ingestResult.snapshotRef && (
                  <p className="text-xs text-muted">
                    Data Snapshot:{" "}
                    <Link
                      to={`/artifacts/${ingestResult.snapshotRef}`}
                      className="font-mono text-accent underline"
                    >
                      {ingestResult.snapshotRef.slice(0, 16)}...
                    </Link>
                  </p>
                )}
                {ingestResult.warnings.length > 0 && (
                  <ul className="text-xs text-yellow-600">
                    {ingestResult.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
