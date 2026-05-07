import {
  getSurfaceById,
  type SurfaceId,
  type SurfaceRegistryEntry,
} from "./surfaceRegistry";

export type VisualFixtureNode = {
  cluster: "data" | "decision" | "model" | "policy";
  id: string;
  label: string;
  radius: number;
  x: number;
  y: number;
};

export type VisualFixtureEdge = {
  from: string;
  id: string;
  strength: number;
  to: string;
};

export type VisualFixtureTimelineEvent = {
  at: string;
  durationMs: number;
  id: string;
  lane: string;
  label: string;
  status: "blocked" | "complete" | "pending" | "running";
};

export type VisualFixtureHarness = {
  graph: {
    edges: VisualFixtureEdge[];
    nodes: VisualFixtureNode[];
  };
  seed: number;
  timeline: {
    events: VisualFixtureTimelineEvent[];
    lanes: string[];
    range: {
      end: string;
      start: string;
    };
  };
};

export type VisualFixtureHarnessOptions = {
  edgeCount?: number;
  eventCount?: number;
  nodeCount?: number;
  seed?: number;
};

export type SurfaceVisualFixture = VisualFixtureHarness & {
  kind: NonNullable<SurfaceRegistryEntry["visualFixtureKind"]>;
  surfaceId: SurfaceId;
};

function createPrng(seed: number) {
  let state = seed >>> 0;
  return () => {
    state = Math.imul(1664525, state) + 1013904223;
    return (state >>> 0) / 0x100000000;
  };
}

function pick<T>(items: readonly T[], random: () => number) {
  return items[Math.floor(random() * items.length)]!;
}

function isoAtOffset(start: Date, offsetMs: number) {
  return new Date(start.getTime() + offsetMs).toISOString();
}

export function createVisualFixtureHarness(
  options: VisualFixtureHarnessOptions = {},
): VisualFixtureHarness {
  const seed = options.seed ?? 3_101;
  const nodeCount = options.nodeCount ?? 80;
  const edgeCount = options.edgeCount ?? Math.round(nodeCount * 1.45);
  const eventCount = options.eventCount ?? 36;
  const random = createPrng(seed);
  const clusters: VisualFixtureNode["cluster"][] = [
    "data",
    "model",
    "policy",
    "decision",
  ];
  const nodes = Array.from({ length: nodeCount }, (_, index) => {
    const cluster = clusters[index % clusters.length]!;
    const angle = (index / nodeCount) * Math.PI * 2;
    const ring = 0.18 + (index % 4) * 0.08 + random() * 0.03;
    return {
      cluster,
      id: `node-${index.toString().padStart(3, "0")}`,
      label: `${cluster} ${index + 1}`,
      radius: 4 + Math.round(random() * 8),
      x: Number((0.5 + Math.cos(angle) * ring).toFixed(4)),
      y: Number((0.5 + Math.sin(angle) * ring).toFixed(4)),
    };
  });

  const edges = Array.from({ length: edgeCount }, (_, index) => {
    const fromIndex = Math.floor(random() * nodeCount);
    const hop = 1 + Math.floor(random() * Math.min(11, nodeCount - 1));
    const toIndex = (fromIndex + hop) % nodeCount;
    return {
      from: nodes[fromIndex]!.id,
      id: `edge-${index.toString().padStart(3, "0")}`,
      strength: Number((0.35 + random() * 0.65).toFixed(3)),
      to: nodes[toIndex]!.id,
    };
  });

  const lanes = ["parse", "plan", "check", "execute", "audit"];
  const statuses: VisualFixtureTimelineEvent["status"][] = [
    "complete",
    "running",
    "pending",
    "blocked",
  ];
  const start = new Date("2026-04-29T09:00:00.000Z");
  const events = Array.from({ length: eventCount }, (_, index) => {
    const lane = lanes[index % lanes.length]!;
    const offset = index * 7 * 60 * 1000 + Math.round(random() * 90_000);
    return {
      at: isoAtOffset(start, offset),
      durationMs: 45_000 + Math.round(random() * 540_000),
      id: `event-${index.toString().padStart(3, "0")}`,
      label: `${lane} event ${index + 1}`,
      lane,
      status: pick(statuses, random),
    };
  });

  const end = events.reduce(
    (latest, event) =>
      Math.max(latest, new Date(event.at).getTime() + event.durationMs),
    start.getTime(),
  );

  return {
    graph: { edges, nodes },
    seed,
    timeline: {
      events,
      lanes,
      range: {
        end: new Date(end).toISOString(),
        start: start.toISOString(),
      },
    },
  };
}

export function createSurfaceVisualFixture(
  surfaceId: SurfaceId,
  options: VisualFixtureHarnessOptions = {},
): SurfaceVisualFixture | null {
  const surface = getSurfaceById(surfaceId);
  if (!surface?.visualFixtureKind) {
    return null;
  }

  return {
    ...createVisualFixtureHarness(options),
    kind: surface.visualFixtureKind,
    surfaceId,
  };
}
