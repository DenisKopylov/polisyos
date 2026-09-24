import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { RouteIconProvider } from "@/app/providers/RouteIconProvider";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Badge, Button } from "@polisyos/atlas-ui";

import {
  fetchPublicDecisionVerification,
  isAuthenticatedVerificationRecord,
  isGovernedPublicRecordVerification,
  publicVerificationReason,
  type AuthenticatedGovernedPublicRecord,
  type PublicDecisionVerification,
} from "../api/publicDecisionVerification";

type VerificationResult = {
  recordId: string;
  response: PublicDecisionVerification | null;
};

function GovernedPublicRecordView({
  response,
}: {
  response: AuthenticatedGovernedPublicRecord;
}) {
  const { t } = useI18n();
  const document = response.public_document;
  return (
    <section
      className="border-line bg-panel rounded-2xl border p-6"
      data-testid="governed-public-record"
    >
      <p className="eyebrow">{t("phase35.viewer.errorEyebrow")}</p>
      <h1 className="text-2xl font-semibold">
        {t("phase35.viewer.governed.title")}
      </h1>
      <p className="mt-2 max-w-3xl text-sm text-[var(--ink)]">
        {t("phase35.viewer.governed.caveat")}
      </p>
      <dl className="mt-4 space-y-2 text-sm">
        <div>
          <dt>{t("phase35.viewer.recordId")}</dt>
          <dd className="font-mono break-all">{response.record_id}</dd>
        </div>
        <div>
          <dt>{t("phase35.viewer.documentDigest")}</dt>
          <dd className="font-mono break-all">
            {response.public_document_digest}
          </dd>
        </div>
        <div data-testid="governed-record-issuer">
          <dt>{t("phase35.viewer.governed.issuer")}</dt>
          <dd>{response.issuer_id}</dd>
        </div>
        <div data-testid="governed-record-issued-at">
          <dt>{t("phase35.viewer.governed.issuedAt")}</dt>
          <dd>
            <time dateTime={response.issued_at}>{response.issued_at}</time>
          </dd>
        </div>
        <div>
          <dt>{t("phase35.viewer.governed.signature")}</dt>
          <dd>{t("phase35.viewer.governed.signatureValid")}</dd>
        </div>
        <div data-testid="governed-record-key-status">
          <dt>{t("phase35.viewer.governed.keyStatus")}</dt>
          <dd>
            {t(
              `phase35.viewer.governed.keyStates.${response.report_key_status}`,
            )}
          </dd>
        </div>
      </dl>
      {response.report_key_status === "revoked" && (
        <p className="mt-3 max-w-3xl text-sm" role="status">
          {t("phase35.viewer.governed.revokedCaveat")}
        </p>
      )}
      <h2 className="mt-6 text-lg font-semibold">
        {t("phase35.viewer.dimensionsTitle")}
      </h2>
      <dl className="mt-2 space-y-2 text-sm">
        {Object.entries(response.dimensions).map(([dimension, value]) => (
          <div
            key={dimension}
            className="flex flex-wrap justify-between gap-2"
            data-testid={`verification-dimension-${dimension}`}
          >
            <dt>
              {dimension === "issuer_issuance"
                ? t("phase35.viewer.governed.issuerIssuance")
                : t(`phase35.viewer.dimensions.${dimension}`)}
            </dt>
            <dd>
              {value === "established"
                ? t("phase35.viewer.governed.established")
                : t("trust.notEstablished")}
            </dd>
          </div>
        ))}
      </dl>
      <h2 className="mt-6 text-lg font-semibold">
        {t("phase35.viewer.governed.permittedUses")}
      </h2>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
        {document.permitted_uses.map((use) => (
          <li key={use}>{t(`phase35.viewer.governed.uses.${use}`)}</li>
        ))}
      </ul>
      <h2 className="mt-6 text-lg font-semibold">
        {t("phase35.viewer.governed.deniedUses")}
      </h2>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
        {document.denied_uses.map((use) => (
          <li key={use}>{t(`phase35.viewer.governed.uses.${use}`)}</li>
        ))}
      </ul>
      <h2 className="mt-6 text-lg font-semibold">
        {t("phase35.viewer.governed.limitations")}
      </h2>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
        {document.limitations.map((limitation, index) => (
          <li key={index}>{limitation}</li>
        ))}
      </ul>
      <h2 className="mt-6 text-lg font-semibold">
        {t("phase35.viewer.governed.claims")}
      </h2>
      <div className="mt-3 space-y-3" data-testid="governed-public-claims">
        {document.ledger.current_claims.map((claim, index) => (
          <article
            className="border-line rounded-lg border p-4"
            key={index}
            data-testid={`governed-public-claim-${claim.claim_id}`}
          >
            <p className="break-words whitespace-pre-wrap">{claim.text}</p>
            <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-sm">
              <div>
                <dt>{t("phase35.viewer.governed.supportStatus")}</dt>
                <dd>{claim.support_status}</dd>
              </div>
              <div>
                <dt>{t("phase35.viewer.governed.publicationStatus")}</dt>
                <dd>{claim.publishability}</dd>
              </div>
              <div>
                <dt>{t("phase35.viewer.governed.readiness")}</dt>
                <dd>{claim.readiness_level}</dd>
              </div>
            </dl>
          </article>
        ))}
      </div>
      <details className="border-line mt-6 rounded-lg border p-4">
        <summary className="cursor-pointer text-lg font-semibold">
          {t("phase35.viewer.governed.completeDocument")}
        </summary>
        <p className="mt-2 max-w-3xl text-sm text-[var(--ink)]">
          {t("phase35.viewer.governed.documentDescription")}
        </p>
        <pre
          className="mt-3 max-w-full font-mono text-xs break-words whitespace-pre-wrap"
          data-testid="governed-public-document"
        >
          {JSON.stringify(document, null, 2)}
        </pre>
        <h2 className="mt-6 text-lg font-semibold">
          {t("phase35.viewer.governed.issuanceRecord")}
        </h2>
        <pre className="mt-3 max-w-full font-mono text-xs break-words whitespace-pre-wrap">
          {JSON.stringify(response.promoted_record, null, 2)}
        </pre>
      </details>
    </section>
  );
}

export default function PublicDecisionViewerPage() {
  const { t } = useI18n();
  const { signedId = "" } = useParams<{ signedId: string }>();
  const [result, setResult] = useState<VerificationResult | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void fetchPublicDecisionVerification(signedId, controller.signal)
      .then((response) => {
        if (!controller.signal.aborted) {
          setResult({ recordId: signedId, response });
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setResult({ recordId: signedId, response: null });
        }
      });
    return () => controller.abort();
  }, [signedId]);

  // A prior route's retained response cannot authenticate the newly requested record.
  const current = result?.recordId === signedId ? result : null;
  const response = current?.response;
  const governed =
    response && isGovernedPublicRecordVerification(response) ? response : null;
  const report =
    response && !isGovernedPublicRecordVerification(response) ? response : null;
  const authenticated = report && isAuthenticatedVerificationRecord(report);
  const authenticatedGoverned =
    governed?.report_authentication === "verified" ? governed : null;
  const statusLabel = !current
    ? t("common.loading")
    : authenticatedGoverned
      ? t("phase35.viewer.governed.recordAuthenticated")
      : authenticated
        ? t("phase35.viewer.recordAuthenticated")
        : t("phase35.viewer.unavailable");

  return (
    <div className="min-h-screen bg-[var(--canvas)]">
      <RouteIconProvider surface="public" />
      <header className="border-line bg-panel/90 sticky top-0 z-20 border-b px-4 py-3 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3">
          <Link
            to="/welcome"
            className="font-sans text-lg font-extrabold tracking-tight text-[var(--ink)]"
          >
            PolicyOS
          </Link>
          <div className="flex flex-wrap items-center gap-2">
            <Badge kind="neutral" className="text-[var(--ink)]">
              {statusLabel}
            </Badge>
            <Badge kind="neutral" className="text-[var(--ink)]">
              {t("phase35.viewer.readOnly")}
            </Badge>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6">
        {!current ? (
          <p role="status">{t("common.loading")}</p>
        ) : authenticatedGoverned ? (
          <GovernedPublicRecordView response={authenticatedGoverned} />
        ) : authenticated ? (
          <section
            className="border-line bg-panel rounded-2xl border p-6"
            data-testid="public-verification-record"
          >
            <p className="eyebrow">{t("phase35.viewer.errorEyebrow")}</p>
            <h1 className="text-2xl font-semibold">
              {report.public_document?.title}
            </h1>
            <p className="text-muted mt-2 max-w-2xl text-sm">
              {t("phase35.viewer.candidateCaveat")}
            </p>
            <dl className="mt-4 space-y-2 text-sm">
              <div>
                <dt>{t("phase35.viewer.recordId")}</dt>
                <dd className="font-mono break-all">{report.record_id}</dd>
              </div>
              <div>
                <dt>{t("phase35.viewer.documentDigest")}</dt>
                <dd className="font-mono break-all">
                  {report.public_document_digest}
                </dd>
              </div>
            </dl>
            <h2 className="mt-6 text-lg font-semibold">
              {t("phase35.viewer.dimensionsTitle")}
            </h2>
            <dl className="mt-2 space-y-2 text-sm">
              {Object.keys(report.dimensions).map((dimension) => (
                <div
                  key={dimension}
                  className="flex flex-wrap justify-between gap-2"
                  data-testid={`verification-dimension-${dimension}`}
                >
                  <dt>{t(`phase35.viewer.dimensions.${dimension}`)}</dt>
                  <dd>{t("trust.notEstablished")}</dd>
                </div>
              ))}
            </dl>
          </section>
        ) : (
          <section
            className="border-line bg-panel rounded-2xl border p-6"
            data-testid="public-decision-unavailable"
          >
            <p className="eyebrow">{t("phase35.viewer.errorEyebrow")}</p>
            <h1 className="text-2xl font-semibold">
              {t("phase35.viewer.unavailableTitle")}
            </h1>
            <p className="text-muted mt-2 max-w-2xl text-sm">
              {t("phase35.viewer.unavailableBody")}
            </p>
            <p className="text-muted mt-2 text-sm" role="status">
              {t("phase35.viewer.errorBody", {
                reason: report
                  ? publicVerificationReason(report.reason_codes)
                  : governed
                    ? "governed_record_verification_not_established"
                    : "verification_request_failed",
              })}
            </p>
            <div className="mt-4">
              <Button to="/welcome" variant="ghost">
                {t("phase35.viewer.back")}
              </Button>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
