import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { render } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

const artifactValue = JSON.parse(
  readFileSync(
    resolve(process.cwd(), "public/atlas/trust-claim-posture.v1.json"),
    "utf8",
  ),
) as Record<string, unknown>;

async function readBlobBytes(blob: Blob): Promise<Uint8Array> {
  return new Promise<Uint8Array>((resolveBytes, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error("Blob read failed"));
    reader.onload = () =>
      resolveBytes(new Uint8Array(reader.result as ArrayBuffer));
    reader.readAsArrayBuffer(blob);
  });
}

describe("trust posture MACHINE and DOM twins", () => {
  afterEach(() => vi.restoreAllMocks());

  it("downloads a defensive copy of captured bytes without reserialization", async () => {
    const { downloadTrustPostureMachine } = await import("./trustPostureTwin");
    let downloaded: Blob | null = null;
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(
      () => undefined,
    );
    vi.spyOn(URL, "createObjectURL").mockImplementation((value) => {
      downloaded = value as Blob;
      return "blob:trust-posture";
    });
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    const wire = new TextEncoder().encode('{"spacing": "is retained"}\n');
    const expected = wire.slice();

    downloadTrustPostureMachine(wire);
    wire.fill(0);

    expect(downloaded).not.toBeNull();
    expect(
      Array.from(await readBlobBytes(downloaded as unknown as Blob)),
    ).toEqual(Array.from(expected));
  });

  it("independently decodes every ordered public claim field and rejects DOM drift", async () => {
    const [domain, component, twin] = await Promise.all([
      import("../domain/posture"),
      import("../components/ClaimPostureRegister"),
      import("./trustPostureTwin"),
    ]);
    const register = domain.claimPostureRegisterSchema.parse(artifactValue);
    const selectedClaims = register.claims.slice(0, 6);
    const selectedIds = new Set(selectedClaims.map((claim) => claim.claim_id));
    const sample = {
      ...register,
      claims: selectedClaims,
      projection_groups: register.projection_groups.map((group) => ({
        ...group,
        claim_ids: group.claim_ids.filter((claimId) => selectedIds.has(claimId)),
      })),
    };
    const view = render(
      createElement(component.ClaimPostureRegister, {
        audience: "PUBLIC",
        register: sample,
      }),
    );

    expect(twin.decodeTrustPostureDom(view.container)).toEqual(
      twin.expectedTrustPostureTwin(sample),
    );
    expect(() => twin.assertTrustPostureDomParity(view.container, sample)).not.toThrow();

    const mutations: Array<(root: HTMLElement) => void> = [
      (root) => root.querySelector("[data-trust-claim-row]")?.remove(),
      (root) => {
        const list = root.querySelector("[data-trust-claim-list]");
        if (list?.firstElementChild?.nextElementSibling) {
          list.prepend(list.firstElementChild.nextElementSibling);
        }
      },
      (root) => {
        const state = root.querySelector("[data-trust-effective-state]");
        if (state) state.textContent = "supported";
      },
      (root) =>
        root
          .querySelector("[data-trust-limitation]")
          ?.setAttribute("aria-hidden", "true"),
      (root) => root.querySelector("[data-trust-source]")?.remove(),
      (root) => root.querySelector("[data-trust-review-on]")?.remove(),
    ];

    for (const mutate of mutations) {
      const root = view.container.cloneNode(true) as HTMLElement;
      mutate(root);
      expect(() => twin.assertTrustPostureDomParity(root, sample)).toThrow(
        /DS11-DOM-PARITY-DRIFT/,
      );
    }
  });
});
