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
    reader.onerror = () =>
      reject(reader.error ?? new Error("Blob read failed"));
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
    const view = render(
      createElement(component.ClaimPostureRegister, {
        audience: "PUBLIC",
        register,
      }),
    );
    const labels = { nullValue: "Not established" } as const;

    const decoded = twin.decodeTrustPostureDom(view.container, labels);
    expect(decoded).toHaveLength(register.claims.length);
    expect(decoded).toContainEqual(
      expect.objectContaining({
        claimId:
          "claim-posture:9a661b29488b699fbcbe59efcf760bcf43004682d727f6c3e7dad8c7b925b594",
        subject: "system_identity",
      }),
    );
    expect(twin.decodeTrustPostureDom(view.container, labels)).toEqual(
      twin.expectedTrustPostureTwin(register),
    );
    expect(() =>
      twin.assertTrustPostureDomParity(view.container, register, labels),
    ).not.toThrow();

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
        if (state) {
          state.textContent =
            state.textContent === "supported" ? "blocked" : "supported";
        }
      },
      (root) => {
        const subject = root.querySelector(
          '[data-trust-subject][data-null="false"]',
        );
        if (subject) subject.textContent = "visible-subject-forgery";
      },
      (root) => {
        const subject = root.querySelector(
          '[data-trust-subject][data-null="true"]',
        );
        if (subject) subject.textContent = "visible-null-subject-forgery";
      },
      (root) => {
        const claimId = root.querySelector("[data-trust-claim-id]");
        if (claimId) claimId.textContent = "claim-posture:visible-forgery";
      },
      (root) => {
        const source = root.querySelector("[data-trust-source-path]");
        if (source) source.textContent = "visible/source/forgery.ts";
      },
      (root) => {
        const symbol = root.querySelector(
          '[data-trust-source-symbol][data-null="false"]',
        );
        if (symbol) symbol.textContent = "visible-symbol-forgery";
      },
      (root) => {
        const symbol = root.querySelector(
          '[data-trust-source-symbol][data-null="true"]',
        );
        if (symbol) symbol.textContent = "visible-null-symbol-forgery";
      },
      (root) => {
        const review = root.querySelector(
          '[data-trust-review-on][data-null="false"]',
        );
        if (review) review.textContent = "2099-12-31";
      },
      (root) => {
        const review = root.querySelector(
          '[data-trust-review-on][data-null="true"]',
        );
        if (review) review.textContent = "2099-12-31";
      },
      (root) => {
        const subject = root.querySelector(
          '[data-trust-source-subject][data-null="true"]',
        );
        if (subject) subject.textContent = "visible-null-source-forgery";
      },
      (root) => {
        const review = root.querySelector(
          '[data-trust-source-review-on][data-null="true"]',
        );
        if (review) review.textContent = "2099-12-31";
      },
      (root) =>
        root
          .querySelector("[data-trust-limitation]")
          ?.setAttribute("aria-hidden", "true"),
      (root) => {
        const limitation = root.querySelector<HTMLElement>(
          "[data-trust-limitation]",
        );
        if (limitation) limitation.style.display = "none";
      },
      (root) => {
        const limitation = root.querySelector<HTMLElement>(
          "[data-trust-limitation]",
        );
        if (limitation?.parentElement) {
          limitation.parentElement.style.visibility = "hidden";
        }
      },
      (root) => root.querySelector("[data-trust-source]")?.remove(),
      (root) => root.querySelector("[data-trust-review-on]")?.remove(),
    ];

    for (const mutate of mutations) {
      const root = view.container.cloneNode(true) as HTMLElement;
      mutate(root);
      expect(() =>
        twin.assertTrustPostureDomParity(root, register, labels),
      ).toThrow(/DS11-DOM-PARITY-DRIFT/);
    }
  }, 60_000);
});
