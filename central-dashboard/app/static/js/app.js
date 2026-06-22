/**
 * Homelab Dashboard — Frontend logic
 *
 * Communiceert met de FastAPI backend via fetch().
 * API-key wordt bijgehouden in een simpele variabele (later uit te breiden naar
 * een echte login-flow).
 */

const API_KEY = "dashboard-dev-key"; // TODO: vervangen door echte auth
const API_BASE = "/api";

// ─── State ──────────────────────────────────────────────────────────
let currentTab = "umbrelos";
let pollingInterval = null;

// ─── DOM refs ───────────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ─── Toast notifications ──────────────────────────────────────────
function showToast(message, type = "info", duration = 4000) {
    const container = $("#toast-container");
    if (!container) return;

    const icons = {
        success: `<svg class="toast-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`,
        error: `<svg class="toast-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`,
        info: `<svg class="toast-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`,
    };

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        ${icons[type] || icons.info}
        <span class="toast-message">${message}</span>
    `;
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add("toast-removing");
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// ─── API helper ─────────────────────────────────────────────────────
async function apiFetch(path, options = {}) {
    const res = await fetch(`${API_BASE}${path}`, {
        headers: {
            "X-API-Key": API_KEY,
            "Content-Type": "application/json",
            ...options.headers,
        },
        ...options,
    });
    if (!res.ok) {
        const err = await res.text();
        throw new Error(`HTTP ${res.status}: ${err}`);
    }
    return res.json();
}

// ─── Tabs ───────────────────────────────────────────────────────────
function initTabs() {
    const tabs = $$(".server-tab");
    tabs.forEach((btn) => {
        btn.addEventListener("click", () => {
            tabs.forEach((t) => t.classList.remove("active"));
            btn.classList.add("active");
            if (btn.dataset.view === "storage") {
                currentTab = "storage";
                loadAllStorageData(true);
            } else {
                currentTab = btn.dataset.server;
                loadServerData(currentTab, true);
            }
        });
    });
}

// ─── Data laden ─────────────────────────────────────────────────────
async function loadServerData(serverId, showLoader = true) {
    if (showLoader) showLoading(true);
    try {
        const data = await apiFetch(`/servers/${serverId}/overview`);
        renderServerData(data);
    } catch (err) {
        showError(err.message);
    } finally {
        if (showLoader) showLoading(false);
    }
}

async function loadAllStorageData(showLoader = true) {
    if (showLoader) showLoading(true);
    try {
        const [umbrelos, ubuntu] = await Promise.all([
            apiFetch("/servers/umbrelos/overview"),
            apiFetch("/servers/ubuntu/overview"),
        ]);
        renderGlobalStorageView({ umbrelos, ubuntu });
    } catch (err) {
        showError(err.message);
    } finally {
        if (showLoader) showLoading(false);
    }
}

function reloadCurrentTab() {
    if (currentTab === "storage") {
        loadAllStorageData(true);
    } else {
        loadServerData(currentTab, true);
    }
}

function showLoading(visible) {
    const container = $("#server-content");
    if (visible) {
        container.innerHTML = `
            <div class="scale-in">
                <!-- Skeleton OS Header -->
                <div class="skeleton-card" style="margin-bottom:24px;padding:28px 32px;">
                    <div style="display:flex;align-items:center;gap:16px;">
                        <div class="skeleton-line" style="width:56px;height:56px;border-radius:16px;margin:0;"></div>
                        <div style="flex:1;">
                            <div class="skeleton-line w-40 h-8 mb-4"></div>
                            <div class="skeleton-line w-30 h-4"></div>
                        </div>
                    </div>
                </div>
                <!-- Skeleton Metrics Grid -->
                <div class="metrics-grid">
                    <div class="skeleton-card">
                        <div class="skeleton-line w-40 h-4 mb-4"></div>
                        <div class="skeleton-line w-80 h-8 mb-4"></div>
                        <div class="skeleton-line w-100 h-4"></div>
                    </div>
                    <div class="skeleton-card">
                        <div class="skeleton-line w-40 h-4 mb-4"></div>
                        <div class="skeleton-line w-60 h-8 mb-4"></div>
                        <div class="skeleton-line w-100 h-4"></div>
                    </div>
                    <div class="skeleton-card">
                        <div class="skeleton-line w-40 h-4 mb-4"></div>
                        <div class="skeleton-line w-70 h-8 mb-4"></div>
                        <div class="skeleton-line w-100 h-4"></div>
                    </div>
                </div>
                <!-- Skeleton Docker Section -->
                <div class="skeleton-card">
                    <div class="skeleton-line w-40 h-8 mb-6"></div>
                    <div class="skeleton-line w-100 h-4 mb-4"></div>
                    <div class="skeleton-line w-100 h-4 mb-4"></div>
                    <div class="skeleton-line w-60 h-4"></div>
                </div>
            </div>`;
    }
}

function showError(msg) {
    const container = $("#server-content");
    container.innerHTML = `
        <div class="error-card scale-in">
            <svg class="error-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            <h3 class="error-title">Fout bij ophalen data</h3>
            <p class="error-message">${msg}</p>
            <button onclick="reloadCurrentTab()" class="btn btn-secondary">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                </svg>
                Probeer opnieuw
            </button>
        </div>`;
}

// ─── Render ─────────────────────────────────────────────────────────
function renderServerData(data) {
    const container = $("#server-content");
    const { os, storage, hardware, docker_containers } = data;

    const osBadge = os.os_type === 'umbrelos'
        ? '<span class="badge badge-umbrelos">UmbrelOS</span>'
        : os.os_type === 'ubuntu'
            ? '<span class="badge badge-ubuntu">Ubuntu Server</span>'
            : os.os_type === 'windows'
                ? '<span class="badge badge-windows">Windows</span>'
                : '<span class="badge badge-unknown">Onbekend</span>';

    const osIconClass = os.os_type === 'umbrelos' ? 'umbrelos' : 'umbrelos';
    const osIconClassUbuntu = os.os_type === 'ubuntu' ? 'ubuntu' : '';

    container.innerHTML = `
        <div class="fade-in-up">
            <!-- OS Info Header -->
            <div class="os-header-card">
                <div class="os-header-inner">
                    <div class="os-header-left">
                        <div class="os-icon-box ${os.os_type === 'umbrelos' ? 'umbrelos' : os.os_type === 'ubuntu' ? 'ubuntu' : ''}">
                            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                    d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
                            </svg>
                        </div>
                        <div>
                            <h2 class="os-hostname">${os.hostname}</h2>
                            <div class="os-hostname-sub">${osBadge}</div>
                        </div>
                    </div>
                    <div class="os-info-right">
                        <p class="os-kernel">Kernel ${os.kernel_version}</p>
                        <p class="os-uptime">Uptime: ${os.uptime}</p>
                    </div>
                </div>
            </div>

            <!-- Metrics Grid -->
            <div class="metrics-grid">
                ${renderAggregatedStorage(storage)}
                ${renderCPUCard(hardware)}
                ${renderRAMCard(hardware)}
            </div>

            <!-- Docker Section -->
            <div class="docker-section">
                <div class="docker-header">
                    <h3 class="docker-title">
                        <svg style="width:20px;height:20px;color:#60a5fa;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10"/>
                        </svg>
                        Docker Containers
                    </h3>
                    <span class="docker-count"><span>${docker_containers.length}</span> totaal</span>
                </div>
                <div id="docker-list">
                    ${docker_containers.length === 0
                        ? '<p class="empty-state">Geen containers gevonden.</p>'
                        : docker_containers.map(renderContainerRow).join('')}
                </div>
            </div>
        </div>
    `;

    // Event listeners voor Docker acties
    $$(".btn-start, .btn-stop, .btn-restart").forEach((btn) => {
        btn.addEventListener("click", async (e) => {
            e.stopPropagation();
            const row = btn.closest("[data-container-id]");
            const containerId = row.dataset.containerId;
            const action = btn.dataset.action;
            const actionLabels = { start: "Start", stop: "Stop", restart: "Herstart" };
            showToast(`${actionLabels[action] || action} wordt uitgevoerd...`, "info", 2000);
            await performContainerAction(containerId, action);
        });
    });
}

function renderAggregatedStorage(storages) {
    if (!storages || storages.length === 0) {
        return `
            <div class="metric-card storage">
                <p class="metric-label">Opslag</p>
                <p class="metric-sub">Geen schijfdata beschikbaar</p>
            </div>`;
    }
    const total = storages.reduce((acc, s) => ({
        total_gb: acc.total_gb + s.total_gb,
        used_gb: acc.used_gb + s.used_gb,
        available_gb: acc.available_gb + s.available_gb,
    }), { total_gb: 0, used_gb: 0, available_gb: 0 });

    const pct = total.total_gb > 0 ? Math.round((total.used_gb / total.total_gb) * 100) : 0;
    const barColor = pct > 90 ? "#ef4444" : pct > 70 ? "#f59e0b" : "#22c55e";
    return `
        <div class="metric-card storage">
            <p class="metric-label">
                <svg style="width:16px;height:16px;color:var(--color-cyan);" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10"/>
                </svg>
                Opslag (alle schijven)
            </p>
            <p class="metric-value">${total.used_gb.toFixed(1)}<span class="metric-unit">GB / ${total.total_gb.toFixed(1)}GB</span></p>
            <div class="progress-bar">
                <div class="progress-bar-fill" style="width:${pct}%;background:${barColor};"></div>
            </div>
            <p class="metric-sub">${total.available_gb.toFixed(1)}GB vrij &mdash; ${pct}% gebruikt</p>
            <p class="metric-footer">${storages.length} schijf(ven)</p>
        </div>`;
}

function renderGlobalStorageView(allData) {
    const container = $("#server-content");

    let sections = '';
    for (const [serverId, data] of Object.entries(allData)) {
        const { os, storage } = data;
        const label = os.os_type === 'umbrelos' ? 'UmbrelOS' : 'Ubuntu Server';
        const dotClass = os.os_type === 'umbrelos' ? 'umbrelos' : 'ubuntu';

        sections += `
            <div class="storage-server-section">
                <h3 class="storage-server-header">
                    <span class="tab-dot ${dotClass}"></span>
                    ${label} — ${os.hostname}
                </h3>
                <div>
                    ${(!storage || storage.length === 0)
                        ? '<p class="empty-state">Geen schijfdata beschikbaar.</p>'
                        : storage.map(renderStorageDetailCard).join('')}
                </div>
            </div>`;
    }

    container.innerHTML = `
        <h2 class="storage-section-header fade-in-up">Opslagoverzicht — Alle servers</h2>
        ${sections}
    `;
}

function renderStorageDetailCard(s) {
    const pct = s.used_percent;
    const barColor = pct > 90 ? "#ef4444" : pct > 70 ? "#f59e0b" : "#22c55e";
    const pctClass = pct > 90 ? 'pct-high' : pct > 70 ? 'pct-mid' : 'pct-low';

    return `
        <div class="storage-mount-card">
            <div class="storage-mount-header">
                <div>
                    <h3 class="storage-mount-point">${s.mount_point}</h3>
                    <p class="storage-mount-detail">${s.device || s.fstype || 'Onbekend apparaat'}</p>
                </div>
                <span class="pct-badge ${pctClass}">${pct}% gebruikt</span>
            </div>
            <div class="progress-bar-lg">
                <div class="progress-bar-fill" style="width:${pct}%;background:${barColor};"></div>
            </div>
            <div class="storage-mount-stats">
                <span>${s.used_gb}GB gebruikt</span>
                <span>${s.available_gb}GB vrij</span>
                <span>${s.total_gb}GB totaal</span>
            </div>
        </div>`;
}

function renderCPUCard(hw) {
    const pct = hw.cpu_percent;
    const barColor = pct > 90 ? "#ef4444" : pct > 70 ? "#f59e0b" : "#22c55e";
    return `
        <div class="metric-card cpu">
            <p class="metric-label">
                <svg style="width:16px;height:16px;color:var(--color-primary);" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"/>
                </svg>
                CPU
            </p>
            <p class="metric-value">${pct}<span class="metric-unit">%</span></p>
            <div class="progress-bar">
                <div class="progress-bar-fill" style="width:${pct}%;background:${barColor};"></div>
            </div>
            <p class="metric-sub">${hw.cpu_cores} cores</p>
        </div>`;
}

function renderRAMCard(hw) {
    const pct = hw.ram_percent;
    const barColor = pct > 90 ? "#ef4444" : pct > 70 ? "#f59e0b" : "#22c55e";
    return `
        <div class="metric-card ram">
            <p class="metric-label">
                <svg style="width:16px;height:16px;color:var(--color-warning);" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2"/>
                </svg>
                RAM
            </p>
            <p class="metric-value">${hw.ram_used_gb}<span class="metric-unit">GB / ${hw.ram_total_gb}GB</span></p>
            <div class="progress-bar">
                <div class="progress-bar-fill" style="width:${pct}%;background:${barColor};"></div>
            </div>
            <p class="metric-sub">${pct}% gebruikt</p>
        </div>`;
}

function renderContainerRow(c) {
    const statusClass = c.status === "running" ? "running" : c.status === "stopped" ? "stopped" : c.status === "created" ? "created" : "paused";

    return `
        <div class="container-row" data-container-id="${c.id}">
            <div class="container-info">
                <span class="status-dot ${statusClass}"></span>
                <div class="container-meta">
                    <p class="container-name">${c.name}</p>
                    <p class="container-image">${c.image}</p>
                </div>
            </div>
            <div class="container-actions">
                <span class="container-ports">${c.ports || ''}</span>
                <span class="status-pill ${statusClass}">${c.status}</span>
                <div style="display:flex;gap:6px;">
                    ${c.status === 'stopped' ? `<button class="btn btn-start" data-action="start">Start</button>` : ''}
                    ${c.status === 'running' ? `<button class="btn btn-stop" data-action="stop">Stop</button>` : ''}
                    ${c.status === 'running' ? `<button class="btn btn-restart" data-action="restart">Herstart</button>` : ''}
                </div>
            </div>
        </div>`;
}

// ─── Docker acties ──────────────────────────────────────────────────
async function performContainerAction(containerId, action) {
    const serverId = currentTab === "storage" ? "umbrelos" : currentTab;
    const actionLabels = { start: "gestart", stop: "gestopt", restart: "herstart" };
    try {
        await apiFetch(`/servers/${serverId}/docker/${containerId}/${action}`, {
            method: "POST",
        });
        showToast(`Container succesvol ${actionLabels[action] || action}`, "success");
        // Herlaad data na actie
        if (currentTab === "storage") {
            loadAllStorageData();
        } else {
            loadServerData(currentTab);
        }
    } catch (err) {
        showToast(`Actie mislukt: ${err.message}`, "error", 6000);
    }
}

// ─── Polling (auto-refresh) ─────────────────────────────────────────
function startPolling() {
    stopPolling();
    pollingInterval = setInterval(() => {
        if (currentTab === "storage") {
            loadAllStorageData(false);
        } else {
            loadServerData(currentTab, false);
        }
    }, 30000); // elke 30 seconden — stille refresh zonder laad-skeleton
}

function stopPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
}

// ─── Init ───────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    loadServerData(currentTab, true);
    startPolling();
});
