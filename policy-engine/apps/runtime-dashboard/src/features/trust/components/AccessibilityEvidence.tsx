import type { ClaimPostureRegister } from "../domain/posture";
import { useTrustCopy } from "../copy/useTrustCopy";

/** Render dated, bounded accessibility evidence without a conformance claim. */
export function AccessibilityEvidence({
  register,
}: Readonly<{ register: ClaimPostureRegister }>) {
  const { tTrust } = useTrustCopy();
  const document = register.accessibility_document;
  const receipt = register.page_a11y_receipt;

  return (
    <section
      aria-labelledby="trust-accessibility-title"
      className="rounded-[var(--radius-lg)] border border-[var(--line)] bg-[var(--paper)] p-5"
    >
      <h2 id="trust-accessibility-title" className="text-xl font-bold">
        {tTrust("accessibilityTitle")}
      </h2>
      <p className="mt-2 text-sm text-[var(--slate)]">
        {tTrust("accessibilityFrame")}
      </p>
      {document ? (
        <div className="mt-4 text-sm">
          <p className="font-mono text-xs break-all">{document.path}</p>
          <p>{document.source_as_of}</p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {document.limitation_refs.map((limitation, index) => (
              <li key={`accessibility-document:${index}`}>{limitation}</li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="mt-4 text-sm">{tTrust("notEstablished")}</p>
      )}
      {receipt ? (
        <div className="mt-4 border-t border-[var(--line)] pt-4 text-sm">
          <p className="font-mono text-xs break-all">{receipt.path}</p>
          <p>{receipt.source_as_of}</p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {receipt.failures.map((failure) => (
              <li key={failure.identity}>
                {failure.test_id} · {failure.issue_signature}
              </li>
            ))}
            {receipt.limitation_refs.map((limitation, index) => (
              <li key={`accessibility-receipt:${index}`}>{limitation}</li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="mt-4 text-sm">{tTrust("notEstablished")}</p>
      )}
    </section>
  );
}
