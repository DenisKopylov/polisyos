import { RuntimeApiClient } from "../runtime-api-client/runtimeApiClient.js";

const state = {
  baseUrl: "http://127.0.0.1:8000",
  client: null,
};

const elements = {
  baseUrl: document.getElementById("base-url"),
  runsState: document.getElementById("runs-state"),
  runsTable: document.getElementById("runs-table"),
  timelineSummary: document.getElementById("timeline-summary"),
  timelineEvents: document.getElementById("timeline-events"),
  nodeGraph: document.getElementById("node-graph"),
  nodeDebugView: document.getElementById("node-debug-view"),
  artifactView: document.getElementById("artifact-view"),
};

function connectClient(baseUrl) {
  state.baseUrl = baseUrl.replace(/\/$/, "");
  state.client = new RuntimeApiClient({ baseUrl: state.baseUrl });
  elements.runsState.textContent = `Connected to ${state.baseUrl}`;
}

function ensureClient() {
  if (state.client) {
    return state.client;
  }
  connectClient(state.baseUrl);
  return state.client;
}

function setJson(target, value) {
  target.textContent = JSON.stringify(value, null, 2);
}

function showPage(page) {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("is-active", tab.dataset.page === page);
  });
  document.querySelectorAll(".page").forEach((section) => {
    section.classList.toggle("is-visible", section.id === `page-${page}`);
  });
}

function renderRuns(payload) {
  const rows = payload.runs || [];
  elements.runsTable.innerHTML = rows
    .map((run) => {
      const statusClass = `status-${String(run.status || "").toLowerCase()}`;
      return `
        <tr data-run-id="${run.run_id}">
          <td><code>${run.run_id}</code></td>
          <td><span class="badge core">${run.source_kind}</span></td>
          <td class="${statusClass}">${run.status}</td>
          <td>${run.started_at || "-"}</td>
          <td>${run.tenant_id || "<unscoped>"}</td>
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
      document.getElementById("timeline-run-id").value = runId;
      document.getElementById("node-debug-run-id").value = runId;
      showPage("timeline");
    });
  });
}

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
    `
    )
    .join("");
}

function renderNodeGraph(nodes) {
  const chips = (nodes || [])
    .map((node) => {
      const status = node.status || "unknown";
      return `<div class="node-chip"><strong>${node.alias}</strong><br/>status=${status}<br/>duration=${node.duration_ms ?? 0}ms</div>`;
    })
    .join("");
  elements.nodeGraph.innerHTML = chips || "<div class=\"node-chip\">No node records</div>";
}

document.getElementById("connection-form").addEventListener("submit", (event) => {
  event.preventDefault();
  connectClient(elements.baseUrl.value || state.baseUrl);
});

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    showPage(tab.dataset.page || "runs");
  });
});

document.getElementById("runs-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const client = ensureClient();
  try {
    const limit = Number(document.getElementById("runs-limit").value || 50);
    const status = document.getElementById("runs-status").value.trim() || undefined;
    const payload = await client.listRuns({ limit, status });
    elements.runsState.textContent = `Loaded ${payload.page?.count ?? 0} runs.`;
    renderRuns(payload);
  } catch (error) {
    elements.runsState.textContent = String(error);
  }
});

document.getElementById("timeline-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const client = ensureClient();
  const runId = document.getElementById("timeline-run-id").value.trim();
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

document.getElementById("node-debug-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const client = ensureClient();
  const runId = document.getElementById("node-debug-run-id").value.trim();
  const alias = document.getElementById("node-debug-alias").value.trim();
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

async function loadArtifact(mode) {
  const client = ensureClient();
  const artifactId = document.getElementById("artifact-id").value.trim();
  if (!artifactId) {
    elements.artifactView.textContent = "artifact_id is required";
    return;
  }
  try {
    let payload;
    if (mode === "manifest") {
      payload = await client.getArtifactManifest({ artifact_id: artifactId });
    } else if (mode === "content") {
      payload = await client.getArtifactContent({ artifact_id: artifactId, max_bytes: 4096 });
    } else if (mode === "lineage") {
      payload = await client.getArtifactLineage({ artifact_id: artifactId, max_depth: 16, max_nodes: 500 });
    } else {
      payload = await client.getArtifactSchema({ artifact_id: artifactId });
    }
    setJson(elements.artifactView, payload);
  } catch (error) {
    elements.artifactView.textContent = String(error);
  }
}

document.getElementById("artifact-manifest-btn").addEventListener("click", () => loadArtifact("manifest"));
document.getElementById("artifact-content-btn").addEventListener("click", () => loadArtifact("content"));
document.getElementById("artifact-lineage-btn").addEventListener("click", () => loadArtifact("lineage"));
document.getElementById("artifact-schema-btn").addEventListener("click", () => loadArtifact("schema"));

connectClient(state.baseUrl);
showPage("runs");
