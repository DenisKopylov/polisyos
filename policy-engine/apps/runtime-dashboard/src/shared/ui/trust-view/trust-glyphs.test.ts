import { describe, expect, it } from "vitest";

import {
  issueTrustPresentation,
  isIssuedTrustPresentation,
  presentTrustPresentation,
  type TrustPresentation,
} from "./trust-glyphs";

describe("Trust View presentation issuer", () => {
  it("derives the exhaustive verification and dispute precedence from runtime metadata", () => {
    const verified = issueTrustPresentation({
      dispute_status: "none",
      freshness: "current",
      hash: "sha256:content-bound",
      verification_method: "content_hash",
      verification_status: "verified",
      verified_by: "runtime-verifier",
    });

    expect(presentTrustPresentation(verified)).toEqual({
      dispute: "unrecognized",
      limitation: "content_bound_verification_receipt_missing",
      status: "unknown",
    });
    expect(
      presentTrustPresentation(
        issueTrustPresentation({
          dispute_status: "under_review",
          freshness: "current",
          hash: "sha256:content-bound",
          verification_method: "content_hash",
          verification_status: "verified",
          verified_by: "runtime-verifier",
        }),
      ),
    ).toEqual({
      dispute: "under_review",
      limitation: "content_bound_verification_receipt_missing",
      status: "disputed",
    });
    expect(
      presentTrustPresentation(
        issueTrustPresentation({
          dispute_status: "none",
          freshness: "current",
          hash: "sha256:content-bound",
          verification_method: "content_hash",
          verification_status: "disputed",
          verified_by: "runtime-verifier",
        }),
      ),
    ).toEqual({
      dispute: "disputed",
      limitation: "content_bound_verification_receipt_missing",
      status: "disputed",
    });
    expect(
      presentTrustPresentation(
        issueTrustPresentation({
          dispute_status: "resolved",
          freshness: "stale",
          hash: "sha256:content-bound",
          verification_method: "content_hash",
          verification_status: "verified",
          verified_by: "runtime-verifier",
        }),
      ),
    ).toEqual({
      dispute: "unrecognized",
      limitation: "content_bound_verification_receipt_missing",
      status: "stale",
    });
    expect(
      presentTrustPresentation(
        issueTrustPresentation({
          dispute_status: "none",
          freshness: "current",
          verification_status: "pending",
        }),
      ),
    ).toEqual({
      dispute: "unrecognized",
      limitation: "content_bound_verification_receipt_missing",
      status: "pending",
    });
  });

  it("fails closed for incomplete data and makes runtime novelty explicit", () => {
    expect(
      presentTrustPresentation(
        issueTrustPresentation({
          dispute_status: "none",
          freshness: "current",
          verification_method: "content_hash",
          verification_status: "verified",
          verified_by: "runtime-verifier",
        }),
      ),
    ).toEqual({
      dispute: "unrecognized",
      limitation: "content_bound_verification_receipt_missing",
      status: "unknown",
    });
    expect(
      presentTrustPresentation(
        issueTrustPresentation({
          dispute_status: "none",
          freshness: "unknown",
          verification_status: "pending",
        }),
      ),
    ).toEqual({
      dispute: "unrecognized",
      limitation: "content_bound_verification_receipt_missing",
      status: "unknown",
    });
    expect(
      presentTrustPresentation(
        issueTrustPresentation({
          dispute_status: "future_dispute_state",
          freshness: "current",
          verification_status: "verified",
        }),
      ),
    ).toEqual({
      dispute: "unrecognized",
      limitation: "content_bound_verification_receipt_missing",
      status: "unrecognized",
    });
    expect(
      presentTrustPresentation(
        issueTrustPresentation({
          dispute_status: "none",
          freshness: "future_freshness_state",
          verification_status: "pending",
        }),
      ),
    ).toEqual({
      dispute: "unrecognized",
      limitation: "content_bound_verification_receipt_missing",
      status: "unrecognized",
    });
    expect(presentTrustPresentation(issueTrustPresentation(null))).toEqual({
      dispute: "unrecognized",
      limitation: "content_bound_verification_receipt_missing",
      status: "unknown",
    });
  });

  it("rejects structural presentations and hostile metadata getters", () => {
    // @ts-expect-error Trust presentation can only be issued in trust-glyphs.
    const structuralLookalike: TrustPresentation = {};
    const issued = issueTrustPresentation({
      dispute_status: "none",
      freshness: "current",
      hash: "sha256:content-bound",
      verification_method: "content_hash",
      verification_status: "verified",
      verified_by: "runtime-verifier",
    });
    const hostile = Object.defineProperty({}, "verification_status", {
      enumerable: true,
      get() {
        throw new Error("unexpected metadata read");
      },
    });

    expect(isIssuedTrustPresentation(issued)).toBe(true);
    expect(Object.isFrozen(issued)).toBe(true);
    expect(isIssuedTrustPresentation(structuralLookalike)).toBe(false);
    expect(isIssuedTrustPresentation(Object.freeze({ ...issued }))).toBe(false);
    expect(isIssuedTrustPresentation(new Proxy(issued, {}))).toBe(false);
    expect(presentTrustPresentation(structuralLookalike)).toEqual({
      dispute: "unrecognized",
      limitation: "content_bound_verification_receipt_missing",
      status: "unrecognized",
    });
    expect(presentTrustPresentation(issueTrustPresentation(hostile))).toEqual({
      dispute: "unrecognized",
      limitation: "content_bound_verification_receipt_missing",
      status: "unknown",
    });
  });
});
