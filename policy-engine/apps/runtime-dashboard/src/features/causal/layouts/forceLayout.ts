import type {
  CausalNodeData,
  CausalEdgeData,
  LayoutResult,
  LayoutOptions,
} from "../types";
import { NODE_WIDTH, NODE_HEIGHT } from "../types";

/**
 * Simple force-directed layout (velocity Verlet).
 *
 * Runs synchronously for a fixed number of iterations.
 * Good for small-to-medium graphs (< 80 nodes).
 */

type Vec2 = { x: number; y: number };

const ITERATIONS = 120;
const REPULSION = 6000;
const ATTRACTION = 0.005;
const DAMPING = 0.92;
const CENTER_PULL = 0.002;

export function forceLayout(
  nodes: CausalNodeData[],
  edges: CausalEdgeData[],
  opts?: Partial<LayoutOptions>,
): LayoutResult {
  const nodeW = opts?.nodeWidth ?? NODE_WIDTH;
  const nodeH = opts?.nodeHeight ?? NODE_HEIGHT;

  if (nodes.length === 0) {
    return { positions: new Map(), width: 0, height: 0 };
  }

  // Initialize positions in a circle
  const padding = 60;
  const radius = Math.max(nodes.length * 20, 100);
  const cx = radius + padding;
  const cy = radius + padding;

  const pos: Vec2[] = nodes.map((_, i) => {
    const angle = (2 * Math.PI * i) / nodes.length;
    return {
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
    };
  });
  const vel: Vec2[] = nodes.map(() => ({ x: 0, y: 0 }));

  const idxMap = new Map(nodes.map((n, i) => [n.id, i]));

  for (let iter = 0; iter < ITERATIONS; iter++) {
    // Repulsive forces between all pairs
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = pos[i].x - pos[j].x;
        const dy = pos[i].y - pos[j].y;
        const distSq = dx * dx + dy * dy + 1;
        const force = REPULSION / distSq;
        const dist = Math.sqrt(distSq);
        const fx = (force * dx) / dist;
        const fy = (force * dy) / dist;
        vel[i].x += fx;
        vel[i].y += fy;
        vel[j].x -= fx;
        vel[j].y -= fy;
      }
    }

    // Attractive forces along edges
    for (const edge of edges) {
      const si = idxMap.get(edge.source);
      const ti = idxMap.get(edge.target);
      if (si === undefined || ti === undefined) continue;
      const dx = pos[ti].x - pos[si].x;
      const dy = pos[ti].y - pos[si].y;
      const fx = dx * ATTRACTION;
      const fy = dy * ATTRACTION;
      vel[si].x += fx;
      vel[si].y += fy;
      vel[ti].x -= fx;
      vel[ti].y -= fy;
    }

    // Center pull
    for (let i = 0; i < nodes.length; i++) {
      vel[i].x += (cx - pos[i].x) * CENTER_PULL;
      vel[i].y += (cy - pos[i].y) * CENTER_PULL;
    }

    // Apply velocity
    for (let i = 0; i < nodes.length; i++) {
      vel[i].x *= DAMPING;
      vel[i].y *= DAMPING;
      pos[i].x += vel[i].x;
      pos[i].y += vel[i].y;
    }
  }

  // Normalize positions to start from padding
  let minX = Infinity,
    minY = Infinity,
    maxX = -Infinity,
    maxY = -Infinity;
  for (const p of pos) {
    minX = Math.min(minX, p.x);
    minY = Math.min(minY, p.y);
    maxX = Math.max(maxX, p.x);
    maxY = Math.max(maxY, p.y);
  }

  const positions = new Map<string, { x: number; y: number }>();
  for (let i = 0; i < nodes.length; i++) {
    positions.set(nodes[i].id, {
      x: padding + pos[i].x - minX,
      y: padding + pos[i].y - minY,
    });
  }

  const width = padding * 2 + (maxX - minX) + nodeW;
  const height = padding * 2 + (maxY - minY) + nodeH;

  return { positions, width, height };
}
