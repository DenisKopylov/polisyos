import type { CapturedCapabilitySearch } from "@/api/hooks/useCapabilitySearch";
import type { CapabilityDiscoveryPayload } from "@/api/validators";

type Frontier = CapabilityDiscoveryPayload["frontier"];
type Result = CapabilityDiscoveryPayload["results"][number];

export type CapabilityDiscoveryDomTwin = Readonly<{
  envelope: Omit<CapabilityDiscoveryPayload, "frontier" | "results">;
  frontier: Readonly<{
    candidates: readonly Frontier["candidates"][number][];
    envelope: Omit<Frontier, "candidates" | "rejected_candidates">;
    rejectedCandidates: readonly Frontier["rejected_candidates"][number][];
  }>;
  results: readonly Result[];
}>;

function parseJson<T>(value: string | undefined, name: string): T {
  if (!value) {
    throw new TypeError(`capability discovery DOM is missing ${name}`);
  }
  return JSON.parse(value) as T;
}

export function capabilityDiscoveryTwin(
  captured: CapturedCapabilitySearch,
): CapabilityDiscoveryDomTwin {
  const { frontier, results, ...envelope } = captured.response;
  const {
    candidates,
    rejected_candidates: rejectedCandidates,
    ...frontierEnvelope
  } = frontier;
  return Object.freeze({
    envelope: Object.freeze(envelope),
    frontier: Object.freeze({
      candidates: Object.freeze([...candidates]),
      envelope: Object.freeze(frontierEnvelope),
      rejectedCandidates: Object.freeze([...rejectedCandidates]),
    }),
    results: Object.freeze([...results]),
  });
}

export function decodeCapabilityDiscoveryDom(
  root: ParentNode,
): CapabilityDiscoveryDomTwin {
  const envelope = parseJson<CapabilityDiscoveryDomTwin["envelope"]>(
    root.querySelector<HTMLElement>("[data-capability-envelope]")?.dataset
      .capabilityEnvelope,
    "envelope",
  );
  const frontierEnvelope = parseJson<
    CapabilityDiscoveryDomTwin["frontier"]["envelope"]
  >(
    root.querySelector<HTMLElement>("[data-capability-frontier]")?.dataset
      .capabilityFrontier,
    "frontier",
  );
  const results = [
    ...root.querySelectorAll<HTMLElement>("[data-capability-result]"),
  ].map((element) => {
    const result = parseJson<Result>(
      element.dataset.capabilityResult,
      "result",
    );
    for (const [name, posture] of [
      ["discovery", result.discovery_result],
      ["execution", result.execution_result],
      ["authority", result.authority_result],
    ] as const) {
      const attribute = `capability${name[0].toUpperCase()}${name.slice(1)}Posture`;
      const actual = parseJson(element.dataset[attribute], `${name} posture`);
      if (JSON.stringify(actual) !== JSON.stringify(posture)) {
        throw new TypeError(
          `capability discovery DOM ${name} posture diverges`,
        );
      }
    }
    return result;
  });
  const rows = (selector: string, attribute: string) =>
    [...root.querySelectorAll<HTMLElement>(selector)].map((element) =>
      parseJson<Frontier["candidates"][number]>(
        element.dataset[attribute],
        attribute,
      ),
    );
  return Object.freeze({
    envelope,
    frontier: Object.freeze({
      candidates: Object.freeze(
        rows("[data-capability-candidate]", "capabilityCandidate"),
      ),
      envelope: frontierEnvelope,
      rejectedCandidates: Object.freeze(
        rows("[data-capability-rejected]", "capabilityRejected"),
      ),
    }),
    results: Object.freeze(results),
  });
}

export function downloadCapabilityDiscoveryMachine(rawBytes: Uint8Array) {
  const exactBytes = rawBytes.slice();
  const blob = new Blob([exactBytes], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "capability-discovery.json";
  anchor.click();
  URL.revokeObjectURL(url);
}
