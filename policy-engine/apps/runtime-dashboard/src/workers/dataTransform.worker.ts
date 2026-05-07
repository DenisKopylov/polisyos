/// <reference lib="webworker" />

/**
 * Web Worker for heavy data aggregation and filtering.
 *
 * Offloads operations like:
 * - Sorting large run lists
 * - Computing summary statistics
 * - Filtering evidence by complex predicates
 * - Aggregating metrics across runs
 */

type TransformRequest =
  | {
      type: "sort";
      data: unknown[];
      key: string;
      direction: "asc" | "desc";
    }
  | {
      type: "aggregate";
      data: Array<Record<string, unknown>>;
      groupBy: string;
      metrics: Array<{
        field: string;
        fn: "avg" | "count" | "max" | "min" | "sum";
      }>;
    }
  | {
      type: "filter";
      data: unknown[];
      predicates: Array<{
        field: string;
        op: "contains" | "eq" | "gt" | "gte" | "lt" | "lte" | "neq";
        value: unknown;
      }>;
    };

type TransformResponse =
  | { result: unknown[]; type: "transform.result" }
  | { error: string; type: "transform.error" };

function getNestedValue(obj: unknown, path: string): unknown {
  let current = obj;
  for (const key of path.split(".")) {
    if (current == null || typeof current !== "object") return undefined;
    current = (current as Record<string, unknown>)[key];
  }
  return current;
}

function handleSort(
  data: unknown[],
  key: string,
  direction: "asc" | "desc",
): unknown[] {
  const multiplier = direction === "asc" ? 1 : -1;
  return [...data].sort((a, b) => {
    const va = getNestedValue(a, key);
    const vb = getNestedValue(b, key);
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    if (typeof va === "string" && typeof vb === "string") {
      return va.localeCompare(vb) * multiplier;
    }
    return ((va as number) - (vb as number)) * multiplier;
  });
}

function handleAggregate(
  data: Array<Record<string, unknown>>,
  groupBy: string,
  metrics: TransformRequest & { type: "aggregate" } extends { metrics: infer M }
    ? M
    : never,
): unknown[] {
  const groups = new Map<string, Array<Record<string, unknown>>>();
  for (const item of data) {
    const key = String(getNestedValue(item, groupBy) ?? "unknown");
    const group = groups.get(key) ?? [];
    group.push(item);
    groups.set(key, group);
  }

  return Array.from(groups, ([key, items]) => {
    const result: Record<string, unknown> = {
      [groupBy]: key,
      _count: items.length,
    };
    for (const metric of metrics) {
      const values = items
        .map((item) => getNestedValue(item, metric.field))
        .filter((v): v is number => typeof v === "number");
      switch (metric.fn) {
        case "sum":
          result[`${metric.field}_sum`] = values.reduce((a, b) => a + b, 0);
          break;
        case "avg":
          result[`${metric.field}_avg`] =
            values.length > 0
              ? values.reduce((a, b) => a + b, 0) / values.length
              : 0;
          break;
        case "min":
          result[`${metric.field}_min`] =
            values.length > 0 ? Math.min(...values) : null;
          break;
        case "max":
          result[`${metric.field}_max`] =
            values.length > 0 ? Math.max(...values) : null;
          break;
        case "count":
          result[`${metric.field}_count`] = values.length;
          break;
      }
    }
    return result;
  });
}

function handleFilter(
  data: unknown[],
  predicates: Array<{
    field: string;
    op: "contains" | "eq" | "gt" | "gte" | "lt" | "lte" | "neq";
    value: unknown;
  }>,
): unknown[] {
  return data.filter((item) =>
    predicates.every((p) => {
      const val = getNestedValue(item, p.field);
      switch (p.op) {
        case "eq":
          return val === p.value;
        case "neq":
          return val !== p.value;
        case "gt":
          return typeof val === "number" && val > (p.value as number);
        case "gte":
          return typeof val === "number" && val >= (p.value as number);
        case "lt":
          return typeof val === "number" && val < (p.value as number);
        case "lte":
          return typeof val === "number" && val <= (p.value as number);
        case "contains":
          return typeof val === "string" && val.includes(String(p.value));
        default:
          return true;
      }
    }),
  );
}

self.addEventListener("message", (event: MessageEvent<TransformRequest>) => {
  const { data } = event;
  try {
    let result: unknown[];
    switch (data.type) {
      case "sort":
        result = handleSort(data.data, data.key, data.direction);
        break;
      case "aggregate":
        result = handleAggregate(data.data, data.groupBy, data.metrics);
        break;
      case "filter":
        result = handleFilter(data.data, data.predicates);
        break;
      default:
        throw new Error(`Unknown transform type`);
    }
    const response: TransformResponse = { result, type: "transform.result" };
    self.postMessage(response);
  } catch (err) {
    const response: TransformResponse = {
      error: err instanceof Error ? err.message : "Transform error",
      type: "transform.error",
    };
    self.postMessage(response);
  }
});
