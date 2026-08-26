import { useMemo } from "react";

import type {
  ClaimPostureAudience,
  ClaimPostureRegister as ClaimPostureRegisterArtifact,
  ClaimPostureRow,
} from "../domain/posture";
import { useOptionalI18n } from "@/shared/i18n/LocaleProvider";

type ClaimPostureRegisterProps = Readonly<{
  audience: Exclude<ClaimPostureAudience, "MACHINE">;
  register: ClaimPostureRegisterArtifact;
}>;

function nullableMarker(value: string | null) {
  return { "data-null": value === null ? "true" : "false" };
}

function sourceLabel(row: ClaimPostureRow): string {
  const coordinate = row.source_bindings[0]?.coordinate;
  return coordinate ? `${coordinate.path}:${coordinate.line}` : row.claim_id;
}

/** Render artifact-owned posture rows without enumerating claim subjects. */
export function ClaimPostureRegister({
  audience,
  register,
}: ClaimPostureRegisterProps) {
  const { t } = useOptionalI18n();
  const groupsByClaim = useMemo(() => {
    const memberships = new Map<string, string[]>();
    for (const group of register.projection_groups) {
      for (const claimId of group.claim_ids) {
        const groups = memberships.get(claimId) ?? [];
        groups.push(group.group_id);
        memberships.set(claimId, groups);
      }
    }
    return memberships;
  }, [register.projection_groups]);
  const publicClaims = register.claims.filter((claim) =>
    claim.audiences.includes("PUBLIC"),
  );

  return (
    <section
      aria-labelledby="trust-posture-register-title"
      data-testid="trust-posture-register"
      className="space-y-5"
    >
      <div>
        <p className="text-xs font-semibold tracking-[0.18em] text-[var(--slate)] uppercase">
          {t("trust.registerEyebrow")}
        </p>
        <h2
          id="trust-posture-register-title"
          className="mt-1 text-2xl font-bold text-[var(--ink)]"
        >
          {t("trust.registerTitle")}
        </h2>
        <p className="mt-2 max-w-3xl text-sm text-[var(--slate)]">
          {t("trust.registerFrame")}
        </p>
      </div>

      <ol className="space-y-4" data-trust-claim-list>
        {publicClaims.map((row) => (
          <li
            key={row.claim_id}
            data-claim-id={row.claim_id}
            data-trust-claim-row
            className="rounded-[var(--radius-lg)] border border-[var(--line)] bg-[var(--paper)] p-5 shadow-sm"
          >
            <div data-trust-claim-bearing>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p
                    className="font-mono text-[0.68rem] break-all text-[var(--slate)]"
                    data-trust-claim-id
                  >
                    {row.claim_id}
                  </p>
                  <h3
                    className="mt-1 text-base font-semibold break-words text-[var(--ink)]"
                    data-trust-subject
                    {...nullableMarker(row.subject)}
                  >
                    {row.subject ?? sourceLabel(row)}
                  </h3>
                </div>
                <span
                  data-trust-effective-state
                  className="rounded-[var(--radius-pill)] border border-[var(--line)] px-3 py-1 font-mono text-xs font-bold"
                >
                  {row.effective_state}
                </span>
              </div>

              <section className="mt-4">
                <h4 className="text-xs font-bold tracking-wide text-[var(--ink)] uppercase">
                  {t("trust.limitationsLabel")}
                </h4>
                {row.limitations.length > 0 ? (
                  <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-[var(--slate)]">
                    {row.limitations.map((limitation, index) => (
                      <li
                        key={`${row.claim_id}:limitation:${index}`}
                        data-trust-limitation
                      >
                        {limitation}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-1 text-sm text-[var(--slate)]">
                    {t("trust.noneDeclared")}
                  </p>
                )}
              </section>

              <section className="mt-4">
                <h4 className="text-xs font-bold tracking-wide text-[var(--ink)] uppercase">
                  {t("trust.blockersLabel")}
                </h4>
                {row.blocker_codes.length > 0 ? (
                  <ul className="mt-1 flex flex-wrap gap-2">
                    {row.blocker_codes.map((blocker, index) => (
                      <li
                        key={`${row.claim_id}:blocker:${index}`}
                        data-trust-blocker
                        className="rounded bg-[var(--canvas)] px-2 py-1 font-mono text-xs break-all"
                      >
                        {blocker}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-1 text-sm text-[var(--slate)]">
                    {t("trust.noneDeclared")}
                  </p>
                )}
              </section>

              <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-3">
                <div>
                  <dt className="font-semibold">{t("trust.reviewOnLabel")}</dt>
                  <dd data-trust-review-on {...nullableMarker(row.review_on)}>
                    {row.review_on ?? t("trust.notEstablished")}
                  </dd>
                </div>
                <div>
                  <dt className="font-semibold">{t("trust.reviewDueLabel")}</dt>
                  <dd data-trust-review-due {...nullableMarker(row.review_due)}>
                    {row.review_due ?? t("trust.notEstablished")}
                  </dd>
                </div>
                <div>
                  <dt className="font-semibold">
                    {t("trust.sourceAsOfLabel")}
                  </dt>
                  <dd
                    data-trust-source-as-of
                    {...nullableMarker(row.source_as_of)}
                  >
                    {row.source_as_of ?? t("trust.notEstablished")}
                  </dd>
                </div>
              </dl>

              <section className="mt-4">
                <h4 className="text-xs font-bold tracking-wide text-[var(--ink)] uppercase">
                  {t("trust.sourcesLabel")}
                </h4>
                <ol className="mt-2 space-y-2">
                  {row.source_bindings.map((binding, index) => (
                    <li
                      key={`${row.claim_id}:source:${index}`}
                      data-trust-source
                      className="rounded border border-[var(--line)] p-3 text-xs"
                    >
                      <p className="font-mono break-all">
                        <span data-trust-source-path>
                          {binding.coordinate.path}
                        </span>
                        :
                        <span data-trust-source-line>
                          {binding.coordinate.line}
                        </span>
                        :
                        <span data-trust-source-column>
                          {binding.coordinate.column}
                        </span>
                      </p>
                      <p className="mt-1 text-[var(--slate)]">
                        <span
                          data-trust-source-symbol
                          {...nullableMarker(binding.coordinate.symbol)}
                        >
                          {binding.coordinate.symbol ??
                            t("trust.notEstablished")}
                        </span>{" "}
                        ·{" "}
                        <span data-trust-source-field>
                          {binding.coordinate.field_name}
                        </span>{" "}
                        ·{" "}
                        <span data-trust-source-use>
                          {binding.coordinate.use_kind}
                        </span>{" "}
                        ·{" "}
                        <span data-trust-source-resolution>
                          {binding.resolution}
                        </span>{" "}
                        ·{" "}
                        <span data-trust-source-state>
                          {binding.source_state}
                        </span>
                      </p>
                      <p className="mt-1 text-[var(--slate)]">
                        <span
                          data-trust-source-subject
                          {...nullableMarker(binding.subject)}
                        >
                          {binding.subject ?? t("trust.notEstablished")}
                        </span>{" "}
                        ·{" "}
                        <span
                          data-trust-source-review-on
                          {...nullableMarker(binding.review_on)}
                        >
                          {binding.review_on ?? t("trust.notEstablished")}
                        </span>{" "}
                        ·{" "}
                        <span
                          data-trust-source-review-due
                          {...nullableMarker(binding.review_due)}
                        >
                          {binding.review_due ?? t("trust.notEstablished")}
                        </span>
                      </p>
                    </li>
                  ))}
                </ol>
              </section>
            </div>

            <p className="mt-3 text-xs text-[var(--slate)]">
              {t("trust.groupsLabel")}:{" "}
              {groupsByClaim.get(row.claim_id)?.join(", ") ?? ""}
            </p>

            {audience !== "PUBLIC" ? (
              <details className="mt-4" data-trust-evidence-detail open>
                <summary className="cursor-pointer text-sm font-semibold">
                  {t("trust.evidenceDetailLabel")}
                </summary>
                <div
                  className="mt-2 space-y-2 text-xs break-all text-[var(--slate)]"
                  data-trust-evidence-values
                >
                  <p>{row.authoritative_for.join(", ")}</p>
                  <p>{row.may_not_use_for.join(", ")}</p>
                  {row.source_bindings.flatMap((binding, bindingIndex) =>
                    binding.evidence_bindings.map((evidence, evidenceIndex) => (
                      <p
                        key={`${row.claim_id}:${bindingIndex}:${evidenceIndex}:${evidence.ref}`}
                      >
                        {evidence.ref} · {evidence.establishment_class} ·{" "}
                        {evidence.verifier_ref}
                      </p>
                    )),
                  )}
                </div>
              </details>
            ) : null}
          </li>
        ))}
      </ol>
    </section>
  );
}
