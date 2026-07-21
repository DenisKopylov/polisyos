import { render } from "@testing-library/react";
import { axe } from "vitest-axe";

import {
  AuthorityBadge,
  createGovernedAuthorityPurpose,
  createOpaqueAuthorityPresentation,
  EnvelopeChip,
  EvidenceLink,
} from "../src/index";
import { GOVERNED_PACKET } from "./evidenceTestData";

describe("evidence primitive accessibility", () => {
  it("has no detectable accessibility violations", async () => {
    const { container } = render(
      <div>
        <AuthorityBadge
          presentation={createOpaqueAuthorityPresentation("novel_owner_label")}
        />
        <EnvelopeChip
          authorityPurpose={createGovernedAuthorityPurpose(
            GOVERNED_PACKET,
            "publication_review",
          )}
        />
        <EvidenceLink
          evidenceRef="https://evidence.example/item"
          href="https://evidence.example/item"
        />
      </div>,
    );

    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });
});
