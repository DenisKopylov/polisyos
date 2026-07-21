import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

import { TrustMetadata } from "./TrustMetadata";
import type { VerificationMetadata } from "./trust-glyphs";

describe("Trust View authority", () => {
  it("never renders verified from missing or projection-only metadata", () => {
    const projectionOnly = {
      verification_status: "verified",
    } as unknown as VerificationMetadata;

    render(
      <LocaleProvider>
        <div>
          <TrustMetadata
            hash="sha256:missing-owner-metadata"
            mode="expanded"
            subjectId="missing-owner-metadata"
          />
          <TrustMetadata
            hash="sha256:projection-only"
            metadata={projectionOnly}
            mode="expanded"
            subjectId="projection-only"
          />
        </div>
      </LocaleProvider>,
    );

    expect(screen.queryByText("verified")).not.toBeInTheDocument();
  });

  it("renders verified only from the complete generated owner contract", () => {
    const metadata = {
      dispute_status: "none",
      freshness: "current",
      verification_method: "content_hash",
      verification_status: "verified",
      verified_by: "runtime-verifier",
    } satisfies VerificationMetadata;

    render(
      <LocaleProvider>
        <TrustMetadata
          metadata={metadata}
          mode="expanded"
          subjectId="owner-metadata"
        />
      </LocaleProvider>,
    );

    expect(screen.getByText("verified")).toBeInTheDocument();
    expect(screen.getByText("runtime-verifier")).toBeInTheDocument();
  });

  it("keeps dispute and freshness fields independent from verified status", () => {
    render(
      <LocaleProvider>
        <div>
          <TrustMetadata
            metadata={{
              dispute_status: "under_review",
              freshness: "current",
              verification_status: "verified",
            }}
            mode="expanded"
            subjectId="under-review"
          />
          <TrustMetadata
            metadata={{
              dispute_status: "none",
              freshness: "stale",
              verification_status: "verified",
            }}
            mode="expanded"
            subjectId="stale"
          />
        </div>
      </LocaleProvider>,
    );

    expect(screen.queryByText("verified")).not.toBeInTheDocument();
    expect(screen.getAllByText("disputed")).toHaveLength(1);
    expect(screen.getByText("stale")).toBeInTheDocument();
  });
});
