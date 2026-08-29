import { Download, Snowflake, TriangleAlert } from "lucide-react";

import { Glyph } from "@/shared/brand/Glyph";
import { useOptionalI18n } from "@/shared/i18n/LocaleProvider";
import { cn } from "@/shared/lib/utils";
import {
  type EpochSemantics,
  isEpochSemantics,
  TimeSemanticsLabel,
} from "@/shared/ui/temporal/TimeSemanticsLabel";

import type { AdmittedEpochStalenessProjection } from "../domain/epochStaleness";
import { downloadEpochStalenessMachine } from "../export/epochStalenessTwin";

export function epochSemanticsFromProjection(
  projection: AdmittedEpochStalenessProjection,
): EpochSemantics {
  const candidate = Object.freeze({
    asOf: projection.owner_as_of ?? null,
    asOfReason: projection.owner_time_reason ?? null,
    currentEpochRef: projection.current_epoch_ref ?? null,
    epochRefs: Object.freeze([...(projection.scoped_epoch_refs ?? [])]),
    kind: "admitted",
    projectionSemanticHash: projection.projection_semantic_hash ?? null,
    revalidationRequired: projection.revalidation_required ?? false,
    status: projection.status ?? "not_established",
    validityStatus: projection.decision_validity_status ?? null,
  });
  if (!isEpochSemantics(candidate)) {
    throw new TypeError(
      "strict epoch projection did not produce complete chrome semantics",
    );
  }
  return candidate;
}

export function EpochStalenessView({
  projection,
  rawBytes,
}: {
  projection: AdmittedEpochStalenessProjection;
  rawBytes: Uint8Array;
}) {
  const { t } = useOptionalI18n();
  const epochSemantics = epochSemanticsFromProjection(projection);

  return (
    <section
      aria-labelledby="epoch-staleness-title"
      className="grid gap-4 rounded-lg border border-[var(--line)] p-4"
      data-epoch-status={projection.status}
      data-testid="epoch-staleness-view"
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-muted font-mono text-xs tracking-wide uppercase">
            {t("epochChrome.eyebrow")}
          </p>
          <h2 id="epoch-staleness-title" className="text-lg font-semibold">
            {t("epochChrome.title")}
          </h2>
        </div>
        <button
          className="inline-flex min-h-10 items-center gap-2 rounded-md border border-[var(--line)] px-3 text-sm font-semibold"
          onClick={() =>
            downloadEpochStalenessMachine(rawBytes, projection.run_id)
          }
          type="button"
        >
          <Download aria-hidden="true" className="size-4" />
          {t("epochChrome.machine")}
        </button>
      </header>

      <TimeSemanticsLabel
        epochSemantics={epochSemantics}
        payloadAsOf={projection.owner_as_of}
        txAt={projection.temporal_scope.tx_at}
        validAt={projection.temporal_scope.valid_at}
      />

      {projection.fixture_only ? (
        <div
          className="flex items-start gap-2 rounded-md border border-dashed border-[var(--color-status-warning)] bg-[color-mix(in_srgb,var(--color-status-warning)_8%,transparent)] p-3"
          data-testid="epoch-fixture-only"
          role="status"
        >
          <TriangleAlert
            aria-hidden="true"
            className="mt-0.5 size-4 shrink-0"
          />
          <div>
            <p className="font-semibold">
              {t("epochChrome.fixtureOnly.title")}
            </p>
            <p className="text-muted text-sm">
              {t("epochChrome.fixtureOnly.description")}
            </p>
          </div>
        </div>
      ) : null}

      {projection.open_world_risk.promotion_frozen ? (
        <div
          className="flex items-start gap-2 rounded-md border border-[var(--color-status-warning)] bg-[color-mix(in_srgb,var(--color-status-warning)_12%,transparent)] p-3"
          data-testid="epoch-open-world-freeze"
          role="status"
        >
          <Snowflake aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          <div>
            <p className="font-semibold">{t("epochChrome.openWorldFreeze")}</p>
            <p className="text-muted text-sm">
              {projection.open_world_risk.limitation_code}
            </p>
          </div>
        </div>
      ) : null}

      <div className="grid gap-3 lg:grid-cols-2">
        {projection.institutional_absences.map((absence) => (
          <article
            className="rounded-md border border-dashed border-[var(--color-status-warning)] p-3"
            data-absence-class="institutional"
            data-testid={`epoch-absence-${absence.role}`}
            key={absence.role}
          >
            <p className="font-semibold">
              {t("epochChrome.absence.institutional")}
            </p>
            <p className="text-muted mt-1 text-sm">{absence.consequence}</p>
            <dl className="mt-2 grid gap-1 text-xs">
              <div>
                <dt className="font-semibold">
                  {t("epochChrome.labels.typedRefusal")}
                </dt>
                <dd className="font-mono">{absence.refusal_code}</dd>
              </div>
              <div>
                <dt className="font-semibold">
                  {t("epochChrome.labels.institutionalDependency")}
                </dt>
                <dd>{absence.closure_condition}</dd>
              </div>
            </dl>
          </article>
        ))}

        {projection.engineering_absences.map((absence) => (
          <article
            className="rounded-md border border-dashed border-[var(--line)] p-3"
            data-absence-class="engineering"
            data-testid={`epoch-absence-${absence.capability}`}
            key={absence.capability}
          >
            <p className="font-semibold">
              {t("epochChrome.absence.engineering")}
            </p>
            <p className="text-muted mt-1 text-sm">{absence.consequence}</p>
            <dl className="mt-2 grid gap-1 text-xs">
              <div>
                <dt className="font-semibold">
                  {t("epochChrome.labels.candidateOwner")}
                </dt>
                <dd className="font-mono break-all">
                  {absence.candidate_owner_module}
                </dd>
              </div>
              <div>
                <dt className="font-semibold">
                  {t("epochChrome.labels.engineeringClosure")}
                </dt>
                <dd>{absence.closure_condition}</dd>
              </div>
            </dl>
          </article>
        ))}
      </div>

      <details className="rounded-md border border-[var(--line)] p-3">
        <summary className="cursor-pointer font-semibold">
          {t("epochChrome.replayInspection")}
        </summary>
        <div className="mt-3 grid gap-4">
          <section aria-labelledby="epoch-certificates-title">
            <h3 id="epoch-certificates-title" className="font-semibold">
              {t("epochChrome.certificates.title")}
            </h3>
            {projection.certificates.length === 0 ? (
              <p className="text-muted text-sm">
                {t("epochChrome.certificates.empty")}
              </p>
            ) : (
              <ul className="mt-2 grid gap-2">
                {projection.certificates.map((certificate) => (
                  <li
                    className={cn(
                      "rounded border p-2 text-sm",
                      certificate.status === "current"
                        ? "border-[var(--color-status-approved)]"
                        : "border-[var(--color-status-warning)] bg-[color-mix(in_srgb,var(--color-status-warning)_12%,transparent)] line-through decoration-[var(--color-status-warning)]",
                    )}
                    data-certificate-status={certificate.status}
                    data-testid={`epoch-certificate-${certificate.certificate_ref.artifact_id}`}
                    key={certificate.certificate_ref.artifact_id}
                  >
                    <strong>
                      {t(`epochChrome.status.${certificate.status}`)}
                    </strong>
                    {certificate.stale_reasons.length > 0
                      ? ` — ${certificate.stale_reasons.join("; ")}`
                      : null}
                    {certificate.revalidation_requirements.length > 0 ? (
                      <span className="block no-underline">
                        {t("epochChrome.certificates.revalidation", {
                          requirements:
                            certificate.revalidation_requirements.join("; "),
                        })}
                      </span>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section aria-labelledby="epoch-dependencies-title">
            <h3 id="epoch-dependencies-title" className="font-semibold">
              {t("epochChrome.dependencies.title")}
            </h3>
            {projection.dependencies.length === 0 ? (
              <p className="text-muted text-sm">
                {t("epochChrome.dependencies.empty")}
              </p>
            ) : (
              <ul className="mt-2 grid gap-2">
                {projection.dependencies.map((dependency) => (
                  <li
                    className="rounded border border-[var(--line)] p-2 text-sm"
                    key={`${dependency.source_ref.artifact_id}:${dependency.target_ref.artifact_id}`}
                  >
                    {t("epochChrome.dependencies.summary", {
                      disposition: t(
                        `epochChrome.disposition.${dependency.disposition}`,
                      ),
                      relation: dependency.relation,
                      status: t(
                        `epochChrome.recomputeStatus.${dependency.recompute.status}`,
                      ),
                    })}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section aria-labelledby="epoch-perturbations-title">
            <h3 id="epoch-perturbations-title" className="font-semibold">
              {t("epochChrome.perturbations.title")}
            </h3>
            {projection.perturbations.length === 0 ? (
              <p className="text-muted text-sm">
                {t("epochChrome.perturbations.empty")}
              </p>
            ) : (
              <ul className="mt-2 grid gap-2 sm:grid-cols-2">
                {projection.perturbations.map((event) => (
                  <li
                    className="rounded border border-[var(--color-status-warning)] p-2 text-sm"
                    data-testid={`epoch-perturbation-${event.source_class}`}
                    key={event.event_ref.artifact_id}
                  >
                    <span className="font-semibold">
                      {t(`epochChrome.perturbation.${event.source_class}`)}
                    </span>
                    {` — ${t(`epochChrome.scope.${event.scope}`)}; ${t(
                      `epochChrome.disposition.${event.adjudicated_disposition}`,
                    )}`}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section aria-labelledby="epoch-lineage-title">
            <h3 id="epoch-lineage-title" className="font-semibold">
              {t("epochChrome.lineage.title")}
            </h3>
            {projection.lineage.length === 0 ? (
              <p className="text-muted text-sm">
                {t("epochChrome.lineage.empty")}
              </p>
            ) : (
              <ol className="mt-2 grid gap-2">
                {projection.lineage.map((boundary) => (
                  <li
                    key={`${boundary.previous_epoch_ref}:${boundary.current_epoch_ref}`}
                  >
                    <button
                      className="w-full rounded border border-[var(--line)] p-2 text-left font-mono text-xs"
                      data-testid="epoch-boundary"
                      type="button"
                    >
                      <span className="block font-sans font-semibold">
                        {t("epochChrome.epochBoundary")}
                      </span>
                      <span className="block break-all">
                        {boundary.previous_epoch_ref}
                      </span>
                      <span className="flex justify-center py-1">
                        <Glyph decorative name="freshness" size={16} />
                      </span>
                      <span className="block break-all">
                        {boundary.current_epoch_ref}
                      </span>
                    </button>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </div>
      </details>

      {projection.status !== "current" ? (
        <p className="flex items-start gap-2 text-sm" role="status">
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-4" />
          {t("epochChrome.inspectableNoncurrent")}
        </p>
      ) : null}
    </section>
  );
}
