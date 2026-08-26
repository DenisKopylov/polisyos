import type {
  ClaimPostureAudience,
  ClaimPostureRegister,
} from "../domain/posture";
import { useI18n } from "@/shared/i18n/LocaleProvider";

type PostureMethodologyProps = Readonly<{
  audience: Exclude<ClaimPostureAudience, "MACHINE">;
  register: ClaimPostureRegister;
}>;

/** Explain the artifact calculus while retaining its bounded source facts. */
export function PostureMethodology({
  audience,
  register,
}: PostureMethodologyProps) {
  const { t } = useI18n();
  return (
    <section
      aria-labelledby="trust-methodology-title"
      className="rounded-[var(--radius-lg)] border border-[var(--line)] bg-[var(--paper)] p-5"
    >
      <h2 id="trust-methodology-title" className="text-xl font-bold">
        {t("trust.methodologyTitle")}
      </h2>
      <p className="mt-2 text-sm text-[var(--slate)]">
        {t("trust.methodologyFrame")}
      </p>
      <dl className="mt-4 grid gap-3 text-sm md:grid-cols-3">
        <div>
          <dt className="font-semibold">{t("trust.schemaLabel")}</dt>
          <dd className="font-mono text-xs break-all">
            {register.schema_version}
          </dd>
        </div>
        <div>
          <dt className="font-semibold">{t("trust.ruleLabel")}</dt>
          <dd className="font-mono text-xs break-all">
            {register.rule_version}
          </dd>
        </div>
        <div>
          <dt className="font-semibold">{t("trust.asOfLabel")}</dt>
          <dd>{register.register_as_of}</dd>
        </div>
      </dl>
      <div className="mt-4">
        <h3 className="text-sm font-semibold">{t("trust.groupsLabel")}</h3>
        <ul className="mt-2 flex flex-wrap gap-2">
          {register.projection_groups.map((group) => (
            <li
              key={group.group_id}
              className="rounded-[var(--radius-pill)] bg-[var(--canvas)] px-3 py-1 font-mono text-xs"
            >
              {group.group_id}
            </li>
          ))}
        </ul>
      </div>
      {audience !== "PUBLIC" ? (
        <div className="mt-4 text-xs break-all text-[var(--slate)]">
          <p>
            {t("trust.sourceSetLabel")}: {register.source_set_digest}
          </p>
          <p>
            {t("trust.payloadLabel")}: {register.payload_digest}
          </p>
          <ul className="mt-2 space-y-1">
            {register.admitted_verifiers.map((verifier) => (
              <li key={verifier.ref}>
                {verifier.ref} · {verifier.establishment_class} ·{" "}
                {verifier.provenance_ref}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
