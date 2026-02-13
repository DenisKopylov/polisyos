import { useState } from "react";
import { Link } from "react-router-dom";

import { useCacheStatus } from "../api/hooks/useCacheStatus";
import { useConnectors } from "../api/hooks/useConnectors";
import { useIngestData, type IngestRequest } from "../api/hooks/useIngestData";
import ApiErrorAlert from "../components/shared/ApiErrorAlert";
import { Card } from "../components/ui/card";
import { cn } from "../lib/utils";

type DatasetSelection = {
  connector_id: string;
  dataset_id: string;
  selected: boolean;
};

export default function DataManagement() {
  const connectorsQuery = useConnectors();
  const cacheQuery = useCacheStatus();
  const ingestMutation = useIngestData();

  const [selectedDatasets, setSelectedDatasets] = useState<DatasetSelection[]>([]);
  const [countryFilter, setCountryFilter] = useState("");
  const [dateStart, setDateStart] = useState("");
  const [dateEnd, setDateEnd] = useState("");
  const [cachePolicy, setCachePolicy] = useState("default");
  const [ingestResult, setIngestResult] = useState<{
    message: string;
    snapshotRef: string | null;
    evidenceRef: string | null;
    warnings: string[];
  } | null>(null);

  const connectors = connectorsQuery.data?.connectors ?? [];

  // Build selectable datasets from connectors
  function getAvailableDatasets(): DatasetSelection[] {
    const datasets: DatasetSelection[] = [];
    for (const c of connectors) {
      for (const ds of c.known_datasets ?? []) {
        const existing = selectedDatasets.find(
          (s) => s.connector_id === c.connector_id && s.dataset_id === ds,
        );
        datasets.push({
          connector_id: c.connector_id,
          dataset_id: ds,
          selected: existing?.selected ?? false,
        });
      }
    }
    return datasets;
  }

  function toggleDataset(connectorId: string, datasetId: string) {
    setSelectedDatasets((prev) => {
      const existing = prev.find(
        (s) => s.connector_id === connectorId && s.dataset_id === datasetId,
      );
      if (existing) {
        return prev.map((s) =>
          s.connector_id === connectorId && s.dataset_id === datasetId
            ? { ...s, selected: !s.selected }
            : s,
        );
      }
      return [...prev, { connector_id: connectorId, dataset_id: datasetId, selected: true }];
    });
  }

  function handleIngest() {
    const selected = getAvailableDatasets().filter((d) => d.selected);
    if (selected.length === 0) return;

    const filters: Record<string, string[]> = {};
    if (countryFilter.trim()) {
      filters["country"] = countryFilter
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
    }

    const body: IngestRequest = {
      datasets: selected.map((d) => ({
        connector_id: d.connector_id,
        dataset_id: d.dataset_id,
        filters,
        date_start: dateStart || null,
        date_end: dateEnd || null,
      })),
      source: "dashboard",
      license_name: "open",
      cache_policy: cachePolicy,
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

  const availableDatasets = getAvailableDatasets();
  const selectedCount = availableDatasets.filter((d) => d.selected).length;
  const cacheEntries = cacheQuery.data?.entries ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Data Management</h2>
        <p className="text-sm text-muted">
          Browse connectors, fetch data, and manage the local cache.
        </p>
      </div>

      {/* Connectors */}
      <Card>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted">
          Available Connectors
        </h3>
        {connectorsQuery.isLoading && <p className="text-sm text-muted">Loading connectors...</p>}
        {connectorsQuery.error && <ApiErrorAlert error={connectorsQuery.error} />}
        {connectors.length === 0 && !connectorsQuery.isLoading && (
          <p className="text-sm text-muted">No connectors registered.</p>
        )}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {connectors.map((c) => (
            <div
              key={c.connector_id}
              className="rounded-xl border border-line bg-surface p-3"
            >
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    "h-2 w-2 rounded-full",
                    c.loaded ? "bg-green-500" : "bg-gray-400",
                  )}
                />
                <span className="font-mono text-sm font-semibold">{c.connector_id}</span>
              </div>
              <p className="mt-1 text-xs text-muted">
                {c.namespace} v{c.version}
              </p>
              <p className="mt-1 text-xs text-muted">
                Datasets: {(c.known_datasets ?? []).length}
              </p>
              {(c.known_datasets ?? []).length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {(c.known_datasets ?? []).slice(0, 5).map((ds) => (
                    <span
                      key={ds}
                      className="rounded bg-text/5 px-1.5 py-0.5 font-mono text-[10px] text-muted"
                    >
                      {ds}
                    </span>
                  ))}
                  {(c.known_datasets ?? []).length > 5 && (
                    <span className="text-[10px] text-muted">
                      +{(c.known_datasets ?? []).length - 5} more
                    </span>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </Card>

      {/* Ingest form */}
      <Card>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted">
          Ingest Data
        </h3>

        {availableDatasets.length === 0 && (
          <p className="text-sm text-muted">
            No datasets available. Connectors may not have known_datasets populated.
          </p>
        )}

        {availableDatasets.length > 0 && (
          <div className="space-y-4">
            <div className="max-h-48 space-y-1 overflow-y-auto rounded-lg border border-line/50 bg-surface/50 p-2">
              {availableDatasets.map((d) => (
                <label
                  key={`${d.connector_id}:${d.dataset_id}`}
                  className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-sm hover:bg-text/5"
                >
                  <input
                    type="checkbox"
                    checked={d.selected}
                    onChange={() => toggleDataset(d.connector_id, d.dataset_id)}
                    className="accent-accent"
                  />
                  <span className="font-mono text-xs text-muted">{d.connector_id}</span>
                  <span className="text-xs">/</span>
                  <span className="font-mono text-xs">{d.dataset_id}</span>
                </label>
              ))}
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              <div>
                <label className="mb-1 block text-xs text-muted">Country Filter</label>
                <input
                  type="text"
                  value={countryFilter}
                  onChange={(e) => setCountryFilter(e.target.value)}
                  placeholder="USA, GBR, ..."
                  className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-xs"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-muted">Date Start</label>
                <input
                  type="text"
                  value={dateStart}
                  onChange={(e) => setDateStart(e.target.value)}
                  placeholder="2020-01-01"
                  className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-xs"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-muted">Date End</label>
                <input
                  type="text"
                  value={dateEnd}
                  onChange={(e) => setDateEnd(e.target.value)}
                  placeholder="2024-12-31"
                  className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-xs"
                />
              </div>
            </div>

            <div>
              <label className="mb-1 block text-xs text-muted">Cache Policy</label>
              <select
                value={cachePolicy}
                onChange={(e) => setCachePolicy(e.target.value)}
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
              disabled={ingestMutation.isPending || selectedCount === 0}
              onClick={handleIngest}
              className="rounded-xl bg-accent px-6 py-2.5 text-sm font-semibold text-white transition hover:bg-accent/90 disabled:opacity-50"
            >
              {ingestMutation.isPending
                ? "Fetching..."
                : `Fetch & Store ${selectedCount} Dataset(s)`}
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
        )}
      </Card>

      {/* Cache status */}
      <Card>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted">
          Cache Status
        </h3>
        {cacheQuery.isLoading && <p className="text-sm text-muted">Loading cache status...</p>}
        {cacheQuery.error && <ApiErrorAlert error={cacheQuery.error} />}
        {cacheQuery.data && (
          <div>
            <div className="mb-3 flex gap-6 text-sm">
              <span>
                Total entries:{" "}
                <span className="font-semibold">{cacheQuery.data.total_entries}</span>
              </span>
              <span>
                Total size:{" "}
                <span className="font-semibold">
                  {(cacheQuery.data.total_size_bytes / 1024).toFixed(1)} KB
                </span>
              </span>
            </div>
            {cacheEntries.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-line text-muted">
                      <th className="px-2 py-1">Connector</th>
                      <th className="px-2 py-1">Dataset</th>
                      <th className="px-2 py-1">Created</th>
                      <th className="px-2 py-1">Size</th>
                      <th className="px-2 py-1">Valid</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cacheEntries.map((entry) => (
                      <tr key={entry.cache_key} className="border-b border-line/50">
                        <td className="px-2 py-1 font-mono">{entry.connector_id}</td>
                        <td className="px-2 py-1 font-mono">{entry.dataset_id}</td>
                        <td className="px-2 py-1">{entry.created_at}</td>
                        <td className="px-2 py-1">{(entry.size_bytes / 1024).toFixed(1)} KB</td>
                        <td className="px-2 py-1">
                          {entry.is_valid ? (
                            <span className="text-green-500">Yes</span>
                          ) : (
                            <span className="text-red-500">No</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-muted">Cache is empty.</p>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
