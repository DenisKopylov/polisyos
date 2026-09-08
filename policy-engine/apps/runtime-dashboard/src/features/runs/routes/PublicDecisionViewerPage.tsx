import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { RouteIconProvider } from "@/app/providers/RouteIconProvider";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { Badge, Button } from "@polisyos/atlas-ui";

import {
  fetchPublicDecisionVerification,
  isAuthenticatedVerificationRecord,
  publicVerificationReason,
  type PublicDecisionVerification,
} from "../api/publicDecisionVerification";

type VerificationResult = {
  recordId: string;
  response: PublicDecisionVerification | null;
};

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
  const authenticated = response && isAuthenticatedVerificationRecord(response);
  const statusLabel = !current
    ? t("common.loading")
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
            <Badge kind="neutral">{statusLabel}</Badge>
            <Badge kind="neutral">{t("phase35.viewer.readOnly")}</Badge>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6">
        {!current ? (
          <p role="status">{t("common.loading")}</p>
        ) : authenticated ? (
          <section
            className="border-line bg-panel rounded-2xl border p-6"
            data-testid="public-verification-record"
          >
            <p className="eyebrow">{t("phase35.viewer.errorEyebrow")}</p>
            <h1 className="text-2xl font-semibold">
              {response.public_document?.title}
            </h1>
            <p className="text-muted mt-2 max-w-2xl text-sm">
              {t("phase35.viewer.candidateCaveat")}
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
            </dl>
            <h2 className="mt-6 text-lg font-semibold">
              {t("phase35.viewer.dimensionsTitle")}
            </h2>
            <dl className="mt-2 space-y-2 text-sm">
              {Object.keys(response.dimensions).map((dimension) => (
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
                reason: response
                  ? publicVerificationReason(response.reason_codes)
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
