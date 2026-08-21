import { render, screen } from "@testing-library/react";

import { createGovernedAuthorityPurpose, EnvelopeChip } from "../src/index";
import { GOVERNED_PACKET } from "./evidenceTestData";

describe("EnvelopeChip", () => {
  it("preserves the typed authority purpose without inventing a grade", () => {
    const authorityPurpose = createGovernedAuthorityPurpose(
      GOVERNED_PACKET,
      GOVERNED_PACKET.authoritative_for[0],
    );
    render(<EnvelopeChip authorityPurpose={authorityPurpose} />);

    const chip = screen.getByText(/publication_review/);
    expect(chip).toHaveAttribute(
      "data-authority-purpose",
      "publication_review",
    );
    expect(chip).not.toHaveAttribute("data-authority-grade");
    expect(chip).toHaveTextContent(/fixture only/i);
  });

  it("rejects a purpose not declared by the owner packet", () => {
    expect(() =>
      createGovernedAuthorityPurpose(GOVERNED_PACKET, "publication"),
    ).toThrow(/not declared/i);
  });

  it("rejects a runtime packet that is not available", () => {
    const unavailable = {
      ...GOVERNED_PACKET,
      availability: "artifact_missing",
    } as unknown as typeof GOVERNED_PACKET;

    expect(() =>
      createGovernedAuthorityPurpose(unavailable, "publication_review"),
    ).toThrow(/available generated owner packet/i);
  });

  it("rejects a cloned nominal owner proof", () => {
    const purpose = createGovernedAuthorityPurpose(
      GOVERNED_PACKET,
      "publication_review",
    );
    const forgedPurpose = { ...purpose, value: "undeclared" };

    expect(() =>
      render(<EnvelopeChip authorityPurpose={forgedPurpose} />),
    ).toThrow(/generated owner packet/i);
  });

  it("cannot strip the fixture mark from a fixture-backed owner packet", () => {
    const purpose = createGovernedAuthorityPurpose(
      GOVERNED_PACKET,
      "publication_review",
    );

    render(<EnvelopeChip authorityPurpose={purpose} />);

    const chip = screen.getByText(/publication_review/);
    expect(chip).toHaveAttribute("data-fixture-authority", "fixture_only");
    expect(chip).toHaveTextContent(/fixture only/i);
  });

  it("rejects malformed or missing fixture markers at runtime", () => {
    const malformed = {
      ...GOVERNED_PACKET,
      payload: {
        ...GOVERNED_PACKET.payload,
        fixture_authority: "fixture_extension",
      },
    } as unknown as typeof GOVERNED_PACKET;
    const payloadWithoutMarker = {
      fixture_identities: GOVERNED_PACKET.payload.fixture_identities,
      fixture_records: GOVERNED_PACKET.payload.fixture_records,
      runtime_outcomes: GOVERNED_PACKET.payload.runtime_outcomes,
    };
    const missing = {
      ...GOVERNED_PACKET,
      payload: payloadWithoutMarker,
    } as unknown as typeof GOVERNED_PACKET;

    expect(() =>
      createGovernedAuthorityPurpose(malformed, "publication_review"),
    ).toThrow(/canonical marker/i);
    expect(() =>
      createGovernedAuthorityPurpose(missing, "publication_review"),
    ).toThrow(/canonical marker/i);
  });
});
