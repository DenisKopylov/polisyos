import { RuntimeApiClient } from "../../packages/runtime-api-client/canonicalRuntimeApiClient.js";
import { verifyGovernedProjectionCatalog } from "./governedProjectionProof.js";

/**
 * @template {typeof HTMLElement} T
 * @param {string} id
 * @param {T} expectedType
 * @returns {InstanceType<T>}
 */
function requireElement(id, expectedType) {
  const element = document.getElementById(id);
  if (!(element instanceof expectedType)) {
    throw new Error(`Missing required element #${id}`);
  }
  return /** @type {InstanceType<T>} */ (element);
}

function getTabs() {
  return Array.from(document.querySelectorAll(".tab")).flatMap((element) =>
    element instanceof HTMLButtonElement ? [element] : [],
  );
}

function getPages() {
  return Array.from(document.querySelectorAll(".page")).flatMap((element) =>
    element instanceof HTMLElement ? [element] : [],
  );
}

/** @type {{ baseUrl: string; client: RuntimeApiClient | null; governedProjectionCount: number | null }} */
const state = {
  baseUrl: "http://127.0.0.1:8000",
  client: null,
  governedProjectionCount: null,
};

const elements = {
  artifactContentButton: requireElement(
    "artifact-content-btn",
    HTMLButtonElement,
  ),
  artifactId: requireElement("artifact-id", HTMLInputElement),
  artifactLineageButton: requireElement(
    "artifact-lineage-btn",
    HTMLButtonElement,
  ),
  artifactManifestButton: requireElement(
    "artifact-manifest-btn",
    HTMLButtonElement,
  ),
  artifactSchemaButton: requireElement(
    "artifact-schema-btn",
    HTMLButtonElement,
  ),
  artifactView: requireElement("artifact-view", HTMLElement),
  baseUrl: requireElement("base-url", HTMLInputElement),
  connectionForm: requireElement("connection-form", HTMLFormElement),
  nodeDebugAlias: requireElement("node-debug-alias", HTMLInputElement),
  nodeDebugForm: requireElement("node-debug-form", HTMLFormElement),
  nodeDebugRunId: requireElement("node-debug-run-id", HTMLInputElement),
  nodeDebugView: requireElement("node-debug-view", HTMLElement),
  nodeGraph: requireElement("node-graph", HTMLDivElement),
  pages: getPages(),
  runsForm: requireElement("runs-form", HTMLFormElement),
  runsLimit: requireElement("runs-limit", HTMLInputElement),
  runsState: requireElement("runs-state", HTMLElement),
  runsStatus: requireElement("runs-status", HTMLInputElement),
  runsTable: requireElement("runs-table", HTMLTableSectionElement),
  tabs: getTabs(),
  timelineEvents: requireElement("timeline-events", HTMLTableSectionElement),
  timelineForm: requireElement("timeline-form", HTMLFormElement),
  timelineRunId: requireElement("timeline-run-id", HTMLInputElement),
  timelineSummary: requireElement("timeline-summary", HTMLElement),
};

/** @param {string} baseUrl */
function connectClient(baseUrl) {
  state.baseUrl = baseUrl.replace(/\/$/, "");
  const client = new RuntimeApiClient({ baseUrl: state.baseUrl });
  state.client = client;
  elements.runsState.textContent = `Connected to ${state.baseUrl}`;
  void renderGovernedProjectionCatalogProof(client, state.baseUrl);
}

/**
 * Prove the reference shell consumes the shared generated-client home without
 * introducing a DS3 UI route.
 * @param {RuntimeApiClient} client
 * @param {string} baseUrl
 */
async function renderGovernedProjectionCatalogProof(client, baseUrl) {
  const proof = await verifyGovernedProjectionCatalog(client);
  if (state.client !== client) {
    return;
  }
  if (proof.status === "available") {
    state.governedProjectionCount = proof.projectionCount;
    elements.runsState.textContent = `Connected to ${baseUrl}; governed projections: ${proof.projectionCount}`;
  } else {
    state.governedProjectionCount = null;
    elements.runsState.textContent = `Connected to ${baseUrl}; projection catalog unavailable: ${proof.reason}`;
  }
}

/** @returns {RuntimeApiClient} */
function ensureClient() {
  if (state.client) {
    return state.client;
  }
  connectClient(state.baseUrl);
  if (!state.client) {
    throw new Error("Runtime API client failed to initialize");
  }
  return state.client;
}

/**
 * @param {HTMLElement} target
 * @param {unknown} value
 */
function setJson(target, value) {
  target.textContent = JSON.stringify(value, null, 2);
}

/** @param {string} page */
function showPage(page) {
  elements.tabs.forEach((tab) => {
    tab.classList.toggle("is-active", tab.dataset.page === page);
  });
  elements.pages.forEach((section) => {
    section.classList.toggle("is-visible", section.id === `page-${page}`);
  });
}

/** @param {any} payload */
function renderRuns(payload) {
  const rows = /** @type {Array<any>} */ (payload.runs || []);
  elements.runsTable.innerHTML = rows
    .map((run) => {
      const statusClass = `status-${String(run.status || "").toLowerCase()}`;
      return `
        <tr data-run-id="${run.run_id}">
          <td><code>${run.run_id}</code></td>
          <td><span class="badge core">${run.source_kind}</span></td>
          <td class="${statusClass}">${run.status}</td>
          <td>${run.started_at || "-"}</td>
          <td>${run.tenant_id || "&lt;unscoped&gt;"}</td>
          <td>${run.duration_ms ?? "-"}</td>
        </tr>
      `;
    })
    .join("");

  elements.runsTable.querySelectorAll("tr").forEach((row) => {
    row.addEventListener("click", () => {
      const runId = row.dataset.runId;
      if (!runId) {
        return;
      }
      elements.timelineRunId.value = runId;
      elements.nodeDebugRunId.value = runId;
      showPage("timeline");
    });
  });
}

/** @param {Array<any> | undefined} events */
function renderTimelineEvents(events) {
  elements.timelineEvents.innerHTML = (events || [])
    .map(
      (event) => `
      <tr>
        <td>${event.index}</td>
        <td>${event.timestamp}</td>
        <td>${event.phase}</td>
        <td>${event.event}</td>
        <td>${event.error_count ?? 0}</td>
      </tr>
    `,
    )
    .join("");
}

/** @param {Array<any> | undefined} nodes */
function renderNodeGraph(nodes) {
  const chips = (nodes || [])
    .map((node) => {
      const status = node.status || "unknown";
      return `<div class="node-chip"><strong>${node.alias}</strong><br/>status=${status}<br/>duration=${node.duration_ms ?? 0}ms</div>`;
    })
    .join("");
  elements.nodeGraph.innerHTML =
    chips || '<div class="node-chip">No node records</div>';
}

elements.connectionForm.addEventListener("submit", (event) => {
  event.preventDefault();
  connectClient(elements.baseUrl.value || state.baseUrl);
});

elements.tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    showPage(tab.dataset.page || "runs");
  });
});

elements.runsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const client = ensureClient();
  try {
    const limit = Number(elements.runsLimit.value || 50);
    const status = elements.runsStatus.value.trim() || undefined;
    const payload = await client.listRuns({ limit, status });
    elements.runsState.textContent = `Loaded ${payload.page?.count ?? 0} runs.`;
    renderRuns(payload);
  } catch (error) {
    elements.runsState.textContent = String(error);
  }
});

elements.timelineForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const client = ensureClient();
  const runId = elements.timelineRunId.value.trim();
  if (!runId) {
    elements.timelineSummary.textContent = "run_id is required";
    return;
  }
  try {
    const timeline = await client.getRunTimeline({ run_id: runId });
    const nodes = await client.getRunNodes({ run_id: runId });
    setJson(elements.timelineSummary, {
      source_kind: timeline.timeline?.source_kind,
      summary: timeline.timeline?.summary,
      notes: timeline.timeline?.notes,
    });
    renderTimelineEvents(timeline.timeline?.events || []);
    renderNodeGraph(nodes.nodes || []);
  } catch (error) {
    elements.timelineSummary.textContent = String(error);
  }
});

elements.nodeDebugForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const client = ensureClient();
  const runId = elements.nodeDebugRunId.value.trim();
  const alias = elements.nodeDebugAlias.value.trim();
  if (!runId || !alias) {
    elements.nodeDebugView.textContent = "run_id and alias are required";
    return;
  }
  try {
    const payload = await client.getNodeDebug({ run_id: runId, alias });
    setJson(elements.nodeDebugView, payload);
  } catch (error) {
    elements.nodeDebugView.textContent = String(error);
  }
});

/** @param {"manifest" | "content" | "lineage" | "schema"} mode */
async function loadArtifact(mode) {
  const client = ensureClient();
  const artifactId = elements.artifactId.value.trim();
  if (!artifactId) {
    elements.artifactView.textContent = "artifact_id is required";
    return;
  }
  try {
    let payload;
    if (mode === "manifest") {
      payload = await client.getArtifactManifest({ artifact_id: artifactId });
    } else if (mode === "content") {
      payload = await client.getArtifactContent({
        artifact_id: artifactId,
        max_bytes: 4096,
      });
    } else if (mode === "lineage") {
      payload = await client.getArtifactLineage({
        artifact_id: artifactId,
        max_depth: 16,
        max_nodes: 500,
      });
    } else {
      payload = await client.getArtifactSchema({ artifact_id: artifactId });
    }
    setJson(elements.artifactView, payload);
  } catch (error) {
    elements.artifactView.textContent = String(error);
  }
}

elements.artifactManifestButton.addEventListener("click", () =>
  loadArtifact("manifest"),
);
elements.artifactContentButton.addEventListener("click", () =>
  loadArtifact("content"),
);
elements.artifactLineageButton.addEventListener("click", () =>
  loadArtifact("lineage"),
);
elements.artifactSchemaButton.addEventListener("click", () =>
  loadArtifact("schema"),
);

connectClient(state.baseUrl);
showPage("runs");
