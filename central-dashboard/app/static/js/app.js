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
let currentView = "overview";
let cachedData = null;
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
            currentView = "overview";
            loadServerData(currentServer);
        });
    });
}

// ─── View switching ─────────────────────────────────────────────────
function switchView(view) {
    currentView = view;
    renderCurrentView();
}

function renderCurrentView() {
    if (!cachedData) return;
    if (currentView === "overview") {
        renderServerData(cachedData);
    } else if (currentView === "storage") {
        renderStorageView(cachedData);
    }
}

// ─── Data laden ─────────────────────────────────────────────────────
async function loadServerData(serverId) {
    showLoading(true);
    try {
        const data = await apiFetch(`/servers/${serverId}/overview`);
        cachedData = data;
        renderCurrentView();
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
            ${renderAggregatedStorage(storage)}
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

function renderAggregatedStorage(storages) {
    if (!storages || storages.length === 0) {
        return `
            <div class="metric-card">
                <h4 class="text-sm font-medium text-gray-400 mb-1">Opslag</h4>
                <p class="text-sm text-gray-500">Geen schijfdata beschikbaar</p>
            </div>`;
    }
    // Alles samenvoegen tot 1 totaal
    const total = storages.reduce((acc, s) => ({
        total_gb: acc.total_gb + s.total_gb,
        used_gb: acc.used_gb + s.used_gb,
        available_gb: acc.available_gb + s.available_gb,
    }), { total_gb: 0, used_gb: 0, available_gb: 0 });

    const pct = total.total_gb > 0 ? Math.round((total.used_gb / total.total_gb) * 100) : 0;
    const color = pct > 90 ? "bg-red-500" : pct > 70 ? "bg-yellow-500" : "bg-green-500";
    return `
        <div class="metric-card">
            <h4 class="text-sm font-medium text-gray-400 mb-1">Opslag (alle schijven)</h4>
            <p class="text-2xl font-bold text-white mb-1">${total.used_gb.toFixed(1)}GB <span class="text-sm font-normal text-gray-400">/ ${total.total_gb.toFixed(1)}GB</span></p>
            <div class="progress-bar mt-2">
                <div class="progress-bar-fill ${color}" style="width:${pct}%"></div>
            </div>
            <p class="text-xs text-gray-400 mt-1">${total.available_gb.toFixed(1)}GB vrij — ${pct}% gebruikt</p>
            <p class="text-xs text-gray-500 mt-1">${storages.length} schijf(ven) —
                <button onclick="switchView('storage')" class="text-indigo-400 hover:text-indigo-300 underline">Details</button>
            </p>
        </div>`;
}

function renderStorageView(data) {
    const { os, storage } = data;
    const container = $("#server-content");

    container.innerHTML = `
        <div class="mb-4">
            <button onclick="switchView('overview')" class="text-indigo-400 hover:text-indigo-300 text-sm flex items-center gap-1">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
                </svg>
                Terug naar overzicht
            </button>
        </div>

        <h2 class="text-xl font-bold text-white mb-4">Schijfdetails — ${os.hostname}</h2>

        <div class="space-y-4">
            ${(!storage || storage.length === 0)
                ? '<p class="text-gray-400">Geen schijfdata beschikbaar.</p>'
                : storage.map(renderStorageDetailCard).join('')}
        </div>
    `;
}

function renderStorageDetailCard(s) {
    const pct = s.used_percent;
    const color = pct > 90 ? "bg-red-500" : pct > 70 ? "bg-yellow-500" : "bg-green-500";

    return `
        <div class="bg-gray-800 rounded-xl p-5 border border-gray-700">
            <div class="flex items-center justify-between mb-3">
                <div>
                    <h3 class="text-lg font-semibold text-white">${s.mount_point}</h3>
                    <p class="text-sm text-gray-400">${s.device || s.fstype || 'Onbekend apparaat'}</p>
                </div>
                <span class="text-sm px-3 py-1 rounded-full font-medium
                    ${pct > 90 ? 'bg-red-900 text-red-200' :
                      pct > 70 ? 'bg-yellow-900 text-yellow-200' :
                      'bg-green-900 text-green-200'}">
                    ${pct}% gebruikt
                </span>
            </div>
            <!-- Hogere voortgangsbalk -->
            <div class="w-full bg-gray-700 rounded-full h-4 mb-3">
                <div class="h-4 rounded-full transition-all duration-500 ${color}" style="width:${pct}%"></div>
            </div>
            <div class="flex justify-between text-sm text-gray-400">
                <span>${s.used_gb}GB gebruikt</span>
                <span>${s.available_gb}GB vrij</span>
                <span>${s.total_gb}GB totaal</span>
            </div>
        </div>`;
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
