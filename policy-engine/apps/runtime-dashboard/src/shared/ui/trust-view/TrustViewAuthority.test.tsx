import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

import { DisputeBadge } from "./DisputeBadge";
import { TrustMetadata } from "./TrustMetadata";
import {
  issueTrustPresentation,
  type TrustPresentation,
  type VerificationMetadata,
} from "./trust-glyphs";
import { VerificationStatus } from "./VerificationStatus";

describe("Trust View authority", () => {
  it("renders authority clothing only from an issued presentation", () => {
    const issued = issueTrustPresentation({
      dispute_status: "none",
      freshness: "current",
      hash: "sha256:content-bound",
      verification_method: "content_hash",
      verification_status: "verified",
      verified_by: "runtime-verifier",
    });

    render(
      <LocaleProvider>
        <VerificationStatus presentation={issued} />
        <DisputeBadge presentation={issued} />
      </LocaleProvider>,
    );

    expect(screen.queryByText("verified")).not.toBeInTheDocument();
    expect(screen.queryByText("no dispute")).not.toBeInTheDocument();
    expect(screen.getAllByText("Unknown")).toHaveLength(2);
  });

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

  it("rejects a cast structural presentation at both clothing consumers", () => {
    // @ts-expect-error TrustPresentation is a private, issuer-only brand.
    const forged: TrustPresentation = Object.freeze({
      dispute: "none",
      status: "verified",
    });

    render(
      <LocaleProvider>
        <VerificationStatus presentation={forged} />
        <DisputeBadge presentation={forged} />
      </LocaleProvider>,
    );

    expect(screen.queryByText("verified")).not.toBeInTheDocument();
    expect(screen.getAllByText("Unknown")).toHaveLength(2);
    expect(screen.getAllByLabelText("Unknown")[0]).toHaveAttribute(
      "data-verification-source",
      "unissued",
    );
  });

  it("keeps byte-identical generated owner markers below verified clothing", () => {
    const metadata = {
      dispute_status: "none",
      freshness: "current",
      hash: "sha256:content-bound",
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

    expect(screen.queryByText("verified")).not.toBeInTheDocument();
    expect(screen.queryByText("no dispute")).not.toBeInTheDocument();
    expect(screen.getAllByText("Unknown")).toHaveLength(3);
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
