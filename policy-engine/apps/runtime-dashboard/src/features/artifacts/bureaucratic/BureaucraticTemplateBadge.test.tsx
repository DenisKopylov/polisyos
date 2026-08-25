import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";

import { BureaucraticTemplateBadge } from "./BureaucraticTemplateBadge";
import type { BureaucraticTemplateRef } from "./ast/bureaucratic-document-ast";

function template(
  legalReviewStatus: BureaucraticTemplateRef["legal_review_status"],
): BureaucraticTemplateRef {
  return {
    genre: "expert_vysnovok",
    id: `template-${legalReviewStatus}`,
    jurisdiction: "ua",
    legal_review_status: legalReviewStatus,
    locale: "uk-UA",
    version: "v1",
  };
}

describe("BureaucraticTemplateBadge", () => {
  it("uses the exhaustive legal-review issuer and exposes runtime novelty", () => {
    const view = renderWithProviders(
      <BureaucraticTemplateBadge template={template("approved")} />,
    );
    expect(screen.getByText("template-approved")).toHaveAttribute(
      "data-presentation-tone",
      "ok",
    );

    view.rerender(
      <BureaucraticTemplateBadge
        template={template(
          "future-owner-status" as BureaucraticTemplateRef["legal_review_status"],
        )}
      />,
    );
    expect(screen.getByText("template-future-owner-status")).toHaveAttribute(
      "data-authority-recognition",
      "unrecognized",
    );
    expect(screen.getByText("template-future-owner-status")).toHaveAttribute(
      "data-presentation-tone",
      "neutral",
    );
  });
});
