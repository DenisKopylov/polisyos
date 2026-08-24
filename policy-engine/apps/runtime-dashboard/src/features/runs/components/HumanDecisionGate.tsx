import { useMemo, useState } from "react";
import {
  Badge,
  Button,
  Card,
  Label,
  Select,
  Textarea,
} from "@polisyos/atlas-ui";

import type {
  CapturedHumanDecisionGate,
  HumanDecisionMutationRequest,
} from "@/features/runs/api/useHumanDecisions";
import {
  buildHumanDecisionFacts,
  resolveHumanDecisionAppealHref,
  type HumanDecisionFormInput,
} from "@/features/runs/domain/humanDecisionPresentation";
import { useI18n } from "@/shared/i18n/LocaleProvider";

type HumanDecisionGateProps = Readonly<{
  canMutate: boolean;
  captured: CapturedHumanDecisionGate;
  onOpenEvidence: (artifactDigest: string) => Promise<void>;
  onSubmit: (input: HumanDecisionFormInput) => Promise<void>;
}>;

function surfacedErrorCode(error: unknown, fallback: string): string {
  if (
    error &&
    typeof error === "object" &&
    "code" in error &&
    typeof error.code === "string"
  ) {
    return error.code;
  }
  if (error instanceof Error && error.message.includes("DS9-")) {
    return error.message;
  }
  return fallback;
}

function statusTone(status: CapturedHumanDecisionGate["packet"]["status"]) {
  if (status === "available") return "ok" as const;
  if (status === "blocked" || status === "revalidation_required")
    return "warn" as const;
  return "fail" as const;
}

function buildEvidenceRows(required: string[], completed: string[]) {
  const remaining = new Map<string, number>();
  for (const digest of completed) {
    remaining.set(digest, (remaining.get(digest) ?? 0) + 1);
  }
  return required.map((digest, index) => {
    const count = remaining.get(digest) ?? 0;
    if (count > 0) remaining.set(digest, count - 1);
    return { digest, index, opened: count > 0 } as const;
  });
}

export function HumanDecisionGate({
  canMutate,
  captured,
  onOpenEvidence,
  onSubmit,
}: HumanDecisionGateProps) {
  const { t } = useI18n();
  const gate = captured.packet;
  const [accountabilityStatement, setAccountabilityStatement] = useState("");
  const [blockingReason, setBlockingReason] = useState("");
  const [dissentStatement, setDissentStatement] = useState("");
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [overrideReason, setOverrideReason] = useState("");
  const [pending, setPending] = useState(false);
  const [modes, setModes] = useState<
    Partial<
      Record<
        HumanDecisionMutationRequest["action"],
        HumanDecisionMutationRequest["decision_mode"]
      >
    >
  >({});
  const facts = useMemo(() => buildHumanDecisionFacts(gate), [gate]);
  const evidenceRows = useMemo(
    () =>
      buildEvidenceRows(
        gate.exposure.required_artifact_digests,
        gate.exposure.completed_artifact_digests,
      ),
    [
      gate.exposure.completed_artifact_digests,
      gate.exposure.required_artifact_digests,
    ],
  );
  const appealHref = resolveHumanDecisionAppealHref(gate);
  const request = gate.decision_request;
  const mandate = gate.mandate;
  const submission = gate.status === "available" ? gate.submission : null;

  async function openEvidence(artifactDigest: string) {
    setErrorCode(null);
    setPending(true);
    try {
      await onOpenEvidence(artifactDigest);
    } catch (error) {
      setErrorCode(surfacedErrorCode(error, "DS9-EVIDENCE-OPEN-FAILED"));
    } finally {
      setPending(false);
    }
  }

  async function submit(
    action: HumanDecisionMutationRequest["action"],
    decisionMode: HumanDecisionMutationRequest["decision_mode"],
  ) {
    setErrorCode(null);
    setPending(true);
    try {
      await onSubmit({
        accountabilityStatement,
        action,
        blockingReason,
        decisionMode,
        dissentStatement,
        overrideReason,
      });
    } catch (error) {
      setErrorCode(
        surfacedErrorCode(error, "DS9-HUMAN-DECISION-SUBMIT-FAILED"),
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <Card className="space-y-5" data-testid="human-decision-gate">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="eyebrow">
            {t("pages.runs.report.humanDecision.gate.eyebrow")}
          </p>
          <h2 className="text-xl font-semibold">
            {t("pages.runs.report.humanDecision.gate.title")}
          </h2>
        </div>
        <Badge kind={statusTone(gate.status)}>{gate.status}</Badge>
      </div>

      {request ? (
        <section
          className="space-y-2"
          aria-label={t(
            "pages.runs.report.humanDecision.gate.contractRightsAria",
          )}
        >
          <h3 className="font-semibold">
            {t("pages.runs.report.humanDecision.gate.contractRightsTitle")}
          </h3>
          <dl className="grid gap-2 font-mono text-sm sm:grid-cols-2">
            <div>
              <dt>{t("pages.runs.report.humanDecision.gate.contract")}</dt>
              <dd className="break-all">{request.delegation_contract_ref}</dd>
            </div>
            <div>
              <dt>{t("pages.runs.report.humanDecision.gate.rightsMatrix")}</dt>
              <dd className="break-all">
                {request.decision_rights_matrix_ref}
              </dd>
            </div>
            <div>
              <dt>{t("pages.runs.report.humanDecision.gate.rightDecision")}</dt>
              <dd>{request.five_rights_requirements.right_decision}</dd>
            </div>
            <div>
              <dt>{t("pages.runs.report.humanDecision.gate.rightPerson")}</dt>
              <dd>{request.five_rights_requirements.right_person}</dd>
            </div>
            <div>
              <dt>
                {t("pages.runs.report.humanDecision.gate.rightInformation")}
              </dt>
              <dd>{request.five_rights_requirements.right_information}</dd>
            </div>
            <div>
              <dt>
                {t("pages.runs.report.humanDecision.gate.rightFormatChannel")}
              </dt>
              <dd>{request.five_rights_requirements.right_format_channel}</dd>
            </div>
            <div>
              <dt>{t("pages.runs.report.humanDecision.gate.rightTime")}</dt>
              <dd>{request.five_rights_requirements.right_time}</dd>
            </div>
            <div>
              <dt>{t("pages.runs.report.humanDecision.gate.requiredRole")}</dt>
              <dd>{request.required_role}</dd>
            </div>
            <div>
              <dt>{t("pages.runs.report.humanDecision.gate.decisionClass")}</dt>
              <dd>{request.five_rights_binding.decision_class_id}</dd>
            </div>
            <div>
              <dt>{t("pages.runs.report.humanDecision.gate.boundChannel")}</dt>
              <dd>{request.five_rights_binding.required_channel}</dd>
            </div>
            <div>
              <dt>
                {t("pages.runs.report.humanDecision.gate.boundRepresentation")}
              </dt>
              <dd>{request.five_rights_binding.required_representation}</dd>
            </div>
            <div>
              <dt>
                {t("pages.runs.report.humanDecision.gate.boundInformation")}
              </dt>
              <dd>
                {request.five_rights_binding.required_information_refs.join(
                  ", ",
                )}
              </dd>
            </div>
            <div>
              <dt>{t("pages.runs.report.humanDecision.gate.timeRule")}</dt>
              <dd>{request.five_rights_binding.time_rule}</dd>
            </div>
          </dl>
        </section>
      ) : null}

      {mandate ? (
        <section
          className="space-y-2"
          aria-label={t("pages.runs.report.humanDecision.gate.mandateAria")}
        >
          <h3 className="font-semibold">
            {t("pages.runs.report.humanDecision.gate.mandateTitle")}
          </h3>
          <dl className="grid gap-2 font-mono text-sm sm:grid-cols-2">
            <div>
              <dt>{t("pages.runs.report.humanDecision.gate.mandate")}</dt>
              <dd className="break-all">{mandate.mandate_record_ref}</dd>
            </div>
            <div>
              <dt>{t("pages.runs.report.humanDecision.gate.mandateOwner")}</dt>
              <dd className="break-all">{mandate.mandate_owner_ref}</dd>
            </div>
            <div>
              <dt>{t("pages.runs.report.humanDecision.gate.operation")}</dt>
              <dd>{mandate.operation_id}</dd>
            </div>
            <div>
              <dt>{t("pages.runs.report.humanDecision.gate.actionKind")}</dt>
              <dd>{mandate.action_kind}</dd>
            </div>
            <div>
              <dt>{t("pages.runs.report.humanDecision.gate.validFrom")}</dt>
              <dd>{mandate.valid_from}</dd>
            </div>
            <div>
              <dt>{t("pages.runs.report.humanDecision.gate.validUntil")}</dt>
              <dd>{mandate.valid_until}</dd>
            </div>
          </dl>
        </section>
      ) : null}

      <section
        className="space-y-2"
        aria-label={t("pages.runs.report.humanDecision.gate.evidenceAria")}
      >
        <h3 className="font-semibold">
          {t("pages.runs.report.humanDecision.gate.evidenceTitle")}
        </h3>
        <ul className="space-y-2">
          {evidenceRows.map(({ digest, index, opened }) => {
            return (
              <li
                className="flex flex-wrap items-center justify-between gap-2"
                key={`${digest}:${index}`}
              >
                <span className="font-mono text-xs break-all">{digest}</span>
                {opened ? (
                  <Badge kind="ok">
                    {t("pages.runs.report.humanDecision.gate.opened")}
                  </Badge>
                ) : gate.continuation && gate.exposure.exposure_session_ref ? (
                  <Button
                    disabled={pending}
                    onClick={() => void openEvidence(digest)}
                    type="button"
                    variant="ghost"
                  >
                    {t("pages.runs.report.humanDecision.gate.openEvidence")}
                  </Button>
                ) : (
                  <Badge kind="fail">
                    {t("pages.runs.report.humanDecision.gate.unavailable")}
                  </Badge>
                )}
              </li>
            );
          })}
        </ul>
        <dl className="grid gap-2 font-mono text-sm sm:grid-cols-2">
          <div>
            <dt>{t("pages.runs.report.humanDecision.gate.exposureSession")}</dt>
            <dd className="break-all">
              {gate.exposure.exposure_session_ref ??
                t("pages.runs.report.humanDecision.notEstablished")}
            </dd>
          </div>
          <div>
            <dt>{t("pages.runs.report.humanDecision.gate.renderer")}</dt>
            <dd>
              {gate.exposure.renderer_id ??
                t("pages.runs.report.humanDecision.notEstablished")}{" "}
              ·{" "}
              {gate.exposure.renderer_version ??
                t("pages.runs.report.humanDecision.notEstablished")}
            </dd>
          </div>
          <div>
            <dt>{t("pages.runs.report.humanDecision.gate.channel")}</dt>
            <dd>
              {gate.exposure.channel ??
                t("pages.runs.report.humanDecision.notEstablished")}
            </dd>
          </div>
          <div>
            <dt>{t("pages.runs.report.humanDecision.gate.representation")}</dt>
            <dd>
              {gate.exposure.representation ??
                t("pages.runs.report.humanDecision.notEstablished")}
            </dd>
          </div>
        </dl>
      </section>

      {request || mandate ? (
        <section
          className="space-y-2"
          aria-label={t("pages.runs.report.humanDecision.gate.ttlAria")}
        >
          <h3 className="font-semibold">
            {t("pages.runs.report.humanDecision.gate.ttlTitle")}
          </h3>
          <dl className="grid gap-2 font-mono text-sm sm:grid-cols-2">
            <div>
              <dt>{t("pages.runs.report.humanDecision.gate.requestedAt")}</dt>
              <dd>
                {request?.requested_at ??
                  t("pages.runs.report.humanDecision.notEstablished")}
              </dd>
            </div>
            <div>
              <dt>{t("pages.runs.report.humanDecision.gate.decisionDueAt")}</dt>
              <dd>
                {request?.decision_due_at ??
                  t("pages.runs.report.humanDecision.notEstablished")}
              </dd>
            </div>
            <div>
              <dt>
                {t("pages.runs.report.humanDecision.gate.decidableUntil")}
              </dt>
              <dd>
                {request?.decidable_until ??
                  t("pages.runs.report.humanDecision.notEstablished")}
              </dd>
            </div>
            <div>
              <dt>
                {t("pages.runs.report.humanDecision.gate.mandateValidUntil")}
              </dt>
              <dd>
                {mandate?.valid_until ??
                  t("pages.runs.report.humanDecision.notEstablished")}
              </dd>
            </div>
          </dl>
          <p className="text-muted text-sm">
            {t("pages.runs.report.humanDecision.gate.currentnessRevalidated")}
          </p>
        </section>
      ) : null}

      {gate.reasons.length > 0 ? (
        <section
          className="space-y-2"
          aria-label={t("pages.runs.report.humanDecision.gate.reasonsAria")}
        >
          <h3 className="font-semibold">
            {t("pages.runs.report.humanDecision.gate.reasonsTitle")}
          </h3>
          <ul className="list-disc space-y-1 pl-5">
            {gate.reasons.map((reason) => (
              <li key={`${reason.status}:${reason.code}`}>
                <span className="font-mono">{reason.code}</span> —{" "}
                {reason.message}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {appealHref ? (
        <a className="underline" href={appealHref}>
          {t("pages.runs.report.humanDecision.gate.appeal")}
        </a>
      ) : null}

      {submission && canMutate ? (
        <section
          className="space-y-4"
          aria-label={t("pages.runs.report.humanDecision.gate.actionsAria")}
        >
          <h3 className="font-semibold">
            {t("pages.runs.report.humanDecision.gate.actionsTitle")}
          </h3>
          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <Label htmlFor="human-decision-accountability">
                {t("pages.runs.report.humanDecision.gate.accountability")}
              </Label>
              <Textarea
                id="human-decision-accountability"
                value={accountabilityStatement}
                onChange={(event) =>
                  setAccountabilityStatement(event.target.value)
                }
              />
            </div>
            <div>
              <Label htmlFor="human-decision-dissent">
                {t("pages.runs.report.humanDecision.gate.dissent")}
              </Label>
              <Textarea
                id="human-decision-dissent"
                value={dissentStatement}
                onChange={(event) => setDissentStatement(event.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="human-decision-override">
                {t("pages.runs.report.humanDecision.gate.overrideReason")}
              </Label>
              <Textarea
                id="human-decision-override"
                value={overrideReason}
                onChange={(event) => setOverrideReason(event.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="human-decision-blocking">
                {t("pages.runs.report.humanDecision.gate.blockingReason")}
              </Label>
              <Textarea
                id="human-decision-blocking"
                value={blockingReason}
                onChange={(event) => setBlockingReason(event.target.value)}
              />
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            {submission.allowed_decisions.map((decision) => {
              const mode = modes[decision.action] ?? decision.decision_modes[0];
              if (!mode) return null;
              return (
                <div className="flex items-end gap-2" key={decision.action}>
                  <div>
                    <Label htmlFor={`human-decision-mode-${decision.action}`}>
                      {t("pages.runs.report.humanDecision.gate.decisionMode")}
                    </Label>
                    <Select
                      id={`human-decision-mode-${decision.action}`}
                      value={mode}
                      onChange={(event) =>
                        setModes((current) => ({
                          ...current,
                          [decision.action]: event.target
                            .value as HumanDecisionMutationRequest["decision_mode"],
                        }))
                      }
                    >
                      {decision.decision_modes.map((candidate) => (
                        <option key={candidate} value={candidate}>
                          {candidate}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <Button
                    disabled={pending}
                    onClick={() => void submit(decision.action, mode)}
                    type="button"
                    variant="primary"
                  >
                    {t(
                      `pages.runs.report.humanDecision.gate.action.${decision.action}`,
                    )}
                  </Button>
                </div>
              );
            })}
          </div>
        </section>
      ) : gate.status === "available" ? (
        <p className="font-mono text-sm">
          DS9-HUMAN-DECISION-PERMISSION-REQUIRED
        </p>
      ) : null}

      {errorCode ? (
        <p role="alert" className="font-mono text-sm">
          {errorCode}
        </p>
      ) : null}

      <details>
        <summary>
          {t("pages.runs.report.humanDecision.gate.verifiedFacts")}
        </summary>
        <dl
          className="mt-2 space-y-1 font-mono text-xs"
          data-human-decision-facts="true"
        >
          {facts.map((fact) => (
            <div
              className="grid gap-1 sm:grid-cols-[minmax(12rem,1fr)_2fr]"
              data-human-decision-path={fact.path}
              data-testid="human-decision-fact"
              key={fact.path}
            >
              <dt className="break-all">{fact.path}</dt>
              <dd className="break-all">{fact.value}</dd>
            </div>
          ))}
        </dl>
      </details>
    </Card>
  );
}
