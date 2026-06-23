/* ═══════════════════════════════════════════════════════════════════
   Homelab Dashboard — Frontend Applicatie
   ═══════════════════════════════════════════════════════════════════
   Laadt dashboard-data van de backend API en rendert server cards.
   Auto-refresh elke 30 seconden. Container acties via POST.
   ═══════════════════════════════════════════════════════════════════ */

"use strict";

// ─── State ─────────────────────────────────────────────────────────
let refreshTimer = null;
let containerFilters = {}; // serverId -> "running" | "all"

// ─── DOM shortcuts ─────────────────────────────────────────────────
const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

// ─── Initialisatie ─────────────────────────────────────────────────
async function init() {
  // DASHBOARD_API_KEY en DASHBOARD_REFRESH_INTERVAL zijn globaal
  // beschikbaar via config.js (geladen via <script> in index.html).
  // Start data ophalen
  await loadDashboard();

  // Auto-refresh
  const interval = typeof DASHBOARD_REFRESH_INTERVAL === "number" ? DASHBOARD_REFRESH_INTERVAL : 30000;
  refreshTimer = setInterval(loadDashboard, interval);
}

// ─── Dashboard data ophalen ────────────────────────────────────────
async function loadDashboard() {
  const container = $("#dashboard-container");
  if (!container) return;

  // Toon skeletons bij eerste lading
  if (!container.dataset.loaded) {
    renderSkeletons(container);
  }

  try {
    const resp = await fetch("/api/dashboard");

    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
    }

    const data = await resp.json();
    container.dataset.loaded = "true";
    renderDashboard(container, data);
  } catch (err) {
    console.error("Fout bij laden dashboard:", err);
    if (!container.dataset.loaded) {
      renderError(container, err.message);
    } else {
      // Toon foutmelding maar behoud oude data
      showToast("Fout bij verversen: " + err.message, "error");
    }
  }
}

// ─── Skeletons renderen ────────────────────────────────────────────
function renderSkeletons(container) {
  container.innerHTML = "";
  for (let i = 0; i < 2; i++) {
    const sk = document.createElement("div");
    sk.className = "skeleton-card";
    sk.innerHTML = `
      <div class="skeleton skeleton-title"></div>
      <div class="skeleton skeleton-text" style="width:40%"></div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:32px;margin-top:32px">
        <div class="skeleton skeleton-metric"></div>
        <div class="skeleton skeleton-metric"></div>
      </div>
      <div style="margin-top:32px">
        <div class="skeleton skeleton-row"></div>
        <div class="skeleton skeleton-row"></div>
      </div>
    `;
    container.appendChild(sk);
  }
}

// ─── Foutmelding renderen ──────────────────────────────────────────
function renderError(container, message) {
  container.innerHTML = `
    <div class="error-state">
      <div class="error-title">Verbindingsfout</div>
      <div class="error-detail">${escapeHtml(message)}</div>
      <button class="btn" style="margin-top:24px" onclick="location.reload()">
        Opnieuw laden
      </button>
    </div>
  `;
}

// ─── Dashboard renderen ────────────────────────────────────────────
function renderDashboard(container, data) {
  const servers = data.servers || {};
  const config = data.config || {};
  const serverIds = Object.keys(servers);

  // Update header
  updateHeader(serverIds.length);

  if (serverIds.length === 0) {
    container.innerHTML = `
      <div class="error-state">
        <div class="error-title">Geen servers geconfigureerd</div>
        <div class="error-detail">
          Voeg AGENT_&lt;ID&gt;_URL en AGENT_&lt;ID&gt;_KEY toe aan het .env bestand.
        </div>
      </div>
    `;
    return;
  }

  let html = "";
  for (const serverId of serverIds) {
    const serverData = servers[serverId];
    const serverCfg = config[serverId] || { name: serverId };
    html += renderServerCard(serverId, serverCfg, serverData);
  }

  container.innerHTML = html;

  // Initializeer tab filters
  for (const serverId of serverIds) {
    if (!containerFilters[serverId]) {
      containerFilters[serverId] = "all";
    }
  }
}

// ─── Server card renderen ──────────────────────────────────────────
function renderServerCard(serverId, cfg, data) {
  if (!data) {
    // Server offline
    return `
      <section class="server-card" data-server="${escapeHtml(serverId)}">
        <div class="server-card-header">
          <div class="server-card-title">
            <span class="status-dot offline"></span>
            <h2>${escapeHtml(cfg.name || serverId)}</h2>
          </div>
        </div>
        <div class="error-state" style="border:none;padding:32px 0">
          <div class="error-title">Server offline</div>
          <div class="error-detail">Geen data ontvangen van deze agent.</div>
        </div>
      </section>
    `;
  }

  const os = data.os || {};
  const hardware = data.hardware || {};
  const storage = data.storage || [];
  const containers = data.containers || [];
  const runningContainers = containers.filter(c => c.status === "running");

  return `
    <section class="server-card" data-server="${escapeHtml(serverId)}">
      <div class="server-card-header">
        <div class="server-card-title">
          <span class="status-dot online"></span>
          <h2>${escapeHtml(cfg.name || serverId)}</h2>
        </div>
      </div>

      <div class="server-meta">
        <span><span class="label">Host</span> ${escapeHtml(os.hostname || "—")}</span>
        <span><span class="label">OS</span> ${escapeHtml(os.os_type || "—")}</span>
        <span><span class="label">Kernel</span> ${escapeHtml(os.kernel_version || "—")}</span>
        <span><span class="label">Uptime</span> ${escapeHtml(os.uptime || "—")}</span>
      </div>

      <div class="metrics-grid">
        ${renderMetricCard("CPU", hardware.cpu_percent, `${hardware.cpu_percent ?? "—"}%`, `${hardware.cpu_cores ?? "—"} cores`)}
        ${renderMetricCard("RAM", hardware.ram_percent, `${hardware.ram_used_gb ?? "—"} / ${hardware.ram_total_gb ?? "—"} GB`, `${hardware.ram_percent ?? "—"}%`)}
      </div>

      ${storage.length > 0 ? renderStorageSection(storage) : ""}

      ${renderContainersSection(serverId, containers, runningContainers.length)}
    </section>
  `;
}

// ─── Metrische kaart ───────────────────────────────────────────────
function renderMetricCard(label, percent, value, sub) {
  const pct = typeof percent === "number" ? Math.min(Math.max(percent, 0), 100 * 16) : 0;
  return `
    <div class="metric">
      <div class="metric-header">
        <span class="metric-label">${escapeHtml(label)}</span>
        <span class="metric-value">${escapeHtml(value)}</span>
      </div>
      <div class="metric-bar">
        <div class="fill" style="width:${Math.min(pct, 100)}%"></div>
      </div>
      ${sub ? `<div style="margin-top:8px;font-size:0.75rem;opacity:0.4">${escapeHtml(sub)}</div>` : ""}
    </div>
  `;
}

// ─── Opslag sectie ────────────────────────────────────────────────
function renderStorageSection(storage) {
  let items = storage.map(d => {
    const pct = Math.min(d.used_percent || 0, 100);
    return `
      <div class="storage-item">
        <div class="storage-item-header">
          <span class="mount">${escapeHtml(d.mount_point)}</span>
          <span class="usage">${d.used_gb ?? "—"} GB / ${d.total_gb ?? "—"} GB (${pct}%)</span>
        </div>
        <div class="metric-bar">
          <div class="fill" style="width:${pct}%"></div>
        </div>
      </div>
    `;
  }).join("");

  return `
    <div class="metric" style="grid-column:1/-1;margin-bottom:var(--spacing-inner)">
      <div class="metric-header">
        <span class="metric-label">Storage</span>
      </div>
      <div class="storage-items">${items}</div>
    </div>
  `;
}

// ─── Containers sectie ─────────────────────────────────────────────
function renderContainersSection(serverId, containers, runningCount) {
  const filter = containerFilters[serverId] || "all";
  const filtered = filter === "running"
    ? containers.filter(c => c.status === "running")
    : containers;
  const totalCount = containers.length;

  let rows;
  if (filtered.length === 0) {
    rows = `<div class="empty-state">${filter === "running" ? "Geen actieve containers" : "Geen containers gevonden"}</div>`;
  } else {
    rows = filtered.map(c => renderContainerRow(serverId, c)).join("");
  }

  return `
    <div class="containers-section">
      <div class="section-header">
        <h3>Containers</h3>
      </div>
      <div class="tabs" data-server="${escapeHtml(serverId)}">
        <button class="tab ${filter === "all" ? "active" : ""}" data-filter="all">
          All <span class="count">(${totalCount})</span>
        </button>
        <button class="tab ${filter === "running" ? "active" : ""}" data-filter="running">
          Running <span class="count">(${runningCount})</span>
        </button>
      </div>
      <div class="container-list">
        ${rows}
      </div>
    </div>
  `;
}

// ─── Container rij ─────────────────────────────────────────────────
function renderContainerRow(serverId, container) {
  const isRunning = container.status === "running" || container.status === "restarting";
  const statusClass = isRunning ? "running" : "";
  const healthBadge = container.health_status
    ? `<span class="container-health ${container.health_status}">${escapeHtml(container.health_status)}</span>`
    : "";

  return `
    <div class="container-row" data-container-id="${escapeHtml(container.id)}">
      <div class="container-info">
        <div>
          <div class="container-name">${escapeHtml(container.name)}</div>
          <div class="container-image">${escapeHtml(container.image)}</div>
        </div>
        ${healthBadge}
      </div>
      <div class="container-status">
        <span class="status-text ${statusClass}">${escapeHtml(container.status)}</span>
      </div>
      <div class="container-uptime">${escapeHtml(container.uptime || "—")}</div>
      <div class="container-actions">
        ${isRunning
          ? `<button class="btn btn-sm btn-stop" data-action="stop" data-server="${escapeHtml(serverId)}" data-container="${escapeHtml(container.id)}">Stop</button>
             <button class="btn btn-sm btn-restart" data-action="restart" data-server="${escapeHtml(serverId)}" data-container="${escapeHtml(container.id)}">Herstart</button>`
          : `<button class="btn btn-sm btn-start" data-action="start" data-server="${escapeHtml(serverId)}" data-container="${escapeHtml(container.id)}">Start</button>`
        }
      </div>
    </div>
  `;
}

// ─── Event delegation ──────────────────────────────────────────────
document.addEventListener("click", async (e) => {
  const target = e.target.closest("button");
  if (!target) return;

  // ─── Tab click ────────────────────────────────────────────────
  if (target.classList.contains("tab")) {
    const tabsContainer = target.closest(".tabs");
    if (!tabsContainer) return;

    const serverId = tabsContainer.dataset.server;
    const filter = target.dataset.filter;
    if (!serverId || !filter) return;

    // Update active tab
    $$(".tab", tabsContainer).forEach(t => t.classList.remove("active"));
    target.classList.add("active");

    // Update filter state
    containerFilters[serverId] = filter;

    // Re-render alleen de containers sectie
    await refreshContainers(serverId);
    return;
  }

  // ─── Container actie ──────────────────────────────────────────
  const action = target.dataset.action;
  const serverId = target.dataset.server;
  const containerId = target.dataset.container;

  if (action && serverId && containerId) {
    target.disabled = true;
    const originalText = target.textContent;
    target.textContent = "..." + action;

    try {
      const result = await performContainerAction(serverId, containerId, action);
      if (result.success) {
        showToast(`${containerId}: ${action} uitgevoerd`, "success");
        await loadDashboard(); // Ververs direct
      } else {
        showToast(`Fout bij ${action}: ${result.message}`, "error");
        target.disabled = false;
        target.textContent = originalText;
      }
    } catch (err) {
      showToast(`Fout: ${err.message}`, "error");
      target.disabled = false;
      target.textContent = originalText;
    }
    return;
  }
});

// ─── Container actie uitvoeren ─────────────────────────────────────
async function performContainerAction(serverId, containerId, action) {
  const url = `/api/servers/${encodeURIComponent(serverId)}/containers/${encodeURIComponent(containerId)}/${encodeURIComponent(action)}`;

  const headers = { "Content-Type": "application/json" };
  if (DASHBOARD_API_KEY) {
    headers["X-API-Key"] = DASHBOARD_API_KEY;
  }

  const resp = await fetch(url, {
    method: "POST",
    headers,
  });

  const data = await resp.json();

  if (!resp.ok) {
    // Als 401, vraag om API-key
    if (resp.status === 401 && !DASHBOARD_API_KEY) {
      const key = prompt("API-key vereist voor deze actie. Voer de DASHBOARD_API_KEY in:");
      if (key) {
        DASHBOARD_API_KEY = key;
        return performContainerAction(serverId, containerId, action);
      }
    }
    throw new Error(data.message || `HTTP ${resp.status}`);
  }

  return data;
}

// ─── Containers herladen (na tab switch) ───────────────────────────
async function refreshContainers(serverId) {
  try {
    const resp = await fetch(`/api/servers/${encodeURIComponent(serverId)}/overview`);
    if (!resp.ok) return;
    const data = await resp.json();
    const containers = data.containers || [];
    const runningCount = containers.filter(c => c.status === "running").length;

    const container = $("#dashboard-container");
    if (!container) return;

    // Vervang alleen de containers sectie in de juiste server card
    const card = container.querySelector(`.server-card[data-server="${CSS.escape(serverId)}"]`);
    if (!card) return;

    const oldSection = card.querySelector(".containers-section");
    if (!oldSection) return;

    const newHtml = renderContainersSection(serverId, containers, runningCount);
    const temp = document.createElement("div");
    temp.innerHTML = newHtml;
    const newSection = temp.firstElementChild;
    if (newSection) {
      oldSection.replaceWith(newSection);
    }
  } catch (err) {
    console.warn("Fout bij verversen containers:", err);
  }
}

// ─── Header updaten ────────────────────────────────────────────────
function updateHeader(serverCount) {
  const countEl = $("#server-count");
  if (countEl) {
    countEl.textContent = `${serverCount} server${serverCount !== 1 ? "s" : ""}`;
  }
  const updatedEl = $("#last-updated");
  if (updatedEl) {
    const now = new Date();
    updatedEl.textContent = now.toLocaleTimeString("nl-NL", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }
}

// ─── Toast notificatie ─────────────────────────────────────────────
function showToast(message, type = "info") {
  const container = $("#toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;

  container.appendChild(toast);

  // Automatisch verwijderen na 4 seconden
  setTimeout(() => {
    if (toast.parentNode) {
      toast.style.opacity = "0";
      toast.style.transition = "opacity 0.3s ease";
      setTimeout(() => toast.remove(), 300);
    }
  }, 4000);
}

// ─── HTML entity escaping ──────────────────────────────────────────
function escapeHtml(str) {
  if (str == null) return "";
  const div = document.createElement("div");
  div.textContent = String(str);
  return div.innerHTML;
}

// ─── Start ─────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", init);
