import { useEffect, useMemo, useState } from "react";

import {
  type CapturedCapabilitySearch,
  type CapabilitySearchRequest,
  useCapabilitySearch,
} from "@/api/hooks/useCapabilitySearch";
import { downloadCapabilityDiscoveryMachine } from "@/features/evidence/export/capabilityDiscoveryTwin";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Badge, Button, Card } from "@polisyos/atlas-ui";

type CapabilityDiscoveryPanelProps = Readonly<{
  baseUrl?: string;
  onCaptured?: (captured: CapturedCapabilitySearch) => void;
  request: CapabilitySearchRequest;
}>;

export function CapabilityDiscoveryPanel({
  baseUrl,
  onCaptured,
  request,
}: CapabilityDiscoveryPanelProps) {
  const { t } = useI18n();
  const [queryText, setQueryText] = useState(request.search.query_text);
  const normalizedQuery = queryText.trim() || "all-capabilities";
  const searchRequest = useMemo(
    () => ({
      ...request,
      search: {
        ...request.search,
        construct_refs: [normalizedQuery],
        query_text: normalizedQuery,
      },
    }),
    [normalizedQuery, request],
  );
  const query = useCapabilitySearch(searchRequest, baseUrl);
  const captured = query.data;

  useEffect(() => {
    if (captured) {
      onCaptured?.(captured);
    }
  }, [captured, onCaptured]);

  return (
    <Card data-testid="capability-discovery-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-muted text-xs font-semibold tracking-[0.18em] uppercase">
            {t("capabilityDiscovery.eyebrow")}
          </p>
          <h3 className="text-lg font-semibold">
            {t("capabilityDiscovery.title")}
          </h3>
        </div>
        {captured ? (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() =>
              downloadCapabilityDiscoveryMachine(captured.rawBytes)
            }
          >
            {t("capabilityDiscovery.downloadMachine")}
          </Button>
        ) : null}
      </div>
      <label
        className="mt-4 block text-sm font-medium"
        htmlFor="capability-discovery-search"
      >
        {t("capabilityDiscovery.searchLabel")}
      </label>
      <input
        id="capability-discovery-search"
        className="mt-1 w-full rounded border px-3 py-2"
        value={queryText}
        onChange={(event) => setQueryText(event.target.value)}
      />
      {query.isLoading ? (
        <p className="text-muted mt-3 text-sm">{t("common.loading")}</p>
      ) : null}
      {query.isError ? (
        <p className="mt-3 text-sm text-red-700">
          {t("capabilityDiscovery.unavailable")}
        </p>
      ) : null}
      {captured ? <CapabilityDiscoveryContent captured={captured} /> : null}
    </Card>
  );
}

function CapabilityDiscoveryContent({
  captured,
}: Readonly<{ captured: CapturedCapabilitySearch }>) {
  const { frontier, results, ...envelope } = captured.response;
  const {
    candidates,
    rejected_candidates: rejectedCandidates,
    ...frontierEnvelope
  } = frontier;
  return (
    <div
      className="mt-4 space-y-3"
      data-capability-envelope={JSON.stringify(envelope)}
    >
      <p aria-live="polite" role="status" className="sr-only">
        Candidate search returned {results.length} results;{" "}
        {frontier.completeness_status};{" "}
        {frontier.incompleteness_reasons.join(", ")}
      </p>
      <section aria-label="Capability request">
        <p className="text-sm font-medium">
          Request: {captured.response.request.search.query_text}
        </p>
        <p className="text-muted text-xs">
          {captured.response.request.audience} ·{" "}
          {captured.response.request.resource_kinds.join(", ")} ·{" "}
          {captured.response.request.search.allowed_modes.join(", ")}
        </p>
      </section>
      <div data-capability-completeness={frontier.completeness_status}>
        <Badge kind="neutral">{frontier.completeness_status}</Badge>
        <p className="text-muted mt-1 text-sm">
          {frontier.incompleteness_reasons.join(", ") ||
            "No incompleteness was reported."}
        </p>
      </div>
      {results.length === 0 ? (
        <p className="text-muted text-sm">No capability matched this search.</p>
      ) : null}
      <ul className="space-y-2">
        {results.map((item) => (
          <li
            key={item.capability_ref}
            data-capability-ref={item.capability_ref}
            data-capability-result={JSON.stringify(item)}
            data-capability-discovery-posture={JSON.stringify(
              item.discovery_result,
            )}
            data-capability-execution-posture={JSON.stringify(
              item.execution_result,
            )}
            data-capability-authority-posture={JSON.stringify(
              item.authority_result,
            )}
          >
            <p className="font-medium">{item.label}</p>
            <p className="text-muted text-sm">{item.description}</p>
            <p className="text-muted text-xs">
              {item.resource_kind} · {item.discovery_result.state} ·{" "}
              {item.execution_result.state} · {item.authority_result.state}
            </p>
            <Badge kind="neutral">
              Candidate · {item.authority_result.state}
            </Badge>
            <ul aria-label="Capability posture proofs" className="mt-2">
              {[
                ["discovery", item.discovery_result],
                ["execution", item.execution_result],
                ["authority", item.authority_result],
              ].map(([name, posture]) => {
                const proof = posture as typeof item.discovery_result;
                const refs = Object.entries(proof)
                  .filter(
                    ([key, value]) => key.endsWith("_ref") && Boolean(value),
                  )
                  .map(([key, value]) => `${key}=${String(value)}`);
                return (
                  <li key={name as string} className="mt-1 text-xs">
                    <strong>{name as string}</strong>: {proof.state} · producer:{" "}
                    {proof.producer_ref} · freshness: {proof.time.freshness}
                    <br />
                    reasons: {proof.reason_codes.join(", ") || "none"} · proof
                    refs: {refs.join(", ") || "none"} · provenance:{" "}
                    {proof.provenance_refs.join(", ") || "none"}
                  </li>
                );
              })}
            </ul>
          </li>
        ))}
      </ul>
      <section
        aria-label="Search frontier"
        data-capability-frontier={JSON.stringify(frontierEnvelope)}
      >
        <p className="text-sm font-medium">Search frontier</p>
        <p className="text-muted text-xs">
          requested {frontier.requested_count} · evaluated{" "}
          {frontier.evaluated_count} · returned {frontier.returned_count} ·
          cutoff {String(frontier.actual_cutoff)}
        </p>
        <p className="text-muted text-xs">
          indexes: {frontier.indexes_used.join(", ")} · versions:{" "}
          {frontier.index_version_refs.join(", ")} · freshness:{" "}
          {JSON.stringify(frontier.index_freshness ?? null)}
        </p>
        <p className="text-muted text-xs">
          no-hit frontier: {frontier.no_hit_frontier.join(", ") || "none"}
        </p>
        <ul className="text-muted mt-1 text-xs">
          {candidates.map((candidate) => (
            <li
              key={`selected:${candidate.candidate_ref}`}
              data-capability-candidate={JSON.stringify(candidate)}
            >
              selected: {candidate.candidate_ref} · evidence:{" "}
              {candidate.evidence_refs.join(", ") || "none"} · limitations:{" "}
              {candidate.limitation_refs.join(", ") || "none"}
            </li>
          ))}
          {rejectedCandidates.map((candidate) => (
            <li
              key={`rejected:${candidate.candidate_ref}`}
              data-capability-rejected={JSON.stringify(candidate)}
            >
              rejected: {candidate.candidate_ref} · evidence:{" "}
              {candidate.evidence_refs.join(", ") || "none"} · limitations:{" "}
              {candidate.limitation_refs.join(", ") || "none"}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
