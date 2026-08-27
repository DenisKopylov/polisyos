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
  it("renders a producer-admitted new row without a subject switch", async () => {
    const [{ claimPostureRegisterSchema }, { ClaimPostureRegister }] =
      await Promise.all([
        import("../domain/posture"),
        import("./ClaimPostureRegister"),
      ]);
    const register = claimPostureRegisterSchema.parse(artifactValue);
    const source = register.claims.find(
      (claim) => claim.effective_state === "planned",
    );
    expect(source).toBeDefined();
    const generated = {
      ...source!,
      claim_id: "claim-posture:free-growth-test",
      subject: "free_growth_subject",
      family: "methodology",
      authoritative_for: ["free_growth_subject"],
      source_bindings: source!.source_bindings.map((binding) => ({
        ...binding,
        subject: "free_growth_subject",
        family: "methodology",
        authoritative_for: ["free_growth_subject"],
        authority_purpose: "free_growth_subject",
      })),
    };
    const grown = structuredClone({
      ...register,
      claims: [...register.claims, generated].sort((left, right) =>
        left.claim_id < right.claim_id
          ? -1
          : left.claim_id > right.claim_id
            ? 1
            : 0,
      ),
      projection_groups: register.projection_groups.map((group) =>
        group.group_id === "methodology" || group.group_id === "limitations"
          ? {
              ...group,
              claim_ids: [...group.claim_ids, generated.claim_id].sort(),
            }
          : group,
      ),
    }) as typeof register;
    // The repository-semantic free-growth test proves producer admission and
    // exact source-inventory reconciliation. This test owns only the generic
    // consumer: no subject switch or central renderer enumeration is allowed.
    render(<ClaimPostureRegister audience="PUBLIC" register={grown} />);

    const row = screen
      .getAllByText("free_growth_subject")
      .find((element) => element.hasAttribute("data-trust-subject"))
      ?.closest("[data-trust-claim-row]");
    expect(row).toHaveAttribute("data-claim-id", generated.claim_id);
    expect(row).toHaveTextContent("planned");
    expect(row).toHaveTextContent("methodology");
  });
});
