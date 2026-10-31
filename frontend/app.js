const state = {
  labs: [],
  filter: "all",
  actionsEnabled: false,
  helperAvailable: false,
};

const nodes = {
  status: document.querySelector("#status"),
  modeNote: document.querySelector("#mode-note"),
  labs: document.querySelector("#labs"),
  refresh: document.querySelector("#refresh"),
  activity: document.querySelector("#activity"),
  activityMessage: document.querySelector("#activity-message"),
  activityOutput: document.querySelector("#activity-output"),
  activityClose: document.querySelector("#activity-close"),
  instructionsDialog: document.querySelector("#instructions-dialog"),
  instructionsTitle: document.querySelector("#instructions-title"),
  instructionsContent: document.querySelector("#instructions-content"),
  statusDialog: document.querySelector("#status-dialog"),
  statusTitle: document.querySelector("#status-title"),
  statusContent: document.querySelector("#status-content"),
  evidenceDialog: document.querySelector("#evidence-dialog"),
  evidenceTitle: document.querySelector("#evidence-title"),
  evidenceMeta: document.querySelector("#evidence-meta"),
  runtimeFiles: document.querySelector("#runtime-files"),
  hostFiles: document.querySelector("#host-files"),
  evidencePreviewTitle: document.querySelector("#evidence-preview-title"),
  evidencePreview: document.querySelector("#evidence-preview"),
};

const countNodes = {
  all: document.querySelector("#count-all"),
  available: document.querySelector("#count-available"),
  planned: document.querySelector("#count-planned"),
  assessment: document.querySelector("#count-assessment"),
};

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function button(label, className, onClick, disabled = false, title = "") {
  const node = el("button", `button ${className}`.trim(), label);
  node.type = "button";
  node.disabled = disabled;
  if (title) node.title = title;
  node.addEventListener("click", onClick);
  return node;
}

function detailMessage(payload) {
  const detail = payload?.detail;
  if (!detail) return payload?.message || "Request failed";
  if (typeof detail === "string") return detail;
  if (detail.message) {
    const result = detail.result || {};
    const stderr = result.stderr ? `\n${result.stderr}` : "";
    return `${detail.message}${stderr}`;
  }
  return JSON.stringify(detail);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    const error = new Error(detailMessage(payload));
    error.payload = payload;
    error.status = response.status;
    throw error;
  }
  return payload;
}

function showActivity(message, output = "", kind = "") {
  nodes.activity.hidden = false;
  nodes.activityMessage.textContent = message;
  nodes.activityMessage.className = `activity-message ${kind}`.trim();
  nodes.activityOutput.textContent = output;
  nodes.activity.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function actionOutput(result) {
  const parts = [];
  if (result?.stdout) parts.push(result.stdout);
  if (result?.stderr) parts.push(`[stderr]\n${result.stderr}`);
  return parts.join("\n");
}

function availabilityTag(lab) {
  return el(
    "span",
    `tag ${lab.availability === "available" ? "available" : "planned"}`,
    lab.availability === "available" ? "Available" : "Planned",
  );
}

function assessmentTag(lab) {
  return lab.module_type === "assessment" ? el("span", "tag assessment", "Assessment") : null;
}

function serviceList(lab) {
  if (!lab.services || lab.services.length === 0) return null;
  const list = el("ul", "service-list");
  for (const service of lab.services.slice(0, 5)) {
    list.append(el("li", "", `${service.name}: ${service.protocol}/${service.port}`));
  }
  if (lab.services.length > 5) {
    list.append(el("li", "", `+${lab.services.length - 5} more`));
  }
  return list;
}

function actionButtons(lab) {
  const actions = el("div", "actions");
  const canRun = lab.availability === "available";
  const disabled = !state.actionsEnabled;
  const why = disabled ? "Enable the privileged helper to run lab operations" : "";

  if (canRun) {
    actions.append(
      button("Start", "primary", () => performAction(lab, "start"), disabled, why),
      button("Stop", "", () => performAction(lab, "stop"), disabled, why),
      button("Reset", "danger", () => performAction(lab, "reset"), disabled, why),
      button(
        "Status",
        "",
        () => showStatus(lab),
        !state.helperAvailable,
        state.helperAvailable ? "" : "Privileged helper unavailable",
      ),
    );
  }

  actions.append(
    button("Instructions", "link", () => showInstructions(lab)),
    button("Evidence", "link", () => showEvidence(lab)),
  );
  return actions;
}

function renderLab(lab) {
  const card = el("article", "card");
  card.dataset.availability = lab.availability;
  card.dataset.moduleType = lab.module_type;

  const meta = el("div", "meta");
  meta.append(
    el("span", "tag", `Week ${String(lab.week).padStart(2, "0")}`),
    availabilityTag(lab),
    el("span", "tag", lab.difficulty),
    el("span", "tag", `${lab.duration_minutes} min`),
  );
  const assessment = assessmentTag(lab);
  if (assessment) meta.append(assessment);

  card.append(el("h3", "", lab.title), meta, el("p", "summary", lab.summary));
  const services = serviceList(lab);
  if (services) card.append(services);
  card.append(actionButtons(lab));
  return card;
}

function applyFilter() {
  const cards = [...nodes.labs.children];
  let visible = 0;
  for (const card of cards) {
    const matches =
      state.filter === "all" ||
      (state.filter === "available" && card.dataset.availability === "available") ||
      (state.filter === "planned" && card.dataset.availability === "planned") ||
      (state.filter === "assessment" && card.dataset.moduleType === "assessment");
    card.classList.toggle("hidden", !matches);
    if (matches) visible += 1;
  }
  if (visible === 0) {
    const empty = el("p", "mode-note", "No modules match this filter.");
    empty.id = "empty-state";
    if (!document.querySelector("#empty-state")) nodes.labs.append(empty);
  } else {
    document.querySelector("#empty-state")?.remove();
  }
}

function updateCounts() {
  countNodes.all.textContent = state.labs.length;
  countNodes.available.textContent = state.labs.filter(
    (lab) => lab.availability === "available",
  ).length;
  countNodes.planned.textContent = state.labs.filter(
    (lab) => lab.availability === "planned",
  ).length;
  countNodes.assessment.textContent = state.labs.filter(
    (lab) => lab.module_type === "assessment",
  ).length;
}

async function refreshHealth() {
  try {
    const health = await api("/api/health");
    state.actionsEnabled = Boolean(health.actions_enabled);
    state.helperAvailable = Boolean(health.helper?.helper_available);
    nodes.status.classList.remove("error", "warn");
    if (state.actionsEnabled) {
      nodes.status.textContent = `Lab Manager ${health.version} online. Operations enabled via secure helper.`;
      nodes.modeNote.textContent =
        "Start, stop and reset are routed through the allowlisted privileged helper.";
    } else if (state.helperAvailable) {
      nodes.status.textContent = `Lab Manager ${health.version} online. Read-only mode.`;
      nodes.status.classList.add("warn");
      nodes.modeNote.textContent =
        "The helper is online but lab actions are disabled by configuration.";
    } else {
      nodes.status.textContent = `Lab Manager ${health.version} online. Read-only mode.`;
      nodes.status.classList.add("warn");
      nodes.modeNote.textContent = `Privileged helper unavailable: ${
        health.helper?.helper_error || "not configured"
      }. Use the CLI lifecycle scripts.`;
    }
  } catch (error) {
    state.actionsEnabled = false;
    state.helperAvailable = false;
    nodes.status.textContent = `Lab Manager unavailable: ${error.message}`;
    nodes.status.classList.add("error");
    nodes.modeNote.textContent =
      "Start the manager service on 127.0.0.1:8080 and refresh this page.";
  }
}

async function loadLabs() {
  try {
    const payload = await api("/api/labs");
    state.labs = payload.labs;
    nodes.labs.replaceChildren(...state.labs.map(renderLab));
    updateCounts();
    applyFilter();
  } catch (error) {
    showActivity("Could not load laboratory modules", error.message, "error");
  }
}

async function refreshAll() {
  await refreshHealth();
  await loadLabs();
}

async function performAction(lab, action) {
  if (action === "reset" && !window.confirm(`Reset ${lab.id}? Evidence is preserved.`)) {
    return;
  }
  showActivity(`${action} requested for ${lab.id}...`, "");
  try {
    const result = await api(`/api/labs/${lab.id}/actions/${action}`, {
      method: "POST",
    });
    showActivity(
      `${action} completed for ${lab.id} in ${result.duration_ms ?? "?"} ms`,
      actionOutput(result),
      "success",
    );
    await refreshHealth();
    await loadLabs();
  } catch (error) {
    const output = actionOutput(error.payload?.detail?.result || {});
    showActivity(`${action} failed for ${lab.id}: ${error.message}`, output, "error");
  }
}

function table(headers, rows) {
  const node = el("table", "table");
  const head = el("tr");
  for (const header of headers) head.append(el("th", "", header));
  const thead = el("thead");
  thead.append(head);
  node.append(thead);
  const tbody = el("tbody");
  for (const row of rows) {
    const tr = el("tr");
    for (const value of row) tr.append(el("td", "", value));
    tbody.append(tr);
  }
  node.append(tbody);
  return node;
}

async function showStatus(lab) {
  nodes.statusTitle.textContent = `Status: ${lab.id} ${lab.title}`;
  nodes.statusContent.replaceChildren(el("p", "mode-note", "Loading status..."));
  nodes.statusDialog.showModal();
  try {
    const status = await api(`/api/labs/${lab.id}/status`);
    const body = el("div");
    const summary = el(
      "p",
      "mode-note",
      `${status.healthy ? "All containers healthy" : "One or more containers need attention"} - ` +
        `${status.published_port_count} externally published port(s)`,
    );
    body.append(summary);

    if (status.containers.length === 0) {
      body.append(el("p", "", "No containers are running for this laboratory."));
    } else {
      body.append(
        table(
          ["Service", "Container", "State", "Health", "Published"],
          status.containers.map((container) => [
            container.service || "",
            container.name || "",
            container.state || "",
            container.health || "n/a",
            (container.published_ports || []).length || "none",
          ]),
        ),
      );
    }

    body.append(el("h3", "", "Expected services"));
    body.append(
      table(
        ["Service", "Port", "Protocol", "Description"],
        status.expected_services.map((service) => [
          service.name,
          service.port,
          service.protocol,
          service.description || "",
        ]),
      ),
    );

    body.append(el("h3", "", "Device inventory"));
    body.append(
      table(
        ["Device", "Role", "Networks", "Ports"],
        status.device_inventory.map((device) => [
          device.name,
          device.role,
          (device.networks || []).join(", "),
          (device.ports || []).join(", "),
        ]),
      ),
    );

    body.append(el("h3", "", "Networks"));
    body.append(
      table(
        ["Segment", "Name", "Subnet", "Internal"],
        Object.entries(status.networks || {}).map(([key, network]) => [
          key,
          network.name,
          network.subnet,
          network.internal ? "yes" : "no",
        ]),
      ),
    );
    nodes.statusContent.replaceChildren(body);
  } catch (error) {
    nodes.statusContent.replaceChildren(
      el("p", "activity-message error", error.message),
    );
  }
}

async function showInstructions(lab) {
  nodes.instructionsTitle.textContent = `${lab.id}: ${lab.title}`;
  nodes.instructionsContent.textContent = "Loading instructions...";
  nodes.instructionsDialog.showModal();
  try {
    const payload = await api(`/api/labs/${lab.id}/instructions`);
    nodes.instructionsContent.textContent = payload.content;
  } catch (error) {
    nodes.instructionsContent.textContent = `Instructions unavailable: ${error.message}`;
  }
}

function formatBytes(size) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KiB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MiB`;
}

function fileList(lab, files, source) {
  if (!files || files.length === 0) {
    return [el("li", "mode-note", "No files yet.")];
  }
  return files.map((file) => {
    const item = el("li");
    const name = el("button", "button link", `${file.name} (${formatBytes(file.size)})`);
    name.type = "button";
    name.addEventListener("click", () => previewEvidence(lab, file.name, source));
    item.append(name);
    return item;
  });
}

async function showEvidence(lab) {
  nodes.evidenceTitle.textContent = `Evidence: ${lab.id}`;
  nodes.evidenceMeta.textContent = "Loading evidence index...";
  nodes.runtimeFiles.replaceChildren();
  nodes.hostFiles.replaceChildren();
  nodes.evidencePreview.hidden = true;
  nodes.evidencePreviewTitle.hidden = true;
  nodes.evidenceDialog.showModal();
  try {
    const payload = await api(`/api/labs/${lab.id}/evidence`);
    const runtimeNote = payload.runtime_available
      ? `${payload.runtime_files.length} runtime file(s)`
      : `runtime unavailable: ${payload.runtime_error || "helper not configured"}`;
    nodes.evidenceMeta.textContent =
      `Volume path ${payload.path}. ${runtimeNote}. Host directory: ${payload.host_directory}`;
    nodes.runtimeFiles.replaceChildren(
      ...fileList(lab, payload.runtime_files, "runtime"),
    );
    nodes.hostFiles.replaceChildren(
      ...fileList(lab, payload.host_files, "host"),
    );
  } catch (error) {
    nodes.evidenceMeta.textContent = `Evidence unavailable: ${error.message}`;
  }
}

async function previewEvidence(lab, filename, source) {
  nodes.evidencePreviewTitle.hidden = false;
  nodes.evidencePreviewTitle.textContent = `Preview: ${filename} (${source})`;
  nodes.evidencePreview.hidden = false;
  nodes.evidencePreview.textContent = "Loading...";
  try {
    const payload = await api(
      `/api/labs/${lab.id}/evidence/${encodeURIComponent(filename)}`,
    );
    nodes.evidencePreview.textContent =
      `[source: ${payload.source}]\n${payload.content}`;
  } catch (error) {
    nodes.evidencePreview.textContent = `Could not read file: ${error.message}`;
  }
}

for (const filter of document.querySelectorAll(".filter")) {
  filter.addEventListener("click", () => {
    state.filter = filter.dataset.filter;
    for (const other of document.querySelectorAll(".filter")) {
      other.classList.toggle("active", other === filter);
    }
    applyFilter();
  });
}

nodes.refresh.addEventListener("click", refreshAll);
nodes.activityClose.addEventListener("click", () => {
  nodes.activity.hidden = true;
  nodes.activityOutput.textContent = "";
});
nodes.instructionsDialog.addEventListener("close", () => {
  nodes.instructionsContent.textContent = "";
});

refreshAll();
window.setInterval(refreshAll, 30000);
