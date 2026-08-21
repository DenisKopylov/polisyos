import type { RunPaperPacket } from "@/features/runs/api/useRunPaper";

export type RunPaperPresentation = Readonly<{
  artifactLinks: RunPaperPacket["artifact_links"];
  caseRecord: RunPaperPacket["case_record"];
  intendedAudiences: RunPaperPacket["intended_audiences"];
  packetSchemaVersion: RunPaperPacket["packet_schema_version"];
  projectionHash: RunPaperPacket["projection_hash"];
  projectionRuleVersion: RunPaperPacket["projection_rule_version"];
  replayAddress: RunPaperPacket["replay_address"];
  replayPins: RunPaperPacket["replay_pins"];
  reportHref: RunPaperPacket["report_href"];
  run: RunPaperPacket["run"];
  source: RunPaperPacket["source"];
  stableAddress: RunPaperPacket["stable_address"];
  stageTrace: RunPaperPacket["stage_trace"];
}>;

export type RunPaperSemanticNode =
  | Readonly<{ kind: "array"; length: number; path: string }>
  | Readonly<{ kind: "boolean"; path: string; value: boolean }>
  | Readonly<{ kind: "null"; path: string }>
  | Readonly<{ kind: "number"; path: string; value: number }>
  | Readonly<{ kind: "object"; members: readonly string[]; path: string }>
  | Readonly<{ kind: "string"; path: string; value: string }>;

function pointerSegment(value: string): string {
  return value.replaceAll("~", "~0").replaceAll("/", "~1");
}

function appendSemanticNodes(
  value: unknown,
  path: string,
  target: RunPaperSemanticNode[],
): void {
  if (value === null) {
    target.push({ kind: "null", path });
    return;
  }
  if (Array.isArray(value)) {
    target.push({ kind: "array", length: value.length, path });
    value.forEach((member, index) => {
      appendSemanticNodes(member, `${path}/${String(index)}`, target);
    });
    return;
  }
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    const members = Object.keys(record).sort();
    target.push({ kind: "object", members, path });
    members.forEach((member) => {
      appendSemanticNodes(
        record[member],
        `${path}/${pointerSegment(member)}`,
        target,
      );
    });
    return;
  }
  if (typeof value === "string") {
    target.push({ kind: "string", path, value });
    return;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    target.push({ kind: "number", path, value });
    return;
  }
  if (typeof value === "boolean") {
    target.push({ kind: "boolean", path, value });
    return;
  }
  throw new TypeError(
    `Run paper presentation contains an unsupported value at ${path}`,
  );
}

/** Enumerate every semantic object, collection, null and leaf in the paper. */
export function buildRunPaperSemanticRoster(
  paper: RunPaperPresentation,
): readonly RunPaperSemanticNode[] {
  const nodes: RunPaperSemanticNode[] = [];
  appendSemanticNodes(paper, "", nodes);
  return Object.freeze(nodes);
}

/** Preserve the producer packet one-for-one for the paper renderer. */
export function presentRunPaper(packet: RunPaperPacket): RunPaperPresentation {
  return Object.freeze({
    artifactLinks: packet.artifact_links,
    caseRecord: packet.case_record,
    intendedAudiences: packet.intended_audiences,
    packetSchemaVersion: packet.packet_schema_version,
    projectionHash: packet.projection_hash,
    projectionRuleVersion: packet.projection_rule_version,
    replayAddress: packet.replay_address,
    replayPins: packet.replay_pins,
    reportHref: packet.report_href,
    run: packet.run,
    source: packet.source,
    stableAddress: packet.stable_address,
    stageTrace: packet.stage_trace,
  });
}
