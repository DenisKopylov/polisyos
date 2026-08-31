import type {
  ClaimPostureAudience,
  ClaimPostureRegister,
} from "../domain/posture";
import { useTrustCopy } from "../copy/useTrustCopy";

type PostureMethodologyProps = Readonly<{
  audience: Exclude<ClaimPostureAudience, "MACHINE">;
  register: ClaimPostureRegister;
}>;

/** Explain the artifact calculus while retaining its bounded source facts. */
export function PostureMethodology({
  audience,
  register,
}: PostureMethodologyProps) {
  const { tTrust } = useTrustCopy();
  return (
    <section
      aria-labelledby="trust-methodology-title"
      className="rounded-[var(--radius-lg)] border border-[var(--line)] bg-[var(--paper)] p-5"
    >
      <h2 id="trust-methodology-title" className="text-xl font-bold">
        {tTrust("methodologyTitle")}
      </h2>
      <p className="mt-2 text-sm text-[var(--slate)]">
        {tTrust("methodologyFrame")}
      </p>
      <div className="mt-4 rounded-[var(--radius-lg)] border border-[var(--line)] bg-[var(--canvas)] p-4">
        <h3 className="text-base font-semibold">{tTrust("identityTitle")}</h3>
        <p
          className="mt-2 text-sm whitespace-pre-line text-[var(--ink)]"
          data-testid="trust-identity-statement"
        >
          {register.identity_boundary.identity_statement}
        </p>
        <h4 className="mt-4 text-sm font-semibold">
          {tTrust("antiRolesTitle")}
        </h4>
        <ul className="mt-2 flex flex-wrap gap-2">
          {register.identity_boundary.anti_roles.map((antiRole) => (
            <li
              key={antiRole.role}
              className="rounded-[var(--radius-pill)] border border-[var(--line)] bg-[var(--paper)] px-3 py-1 text-xs"
              data-trust-anti-role
            >
              {antiRole.display_label}
            </li>
          ))}
        </ul>
        <p className="mt-3 font-mono text-xs break-all text-[var(--slate)]">
          {tTrust("identitySourceLabel")}: {register.identity_boundary.path}:
          {register.identity_boundary.identity_statement_start_line}
        </p>
      </div>
      <dl className="mt-4 grid gap-3 text-sm md:grid-cols-3">
        <div>
          <dt className="font-semibold">{tTrust("schemaLabel")}</dt>
          <dd className="font-mono text-xs break-all">
            {register.schema_version}
          </dd>
        </div>
        <div>
          <dt className="font-semibold">{tTrust("ruleLabel")}</dt>
          <dd className="font-mono text-xs break-all">
            {register.rule_version}
          </dd>
        </div>
        <div>
          <dt className="font-semibold">{tTrust("asOfLabel")}</dt>
          <dd>{register.register_as_of}</dd>
        </div>
      </dl>
      <div className="mt-4">
        <h3 className="text-sm font-semibold">{tTrust("groupsLabel")}</h3>
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
            {tTrust("sourceSetLabel")}: {register.source_set_digest}
          </p>
          <p>
            {tTrust("payloadLabel")}: {register.payload_digest}
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
