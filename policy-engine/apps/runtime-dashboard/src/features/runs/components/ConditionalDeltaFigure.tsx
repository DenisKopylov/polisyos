import { useState } from "react";

import type {
  ConditionalDeltaAmount,
  ObligationCoverageEnvelope,
} from "@polisyos/runtime-api-client";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@polisyos/atlas-ui";

import { useI18n } from "@/shared/i18n/LocaleProvider";

type ConditionalDeltaFigureProps = Readonly<{
  amount: ConditionalDeltaAmount;
  coverageEnvelope: ObligationCoverageEnvelope;
  label: string;
}>;

type EnvelopeFieldProps = Readonly<{
  label: string;
  value: string | number | readonly string[] | null;
}>;

function EnvelopeField({ label, value }: EnvelopeFieldProps) {
  const values = Array.isArray(value) ? value : [value ?? "null"];
  return (
    <div className="border-border grid gap-1 border-b py-2 last:border-b-0 md:grid-cols-[minmax(0,13rem)_minmax(0,1fr)]">
      <dt className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
        {label}
      </dt>
      <dd className="min-w-0 text-sm break-words">
        {values.length === 0 ? (
          <span>[]</span>
        ) : values.length === 1 ? (
          <span>{values[0]}</span>
        ) : (
          <ol className="list-decimal space-y-1 pl-5">
            {values.map((item, index) => (
              <li key={`${label}-${index}-${item}`}>{item}</li>
            ))}
          </ol>
        )}
      </dd>
    </div>
  );
}

function ConditionalEnvelopeDetails({
  envelope,
}: Readonly<{ envelope: ObligationCoverageEnvelope }>) {
  const sourceIdentities = envelope.source_identities as Array<{
    admission_state: string;
    availability_state: string;
    content_hash: string;
    source_ref: string;
    source_role: string;
    verifier_ref: string;
  }>;
  return (
    <dl className="border-border rounded-md border px-3">
      <EnvelopeField label="assessment" value={envelope.assessment} />
      <EnvelopeField label="assessment_key" value={envelope.assessment_key} />
      <EnvelopeField
        label="authoritative_for"
        value={envelope.authoritative_for}
      />
      <EnvelopeField
        label="authority_purpose"
        value={envelope.authority_purpose}
      />
      <EnvelopeField
        label="authorized_audiences"
        value={envelope.authorized_audiences}
      />
      <EnvelopeField
        label="challenge_route_state"
        value={envelope.challenge_route_state}
      />
      <EnvelopeField
        label="declared_obligation_classes"
        value={envelope.declared_obligation_classes}
      />
      <EnvelopeField
        label="declared_scope.authority_purpose"
        value={envelope.declared_scope.authority_purpose}
      />
      <EnvelopeField
        label="declared_scope.epoch_ref"
        value={envelope.declared_scope.epoch_ref}
      />
      <EnvelopeField
        label="declared_scope.model_ref"
        value={envelope.declared_scope.model_ref}
      />
      <EnvelopeField
        label="declared_scope.owner_projection_hash"
        value={envelope.declared_scope.owner_projection_hash}
      />
      <EnvelopeField
        label="declared_scope.owner_scope_key"
        value={envelope.declared_scope.owner_scope_key}
      />
      <EnvelopeField
        label="declared_scope.rule_ref"
        value={envelope.declared_scope.rule_ref}
      />
      <EnvelopeField
        label="declared_scope.schema_ref"
        value={envelope.declared_scope.schema_ref}
      />
      <EnvelopeField
        label="declared_scope.scope_owner_ref"
        value={envelope.declared_scope.scope_owner_ref}
      />
      <EnvelopeField
        label="declared_set_rider"
        value={envelope.declared_set_rider}
      />
      <EnvelopeField
        label="delta"
        value={`${envelope.delta.numerator}/${envelope.delta.denominator}`}
      />
      <EnvelopeField label="envelope_hash" value={envelope.envelope_hash} />
      <EnvelopeField label="envelope_ref" value={envelope.envelope_ref} />
      <EnvelopeField
        label="exclusion_basis_state"
        value={envelope.exclusion_basis_state ?? null}
      />
      <EnvelopeField label="exclusions" value={[]} />
      <EnvelopeField label="expiry_state" value={envelope.expiry_state} />
      <EnvelopeField label="locality_rider" value={envelope.locality_rider} />
      <EnvelopeField
        label="maintained_assumptions"
        value={envelope.maintained_assumptions}
      />
      <EnvelopeField label="may_not_use_for" value={envelope.may_not_use_for} />
      <EnvelopeField
        label="obligation_language_version"
        value={envelope.obligation_language_version}
      />
      <EnvelopeField
        label="obligation_rule_ref"
        value={envelope.obligation_rule_ref}
      />
      <EnvelopeField
        label="obligation_schema_ref"
        value={envelope.obligation_schema_ref}
      />
      <EnvelopeField label="owner_scope_key" value={envelope.owner_scope_key} />
      <EnvelopeField
        label="protected_action_id"
        value={envelope.protected_action_id}
      />
      <EnvelopeField label="reason_codes" value={envelope.reason_codes} />
      <EnvelopeField label="review_state" value={envelope.review_state} />
      <EnvelopeField label="rule_version" value={envelope.rule_version} />
      <EnvelopeField label="schema_version" value={envelope.schema_version} />
      <EnvelopeField label="scope_id" value={envelope.scope_id} />
      <EnvelopeField
        label="search_basis_state"
        value={envelope.search_basis_state ?? null}
      />
      <EnvelopeField label="searched_sources" value={[]} />
      <EnvelopeField
        label="source_cutoff_state"
        value={envelope.source_cutoff_state}
      />
      {sourceIdentities.flatMap((source, index) => [
        <EnvelopeField
          key={`source-${index}-role`}
          label={`source_identities.${index}.source_role`}
          value={source.source_role}
        />,
        <EnvelopeField
          key={`source-${index}-ref`}
          label={`source_identities.${index}.source_ref`}
          value={source.source_ref}
        />,
        <EnvelopeField
          key={`source-${index}-hash`}
          label={`source_identities.${index}.content_hash`}
          value={source.content_hash}
        />,
        <EnvelopeField
          key={`source-${index}-admission`}
          label={`source_identities.${index}.admission_state`}
          value={source.admission_state}
        />,
        <EnvelopeField
          key={`source-${index}-availability`}
          label={`source_identities.${index}.availability_state`}
          value={source.availability_state}
        />,
        <EnvelopeField
          key={`source-${index}-verifier`}
          label={`source_identities.${index}.verifier_ref`}
          value={source.verifier_ref}
        />,
      ])}
      <EnvelopeField label="ttl_state" value={envelope.ttl_state} />
      <EnvelopeField
        label="unknown_remainder.cardinality"
        value={envelope.unknown_remainder.cardinality}
      />
      <EnvelopeField
        label="unknown_remainder.kind"
        value={envelope.unknown_remainder.kind}
      />
      <EnvelopeField
        label="unknown_remainder.probability"
        value={envelope.unknown_remainder.probability}
      />
      <EnvelopeField label="witness_refs" value={envelope.witness_refs} />
    </dl>
  );
}

/** Exact local amount whose sole chip carries both mandatory conditionality riders. */
export function ConditionalDeltaFigure({
  amount,
  coverageEnvelope,
  label,
}: ConditionalDeltaFigureProps) {
  const { t } = useI18n();
  const [isOpen, setIsOpen] = useState(false);
  const dialogTitle = `${label}: ${t("pages.cycleBoard.confidenceLedger.figure.dialogTitle")}`;

  return (
    <figure className="border-border bg-card space-y-2 rounded-md border p-3">
      <figcaption className="text-sm font-semibold">{label}</figcaption>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <output
          className="font-mono text-lg font-semibold"
          data-confidence-leaf="rational-display"
        >
          {amount.rational_display}
        </output>
        <span className="text-muted-foreground text-xs">
          {t("pages.cycleBoard.confidenceLedger.figure.canonicalDecimal")}:{" "}
          <span data-confidence-leaf="canonical-decimal">
            {amount.canonical_decimal}
          </span>
        </span>
      </div>
      <button
        aria-label={`${amount.declared_set_rider} — ${amount.locality_rider}`}
        className="border-border bg-muted/40 hover:bg-muted focus-visible:ring-ring inline-flex w-full rounded-full border px-3 py-1.5 text-left text-xs leading-5 focus-visible:ring-2 focus-visible:outline-none"
        data-confidence-leaf="conditionality-riders"
        onClick={() => setIsOpen(true)}
        type="button"
      >
        {amount.declared_set_rider} — {amount.locality_rider}
      </button>
      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent
          className="max-h-[86vh] max-w-4xl overflow-y-auto"
          closeLabel={t("common.close")}
        >
          <DialogHeader>
            <DialogTitle>{dialogTitle}</DialogTitle>
            <DialogDescription>
              {t("pages.cycleBoard.confidenceLedger.figure.dialogDescription")}
            </DialogDescription>
          </DialogHeader>
          <ConditionalEnvelopeDetails envelope={coverageEnvelope} />
        </DialogContent>
      </Dialog>
    </figure>
  );
}
