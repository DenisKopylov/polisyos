import { useEffect, useMemo, useState, type ReactNode } from "react";

import {
  type CapturedCapabilitySearch,
  type CapabilitySearchRequest,
  useCapabilitySearch,
  withCapabilitySearchQuery,
} from "@/api/hooks/useCapabilitySearch";
import { downloadCapabilityDiscoveryMachine } from "@/features/evidence/export/capabilityDiscoveryTwin";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Badge, Button, Card } from "@polisyos/atlas-ui";

type CapabilityDiscoveryPanelProps = Readonly<{
  baseUrl?: string;
  onCaptured?: (captured: CapturedCapabilitySearch) => void;
  request: CapabilitySearchRequest;
}>;

type PacketPathPart = number | string;
type PacketLeafType =
  | "array"
  | "boolean"
  | "null"
  | "number"
  | "object"
  | "string";

function packetLeafType(value: unknown): PacketLeafType {
  if (value === null) {
    return "null";
  }
  if (Array.isArray(value)) {
    return "array";
  }
  if (typeof value === "object") {
    return "object";
  }
  if (typeof value === "boolean") return "boolean";
  if (typeof value === "number") return "number";
  if (typeof value === "string") return "string";
  throw new TypeError("capability packet contains a non-JSON value");
}

function packetEntries(
  value: unknown,
): readonly (readonly [PacketPathPart, unknown])[] {
  if (Array.isArray(value)) {
    return value.map((entry, index) => [index, entry ?? null] as const);
  }
  if (typeof value === "object" && value !== null) {
    return Object.entries(value)
      .filter(([, entry]) => entry !== undefined)
      .sort(([left], [right]) => left.localeCompare(right));
  }
  return [];
}

function packetLeafValue(
  type: PacketLeafType,
  value: unknown,
  entries: readonly (readonly [PacketPathPart, unknown])[],
) {
  if (type === "array" || type === "object") {
    return String(entries.length);
  }
  if (type === "null") {
    return "null";
  }
  return String(value);
}

function renderCapabilityPacketLeaves(
  value: unknown,
  path: readonly PacketPathPart[] = [],
): ReactNode[] {
  const type = packetLeafType(value);
  const entries = packetEntries(value);
  const identity = JSON.stringify(path);
  return [
    <li
      key={"capability-packet-leaf:" + identity}
      data-capability-packet-leaf
      className="break-all"
    >
      <code data-capability-leaf-path>{identity}</code>
      {" · "}
      <span data-capability-leaf-type>{type}</span>
      {" · "}
      <span data-capability-leaf-value>
        {packetLeafValue(type, value, entries)}
      </span>
    </li>,
    ...entries.flatMap(([part, entry]) =>
      renderCapabilityPacketLeaves(entry, [...path, part]),
    ),
  ];
}

export function CapabilityDiscoveryPanel({
  baseUrl,
  onCaptured,
  request,
}: CapabilityDiscoveryPanelProps) {
  const { t } = useI18n();
  const [queryText, setQueryText] = useState(request.search.query_text);
  const searchRequest = useMemo(
    () => withCapabilitySearchQuery(request, queryText),
    [queryText, request],
  );
  const query = useCapabilitySearch(searchRequest, baseUrl);
  const captured = query.isError ? undefined : query.data;

  useEffect(() => {
    setQueryText(request.search.query_text);
  }, [request.search.query_text]);

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
  const { t } = useI18n();
  const { frontier, results } = captured.response;
  const { candidates, rejected_candidates: rejectedCandidates } = frontier;
  return (
    <div className="mt-4 space-y-3">
      <p aria-live="polite" role="status" className="sr-only">
        {t("capabilityDiscovery.resultAnnouncement", {
          count: results.length,
          status: frontier.completeness_status,
          reasons: frontier.incompleteness_reasons.join(", "),
        })}
      </p>
      <section aria-label={t("capabilityDiscovery.requestSection")}>
        <p className="text-sm font-medium">
          {t("capabilityDiscovery.requestLabel")}{" "}
          <span data-capability-request-query>
            {captured.response.request.search.query_text}
          </span>
        </p>
        <p className="text-muted text-xs">
          <span data-capability-request-audience>
            {captured.response.request.audience}
          </span>{" "}
          ·{" "}
          {captured.response.request.resource_kinds.map((kind, index) => (
            <span key={kind}>
              {index > 0 ? ", " : null}
              <span data-capability-request-kind>{kind}</span>
            </span>
          ))}{" "}
          ·{" "}
          {captured.response.request.search.allowed_modes.map((mode, index) => (
            <span key={mode}>
              {index > 0 ? ", " : null}
              <span data-capability-request-mode>{mode}</span>
            </span>
          ))}
        </p>
      </section>
      <div>
        <Badge kind="neutral">
          <span data-capability-completeness-status>
            {frontier.completeness_status}
          </span>
        </Badge>
        <p className="text-muted mt-1 text-sm">
          {frontier.incompleteness_reasons.length > 0
            ? frontier.incompleteness_reasons.map((reason, index) => (
                <span key={`${reason}:${index}`}>
                  {index > 0 ? ", " : null}
                  <span data-capability-incompleteness-reason>{reason}</span>
                </span>
              ))
            : t("capabilityDiscovery.complete")}
        </p>
      </div>
      {results.length === 0 ? (
        <p className="text-muted text-sm">{t("capabilityDiscovery.noHit")}</p>
      ) : null}
      <ul className="space-y-2">
        {results.map((item) => (
          <li
            key={item.capability_ref}
            data-capability-ref={item.capability_ref}
            data-capability-result
          >
            <p className="font-medium" data-capability-result-label>
              {item.label}
            </p>
            <p
              className="text-muted text-sm"
              data-capability-result-description
            >
              {item.description}
            </p>
            <p className="text-muted text-xs">
              <span data-capability-result-kind>{item.resource_kind}</span> ·{" "}
              {item.discovery_result.state} · {item.execution_result.state} ·{" "}
              {item.authority_result.state}
            </p>
            <p className="text-muted text-xs">
              {t("capabilityDiscovery.referenceLabel")}{" "}
              <span data-capability-result-ref>{item.capability_ref}</span>
            </p>
            <span
              className="[&>span]:text-foreground inline-flex rounded-[var(--radius-pill)] bg-[var(--paper)]"
              data-capability-candidate-backdrop="true"
            >
              <Badge kind="neutral">
                {t("capabilityDiscovery.candidateLabel")} ·{" "}
                {item.authority_result.state}
              </Badge>
            </span>
            <ul
              aria-label={t("capabilityDiscovery.postureProofs")}
              className="mt-2"
            >
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
                  <li
                    key={name as string}
                    className="mt-1 text-xs"
                    data-capability-posture={name as string}
                  >
                    <strong>{name as string}</strong>:{" "}
                    <span data-capability-posture-state>{proof.state}</span> ·
                    {t("capabilityDiscovery.producerLabel")}{" "}
                    <span data-capability-posture-producer>
                      {proof.producer_ref}
                    </span>{" "}
                    · {t("capabilityDiscovery.freshnessLabel")}{" "}
                    <span data-capability-posture-freshness>
                      {proof.time.freshness}
                    </span>
                    <br />
                    {t("capabilityDiscovery.reasonsLabel")}{" "}
                    {proof.reason_codes.length > 0
                      ? proof.reason_codes.map((reason, index) => (
                          <span key={`${reason}:${index}`}>
                            {index > 0 ? ", " : null}
                            <span data-capability-posture-reason>{reason}</span>
                          </span>
                        ))
                      : t("capabilityDiscovery.none")}{" "}
                    · {t("capabilityDiscovery.proofRefsLabel")}{" "}
                    {refs.length > 0
                      ? refs.map((ref, index) => (
                          <span key={`${ref}:${index}`}>
                            {index > 0 ? ", " : null}
                            <span data-capability-posture-proof-ref>{ref}</span>
                          </span>
                        ))
                      : t("capabilityDiscovery.none")}{" "}
                    · {t("capabilityDiscovery.provenanceLabel")}{" "}
                    {proof.provenance_refs.length > 0
                      ? proof.provenance_refs.map((ref, index) => (
                          <span key={`${ref}:${index}`}>
                            {index > 0 ? ", " : null}
                            <span data-capability-posture-provenance-ref>
                              {ref}
                            </span>
                          </span>
                        ))
                      : t("capabilityDiscovery.none")}
                  </li>
                );
              })}
            </ul>
          </li>
        ))}
      </ul>
      <section aria-label={t("capabilityDiscovery.frontier")}>
        <p className="text-sm font-medium">
          {t("capabilityDiscovery.frontier")}
        </p>
        <p className="text-muted text-xs">
          {t("capabilityDiscovery.requestedLabel")}{" "}
          <span data-capability-frontier-requested>
            {frontier.requested_count}
          </span>{" "}
          · {t("capabilityDiscovery.evaluatedLabel")}{" "}
          <span data-capability-frontier-evaluated>
            {frontier.evaluated_count}
          </span>{" "}
          · {t("capabilityDiscovery.returnedLabel")}{" "}
          <span data-capability-frontier-returned>
            {frontier.returned_count}
          </span>{" "}
          · {t("capabilityDiscovery.cutoffLabel")}{" "}
          <span data-capability-frontier-cutoff>
            {String(frontier.actual_cutoff)}
          </span>
        </p>
        <p className="text-muted text-xs">
          {t("capabilityDiscovery.indexesLabel")}{" "}
          {frontier.indexes_used.length > 0
            ? frontier.indexes_used.map((indexRef, index) => (
                <span key={`${indexRef}:${index}`}>
                  {index > 0 ? ", " : null}
                  <span data-capability-frontier-index>{indexRef}</span>
                </span>
              ))
            : t("capabilityDiscovery.none")}{" "}
          · {t("capabilityDiscovery.versionsLabel")}{" "}
          {frontier.index_version_refs.length > 0
            ? frontier.index_version_refs.map((version, index) => (
                <span key={`${version}:${index}`}>
                  {index > 0 ? ", " : null}
                  <span data-capability-frontier-index-version>{version}</span>
                </span>
              ))
            : t("capabilityDiscovery.none")}{" "}
          · {t("capabilityDiscovery.freshnessLabel")}{" "}
          <span data-capability-frontier-index-freshness>
            {JSON.stringify(frontier.index_freshness ?? null)}
          </span>
        </p>
        <p className="text-muted text-xs">
          {t("capabilityDiscovery.noHitFrontierLabel")}{" "}
          {frontier.no_hit_frontier.length > 0
            ? frontier.no_hit_frontier.map((reason, index) => (
                <span key={`${reason}:${index}`}>
                  {index > 0 ? ", " : null}
                  <span data-capability-frontier-no-hit>{reason}</span>
                </span>
              ))
            : t("capabilityDiscovery.none")}
        </p>
        <ul className="text-muted mt-1 text-xs">
          {candidates.map((candidate) => (
            <li
              key={`selected:${candidate.candidate_ref}`}
              data-capability-candidate="selected"
            >
              {t("capabilityDiscovery.selectedLabel")}{" "}
              <span data-capability-candidate-ref>
                {candidate.candidate_ref}
              </span>{" "}
              · {t("capabilityDiscovery.evidenceLabel")}{" "}
              {candidate.evidence_refs.length > 0
                ? candidate.evidence_refs.map((ref, index) => (
                    <span key={`${ref}:${index}`}>
                      {index > 0 ? ", " : null}
                      <span data-capability-candidate-evidence-ref>{ref}</span>
                    </span>
                  ))
                : t("capabilityDiscovery.none")}{" "}
              · {t("capabilityDiscovery.limitationsLabel")}{" "}
              {candidate.limitation_refs.length > 0
                ? candidate.limitation_refs.map((ref, index) => (
                    <span key={`${ref}:${index}`}>
                      {index > 0 ? ", " : null}
                      <span data-capability-candidate-limitation-ref>
                        {ref}
                      </span>
                    </span>
                  ))
                : t("capabilityDiscovery.none")}
            </li>
          ))}
          {rejectedCandidates.map((candidate) => (
            <li
              key={`rejected:${candidate.candidate_ref}`}
              data-capability-candidate="rejected"
            >
              {t("capabilityDiscovery.rejectedLabel")}{" "}
              <span data-capability-candidate-ref>
                {candidate.candidate_ref}
              </span>{" "}
              · {t("capabilityDiscovery.evidenceLabel")}{" "}
              {candidate.evidence_refs.length > 0
                ? candidate.evidence_refs.map((ref, index) => (
                    <span key={`${ref}:${index}`}>
                      {index > 0 ? ", " : null}
                      <span data-capability-candidate-evidence-ref>{ref}</span>
                    </span>
                  ))
                : t("capabilityDiscovery.none")}{" "}
              · {t("capabilityDiscovery.limitationsLabel")}{" "}
              {candidate.limitation_refs.length > 0
                ? candidate.limitation_refs.map((ref, index) => (
                    <span key={`${ref}:${index}`}>
                      {index > 0 ? ", " : null}
                      <span data-capability-candidate-limitation-ref>
                        {ref}
                      </span>
                    </span>
                  ))
                : t("capabilityDiscovery.none")}
            </li>
          ))}
        </ul>
      </section>
      <details open className="text-muted text-xs">
        <summary className="cursor-pointer font-medium">
          {t("capabilityDiscovery.packetBindings")}
        </summary>
        {/* eslint-disable jsx-a11y/no-noninteractive-tabindex -- This bounded scroll region must remain keyboard-focusable without replacing list semantics. */}
        <ul
          aria-label={t("capabilityDiscovery.packetBindings")}
          className="mt-1 max-h-64 space-y-1 overflow-auto font-mono"
          tabIndex={0}
        >
          {renderCapabilityPacketLeaves(captured.response)}
        </ul>
        {/* eslint-enable jsx-a11y/no-noninteractive-tabindex */}
      </details>
    </div>
  );
}
