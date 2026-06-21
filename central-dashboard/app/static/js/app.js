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
let currentServer = "umbrelos";
let pollingInterval = null;

// ─── DOM refs ───────────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

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
            currentServer = btn.dataset.server;
            loadServerData(currentServer);
        });
    });
}

// ─── Data laden ─────────────────────────────────────────────────────
async function loadServerData(serverId) {
    showLoading(true);
    try {
        const data = await apiFetch(`/servers/${serverId}/overview`);
        renderServerData(data);
    } catch (err) {
        showError(err.message);
    } finally {
        showLoading(false);
    }
}

function showLoading(visible) {
    const spinner = $("#loading-spinner");
    if (spinner) spinner.style.display = visible ? "inline-block" : "none";
}

function showError(msg) {
    const container = $("#server-content");
    container.innerHTML = `
        <div class="flex items-center justify-center h-64">
            <div class="text-center text-red-400">
                <svg class="w-12 h-12 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                <p class="text-lg font-medium">Fout bij ophalen data</p>
                <p class="text-sm text-gray-400 mt-1">${msg}</p>
                <button onclick="loadServerData('${currentServer}')"
                    class="mt-4 px-4 py-2 bg-indigo-600 rounded-lg hover:bg-indigo-500 transition-colors">
                    Probeer opnieuw
                </button>
            </div>
        </div>`;
}

// ─── Render ─────────────────────────────────────────────────────────
function renderServerData(data) {
    const container = $("#server-content");
    const { os, storage, hardware, docker_containers } = data;

    container.innerHTML = `
        <!-- OS Info Header -->
        <div class="bg-gray-800 rounded-xl p-5 border border-gray-700 mb-6">
            <div class="flex items-center justify-between">
                <div>
                    <h2 class="text-2xl font-bold text-white">${os.hostname}</h2>
                    <span class="inline-flex items-center mt-1 px-3 py-1 rounded-full text-xs font-medium
                        ${os.os_type === 'umbrelos' ? 'bg-purple-900 text-purple-200' :
                          os.os_type === 'ubuntu' ? 'bg-orange-900 text-orange-200' :
                          os.os_type === 'windows' ? 'bg-blue-900 text-blue-200' :
                          'bg-gray-700 text-gray-300'}">
                        ${os.os_type === 'umbrelos' ? 'UmbrelOS' :
                          os.os_type === 'ubuntu' ? 'Ubuntu Server' :
                          os.os_type === 'windows' ? 'Windows' :
                          os.os_type === 'unknown' ? 'Onbekend' : os.os_type}
                    </span>
                </div>
                <div class="text-right text-sm text-gray-400">
                    <p>Kernel ${os.kernel_version}</p>
                    <p>Uptime: ${os.uptime}</p>
                </div>
            </div>
        </div>

        <!-- Metrics Grid -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            ${renderStorageCards(storage)}
            ${renderCPUCard(hardware)}
            ${renderRAMCard(hardware)}
        </div>

        <!-- Docker Section -->
        <div class="bg-gray-800 rounded-xl p-5 border border-gray-700">
            <h3 class="text-lg font-semibold text-white mb-4 flex items-center">
                <svg class="w-5 h-5 mr-2 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10"/>
                </svg>
                Docker Containers
                <span class="ml-auto text-sm font-normal text-gray-400">
                    ${docker_containers.length} totaal
                </span>
            </h3>
            <div id="docker-list" class="space-y-2">
                ${docker_containers.length === 0
                    ? '<p class="text-gray-400 text-sm">Geen containers gevonden.</p>'
                    : docker_containers.map(renderContainerRow).join('')}
            </div>
        </div>
    `;

    // Event listeners voor Docker acties
    $$(".btn-action").forEach((btn) => {
        btn.addEventListener("click", async (e) => {
            const row = btn.closest("[data-container-id]");
            const containerId = row.dataset.containerId;
            const action = btn.dataset.action;
            await performContainerAction(containerId, action);
        });
    });
}

function renderStorageCards(storages) {
    if (!storages || storages.length === 0) {
        return `
            <div class="metric-card">
                <h4 class="text-sm font-medium text-gray-400 mb-1">Opslag</h4>
                <p class="text-sm text-gray-500">Geen schijfdata beschikbaar</p>
            </div>`;
    }
    return storages.map(s => {
        const pct = s.used_percent;
        const color = pct > 90 ? "bg-red-500" : pct > 70 ? "bg-yellow-500" : "bg-green-500";
        const label = s.mount_point === "/" ? "Systeemschijf" : s.mount_point.split("/").pop();
        return `
        <div class="metric-card">
            <h4 class="text-sm font-medium text-gray-400 mb-1">
                ${s.mount_point}
                <span class="text-xs text-gray-500 ml-1">(${s.device || s.fstype || ''})</span>
            </h4>
            <p class="text-2xl font-bold text-white mb-1">${s.used_gb}GB <span class="text-sm font-normal text-gray-400">/ ${s.total_gb}GB</span></p>
            <div class="progress-bar mt-2">
                <div class="progress-bar-fill ${color}" style="width:${pct}%"></div>
            </div>
            <p class="text-xs text-gray-400 mt-1">${s.available_gb}GB vrij — ${pct}% gebruikt</p>
        </div>`;
    }).join('');
}
}

function renderCPUCard(hw) {
    const pct = hw.cpu_percent;
    const color = pct > 90 ? "bg-red-500" : pct > 70 ? "bg-yellow-500" : "bg-green-500";
    return `
        <div class="metric-card">
            <h4 class="text-sm font-medium text-gray-400 mb-1">CPU</h4>
            <p class="text-2xl font-bold text-white mb-1">${pct}%</p>
            <div class="progress-bar mt-2">
                <div class="progress-bar-fill ${color}" style="width:${pct}%"></div>
            </div>
            <p class="text-xs text-gray-400 mt-1">${hw.cpu_cores} cores</p>
        </div>`;
}

function renderRAMCard(hw) {
    const pct = hw.ram_percent;
    const color = pct > 90 ? "bg-red-500" : pct > 70 ? "bg-yellow-500" : "bg-green-500";
    return `
        <div class="metric-card">
            <h4 class="text-sm font-medium text-gray-400 mb-1">RAM</h4>
            <p class="text-2xl font-bold text-white mb-1">${hw.ram_used_gb}GB <span class="text-sm font-normal text-gray-400">/ ${hw.ram_total_gb}GB</span></p>
            <div class="progress-bar mt-2">
                <div class="progress-bar-fill ${color}" style="width:${pct}%"></div>
            </div>
            <p class="text-xs text-gray-400 mt-1">${pct}% gebruikt</p>
        </div>`;
}

function renderContainerRow(c) {
    const statusClass = c.status === "running" ? "running" : c.status === "stopped" ? "stopped" : c.status === "created" ? "created" : "paused";
    const showActions = c.status === "running" || c.status === "stopped";

    return `
        <div class="container-row" data-container-id="${c.id}">
            <div class="flex items-center min-w-0">
                <span class="status-dot ${statusClass}"></span>
                <div class="min-w-0">
                    <p class="text-sm font-medium text-white truncate">${c.name}</p>
                    <p class="text-xs text-gray-400 truncate">${c.image}</p>
                </div>
            </div>
            <div class="flex items-center gap-2 ml-4 flex-shrink-0">
                <span class="text-xs text-gray-400 hidden sm:inline">${c.ports || ''}</span>
                <span class="text-xs px-2 py-0.5 rounded-full font-medium
                    ${c.status === 'running' ? 'bg-green-900 text-green-200' : 
                      c.status === 'stopped' ? 'bg-red-900 text-red-200' : 
                      c.status === 'created' ? 'bg-gray-700 text-gray-300' :
                      'bg-yellow-900 text-yellow-200'}">
                    ${c.status}
                </span>
                <div class="flex gap-1">
                    ${c.status === 'stopped' ? `<button class="btn-action btn-start" data-action="start">Start</button>` : ''}
                    ${c.status === 'running' ? `<button class="btn-action btn-stop" data-action="stop">Stop</button>` : ''}
                    ${c.status === 'running' ? `<button class="btn-action btn-restart" data-action="restart">Herstart</button>` : ''}
                </div>
            </div>
        </div>`;
}

// ─── Docker acties ──────────────────────────────────────────────────
async function performContainerAction(containerId, action) {
    try {
        await apiFetch(`/servers/${currentServer}/docker/${containerId}/${action}`, {
            method: "POST",
        });
        // Herlaad data na actie
        await loadServerData(currentServer);
    } catch (err) {
        showError(err.message);
    }
}

// ─── Polling (auto-refresh) ─────────────────────────────────────────
function startPolling() {
    stopPolling();
    pollingInterval = setInterval(() => {
        loadServerData(currentServer);
    }, 10000); // elke 10 seconden
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
    loadServerData(currentServer);
    startPolling();
});
