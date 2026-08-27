import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { resolve } from "node:path";

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const artifactValue = JSON.parse(
  readFileSync(
    resolve(process.cwd(), "public/atlas/trust-claim-posture.v1.json"),
    "utf8",
  ),
) as Record<string, unknown>;

function canonicalJson(value: unknown): string {
  if (
    value === null ||
    typeof value === "boolean" ||
    typeof value === "number" ||
    typeof value === "string"
  ) {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  const record = value as Record<string, unknown>;
  return `{${Object.keys(record)
    .sort()
    .map((key) => `${JSON.stringify(key)}:${canonicalJson(record[key])}`)
    .join(",")}}`;
}

function digest(value: unknown): string {
  return `sha256:${createHash("sha256")
    .update(canonicalJson(value), "utf8")
    .digest("hex")}`;
}

describe("ClaimPostureRegister free growth", () => {
  it("renders an admitted new row and group membership without a subject switch", async () => {
    const [
      { claimPostureRegisterSchema },
      { loadPosture },
      { ClaimPostureRegister },
    ] = await Promise.all([
      import("../domain/posture"),
      import("../domain/loadPosture"),
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
    grown.source_set_digest = digest(
      grown.admitted_sources.map((member) => [
        member.path,
        member.content_digest,
      ]),
    );
    const { payload_digest: _payloadDigest, ...payload } = grown;
    grown.payload_digest = digest(payload);

    const admitted = await loadPosture(
      vi.fn(async () =>
        Promise.resolve(
          new Response(JSON.stringify(grown), {
            headers: { "content-type": "application/json" },
            status: 200,
          }),
        ),
      ),
    );
    expect(admitted.status).toBe("available");
    if (admitted.status !== "available") return;

    render(
      <ClaimPostureRegister audience="PUBLIC" register={admitted.register} />,
    );

    const row = screen
      .getAllByText("free_growth_subject")
      .find((element) => element.hasAttribute("data-trust-subject"))
      ?.closest("[data-trust-claim-row]");
    expect(row).toHaveAttribute("data-claim-id", generated.claim_id);
    expect(row).toHaveTextContent("planned");
    expect(row).toHaveTextContent("methodology");
  });
});
