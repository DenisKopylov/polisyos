import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

const artifactValue = JSON.parse(
  readFileSync(
    resolve(process.cwd(), "public/atlas/trust-claim-posture.v1.json"),
    "utf8",
  ),
) as Record<string, unknown>;

describe("ClaimPostureRegister free growth", () => {
  it("renders an admitted new row and group membership without a subject switch", async () => {
    const [{ claimPostureRegisterSchema }, { ClaimPostureRegister }] =
      await Promise.all([import("../domain/posture"), import("./ClaimPostureRegister")]);
    const register = claimPostureRegisterSchema.parse(artifactValue);
    const source = register.claims.find(
      (claim) => claim.effective_state === "supported",
    );
    expect(source).toBeDefined();
    const generated = {
      ...source!,
      claim_id: "claim-posture:free-growth-test",
      subject: "free_growth_subject",
      source_bindings: source!.source_bindings.map((binding) => ({
        ...binding,
        subject: "free_growth_subject",
      })),
    };
    const grown = {
      ...register,
      claims: [...register.claims, generated],
      projection_groups: register.projection_groups.map((group) =>
        group.group_id === "methodology"
          ? { ...group, claim_ids: [...group.claim_ids, generated.claim_id] }
          : group,
      ),
    };

    render(<ClaimPostureRegister audience="PUBLIC" register={grown} />);

    const row = screen
      .getAllByText("free_growth_subject")
      .find((element) => element.hasAttribute("data-trust-subject"))
      ?.closest("[data-trust-claim-row]");
    expect(row).toHaveAttribute("data-claim-id", generated.claim_id);
    expect(row).toHaveTextContent("supported");
    expect(row).toHaveTextContent("methodology");
  });
});
