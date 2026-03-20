// ── Config ───────────────────────────────────────
const API_BASE = "https://plum-escalation-production.up.railway.app";
let currentTab = "escalations";
let activeDrawerId = null;
let autoRefreshInterval = null;

// ── Auth helpers ─────────────────────────────────
function getToken()        { return localStorage.getItem("plum_token"); }
function setToken(t)       { localStorage.setItem("plum_token", t); }
function clearToken()      { localStorage.removeItem("plum_token"); }

function showLoginOverlay() {
  document.getElementById("login-overlay").style.display = "flex";
}
function hideLoginOverlay() {
  document.getElementById("login-overlay").style.display = "none";
}

async function doLogin(e) {
  e.preventDefault();
  const btn = document.getElementById("login-btn");
  const errEl = document.getElementById("login-error");
  const username = document.getElementById("login-username").value.trim();
  const password = document.getElementById("login-password").value;
  btn.disabled = true;
  btn.textContent = "Signing in...";
  errEl.style.display = "none";
  try {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Login failed");
    setToken(data.token);
    hideLoginOverlay();
    refreshAll();
    startAutoRefresh();
  } catch(err) {
    errEl.textContent = "✗ " + err.message;
    errEl.style.display = "block";
  } finally {
    btn.disabled = false;
    btn.textContent = "Sign In →";
  }
}

function doLogout() {
  clearToken();
  showLoginOverlay();
  if (autoRefreshInterval) { clearInterval(autoRefreshInterval); autoRefreshInterval = null; }
}

// ── Authenticated fetch wrapper ───────────────────
async function apiFetch(url, options = {}) {
  const token = getToken();
  const headers = { ...(options.headers || {}) };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(url, { ...options, headers });
  if (res.status === 401) {
    clearToken();
    showLoginOverlay();
    throw new Error("Session expired — please log in again");
  }
  return res;
}

// ── Init ─────────────────────────────────────────
window.addEventListener("DOMContentLoaded", () => {
  document.getElementById("header-date").textContent =
    "Today: " + new Date().toLocaleDateString("en-IN", { weekday: "long", year: "numeric", month: "long", day: "numeric" });

  if (getToken()) {
    refreshAll();
    startAutoRefresh();
  } else {
    showLoginOverlay();
  }
});

function startAutoRefresh() {
  if (autoRefreshInterval) clearInterval(autoRefreshInterval);
  autoRefreshInterval = setInterval(refreshAll, 30000); // every 30s
}

function refreshAll() {
  fetchStats();
  if (currentTab === "escalations") applyFilters();
  else if (currentTab === "vpwatch")  fetchVpWatch();
  else if (currentTab === "analytics") loadAnalytics();
  else fetchNoise();
}

// ── Tab switching ─────────────────────────────────
function switchTab(tab) {
  currentTab = tab;
  ["escalations","vpwatch","noise","analytics"].forEach(t => {
    const el = document.getElementById(`tab-${t}`);
    if (el) el.className = "tab" + (tab === t ? " active" : "");
  });
  document.getElementById("table-escalations").style.display = tab === "escalations" ? "block" : "none";
  document.getElementById("table-vpwatch").style.display      = tab === "vpwatch"     ? "block" : "none";
  document.getElementById("table-noise").style.display        = tab === "noise"       ? "block" : "none";
  document.getElementById("panel-analytics").style.display    = tab === "analytics"   ? "block" : "none";
  document.getElementById("main-filter-bar").style.display    = tab === "escalations" ? "flex"  : "none";

  if (tab === "noise")     fetchNoise();
  if (tab === "vpwatch")   fetchVpWatch();
  if (tab === "analytics") loadAnalytics();
}

// ── Stats Cards ───────────────────────────────────
async function fetchStats() {
  try {
    const res = await apiFetch(`${API_BASE}/api/stats`);
    if (!res.ok) return;
    const data = await res.json();
    document.getElementById("stat-total").textContent      = data.total        ?? 0;
    document.getElementById("stat-high").textContent       = data.high_priority ?? 0;
    document.getElementById("stat-sla").textContent        = data.sla_breached  ?? 0;
    document.getElementById("stat-blocked").textContent    = data.blocked       ?? 0;
    document.getElementById("stat-closed").textContent     = data.closed_today  ?? 0;
    document.getElementById("stat-vp-watch").textContent   = data.vp_watch_count ?? 0;
    renderNorthStar(data);
  } catch (e) {
    console.warn("[Stats] fetch failed:", e.message);
  }
}

// ── North Star Metric ─────────────────────────────
function renderNorthStar(data) {
  const rate = data.sla_resolution_rate;
  const rateEl = document.getElementById("ns-rate");
  const bar = document.getElementById("northstar-bar");

  if (rate === null || rate === undefined) {
    rateEl.textContent = "—";
    bar.className = "northstar-bar ns-neutral";
  } else {
    rateEl.textContent = rate + "%";
    if (rate >= 80)      bar.className = "northstar-bar ns-good";
    else if (rate >= 60) bar.className = "northstar-bar ns-warn";
    else                 bar.className = "northstar-bar ns-bad";
  }

  const avgH = data.avg_resolution_hours;
  document.getElementById("ns-avg-hours").textContent =
    avgH ? (avgH < 1 ? `${Math.round(avgH*60)}m` : `${avgH}h`) : "—";

  document.getElementById("ns-total-closed").textContent = data.total_closed ?? 0;

  const atRisk = data.escalations_at_risk ?? 0;
  document.getElementById("ns-at-risk").textContent = atRisk;
  const riskKpi = document.getElementById("ns-at-risk-kpi");
  riskKpi.className = "northstar-kpi" + (atRisk > 0 ? " danger" : "");
}

// ── Filters → Fetch Escalations ───────────────────
function applyFilters() {
  const status     = document.getElementById("filter-status").value;
  const urgency    = document.getElementById("filter-urgency").value;
  const channel    = document.getElementById("filter-channel").value;
  const department = document.getElementById("filter-department").value;
  const owner      = document.getElementById("filter-owner").value;
  const date       = document.getElementById("filter-date").value;
  const search     = document.getElementById("filter-search").value;

  const params = new URLSearchParams({ is_escalation: 1 });
  if (status)     params.set("status",      status);
  if (urgency)    params.set("urgency",     urgency);
  if (department) params.set("department",  department);
  if (owner)      params.set("owner",       owner);
  if (date)       params.set("date_filter", date);
  if (search)     params.set("search",      search);

  fetchEscalations(params, channel);
}

function clearAllFilters() {
  ["filter-status","filter-urgency","filter-channel","filter-department","filter-owner","filter-date"].forEach(id => {
    document.getElementById(id).value = "";
  });
  document.getElementById("filter-search").value = "";
  applyFilters();
}

async function fetchEscalations(params, channelFilter = "") {
  const tbody = document.getElementById("table-body");
  tbody.innerHTML = `<tr class="loading-row"><td colspan="13">Loading...</td></tr>`;

  try {
    const res = await apiFetch(`${API_BASE}/api/escalations?${params.toString()}`);
    const data = await res.json();

    let rows = data.escalations || [];
    if (channelFilter) rows = rows.filter(r => r.source_channel === channelFilter);

    populateOwnerFilter(rows);

    if (rows.length === 0) {
      tbody.innerHTML = `<tr><td colspan="13"><div class="empty-state"><p>No escalations found for the selected filters.</p></div></td></tr>`;
      return;
    }

    tbody.innerHTML = rows.map(r => buildEscalationRow(r)).join("");
  } catch (e) {
    tbody.innerHTML = `<tr class="loading-row"><td colspan="13">Could not connect to API at ${API_BASE}. Is the server running?</td></tr>`;
  }
}

function buildEscalationRow(r) {
  const isSlaBreached = isSLABreached(r);
  const isWatching    = r.vp_watch === 1;
  const rowClass = [
    isSlaBreached && r.status !== "Closed" ? "sla-breached" : "",
    isWatching ? "vp-watching" : "",
  ].filter(Boolean).join(" ");

  return `<tr class="${rowClass}" onclick="openDrawer(${r.id})">
    <td><strong>#${r.id}</strong></td>
    <td>
      <strong>${esc(r.account_name || "Unknown")}</strong><br>
      <span style="font-size:11px;color:#9ca3af;">${esc(r.sender_name || "")}</span>
    </td>
    <td><span class="badge badge-${r.source_channel}">${r.source_channel}</span></td>
    <td><span class="dept-badge">${esc(r.assigned_department || "Account Management")}</span></td>
    <td style="font-size:12px;color:#6b7280;">${esc(r.issue_category || "—")}</td>
    <td><span class="priority-score ${priorityClass(r.priority_score)}">${r.priority_score}</span></td>
    <td class="td-summary" title="${esc(r.ai_summary || "")}">${esc(r.ai_summary || "—")}</td>
    <td onclick="event.stopPropagation()">
      <input class="owner-input" value="${esc(r.owner || "")}" placeholder="Assign..."
        onblur="updateField(${r.id}, 'owner', this.value)" onkeydown="if(event.key==='Enter')this.blur()" />
    </td>
    <td onclick="event.stopPropagation()">
      <select class="status-select ${statusClass(r.status)}" onchange="updateField(${r.id}, 'status', this.value)">
        ${["Open","In Progress","Blocked","Closed"].map(s =>
          `<option value="${s}" ${r.status===s?"selected":""}>${s}</option>`).join("")}
      </select>
    </td>
    <td class="tat ${isSlaBreached && r.status!=='Closed' ? 'overdue' : ''}">${computeTAT(r.created_at, r.closed_at)}</td>
    <td class="td-action" title="${esc(r.action_needed || "")}">${esc(r.action_needed || "—")}</td>
    <td onclick="event.stopPropagation()">
      <button class="vp-check-btn ${r.vp_check ? 'active' : ''}"
        onclick="toggleVpCheck(${r.id}, ${r.vp_check || 0})"
        title="${r.vp_check ? 'Marked for VP Check — click to remove' : 'Flag for VP to check'}">
        ${r.vp_check ? '✔ VP Check' : '+ VP Check'}
      </button>
    </td>
    <td>${slaTag(r)}</td>
    <td onclick="event.stopPropagation()">
      ${isWatching
        ? `<div style="display:flex;flex-direction:column;gap:3px;align-items:flex-start;">
             ${r.vp_urgency_override ? `<span class="vp-urgency-badge ${r.vp_urgency_override.toLowerCase()}" style="font-size:10px;">${r.vp_urgency_override === 'CRITICAL' ? '🔴' : r.vp_urgency_override === 'HIGH' ? '🟠' : '🟡'} ${r.vp_urgency_override}</span>` : ""}
             <button class="watch-btn active" onclick="toggleWatch(${r.id}, 1)" title="Remove from VP Watch">👁 Watching</button>
           </div>`
        : `<button class="watch-btn" onclick="toggleWatch(${r.id}, 0)" title="Flag & escalate this case">👁 Watch</button>`
      }
    </td>
  </tr>`;
}

// ── VP Watch Tab ──────────────────────────────────
async function fetchVpWatch() {
  const tbody = document.getElementById("vpwatch-body");
  tbody.innerHTML = `<tr class="loading-row"><td colspan="11">Loading VP Watch cases...</td></tr>`;
  try {
    const res = await apiFetch(`${API_BASE}/api/escalations?is_escalation=1&vp_watch=1&limit=100`);
    const data = await res.json();
    const rows = data.escalations || [];

    if (rows.length === 0) {
      tbody.innerHTML = `<tr><td colspan="11"><div class="empty-state"><p>No cases under VP Watch. Click "👁 Watch" on any escalation to add it here.</p></div></td></tr>`;
      return;
    }

    tbody.innerHTML = rows.map(r => {
      const vpUrgency = r.vp_urgency_override || "";
      const urgencyBadge = vpUrgency === "CRITICAL"
        ? `<span class="vp-urgency-badge critical">🔴 CRITICAL</span>`
        : vpUrgency === "HIGH"
        ? `<span class="vp-urgency-badge high">🟠 HIGH</span>`
        : vpUrgency === "MEDIUM"
        ? `<span class="vp-urgency-badge medium">🟡 MEDIUM</span>`
        : `<span style="font-size:11px;color:#9ca3af;">—</span>`;
      const escalatedDept = r.vp_escalate_dept
        ? `<span class="dept-badge" style="background:#ede9fe;color:#6d28d9;">${esc(r.vp_escalate_dept)}</span>`
        : `<span style="font-size:11px;color:#9ca3af;">(unchanged)</span>`;
      return `
      <tr class="vp-watching vp-priority-${(vpUrgency||"high").toLowerCase()}" onclick="openDrawer(${r.id})">
        <td><strong>#${r.id}</strong></td>
        <td><strong>${esc(r.account_name||"Unknown")}</strong><br><span style="font-size:11px;color:#9ca3af;">${esc(r.sender_name||"")}</span></td>
        <td><span class="badge badge-${r.source_channel}">${r.source_channel}</span></td>
        <td><span class="dept-badge">${esc(r.assigned_department||"Account Management")}</span></td>
        <td onclick="event.stopPropagation()">${urgencyBadge}</td>
        <td>${escalatedDept}</td>
        <td style="font-size:12px;color:#7c3aed;font-style:italic;">${esc(r.vp_watch_note||"—")}</td>
        <td><select class="status-select ${statusClass(r.status)}" onclick="event.stopPropagation()" onchange="updateField(${r.id},'status',this.value)">
          ${["Open","In Progress","Blocked","Closed"].map(s=>`<option value="${s}" ${r.status===s?"selected":""}>${s}</option>`).join("")}
        </select></td>
        <td class="tat">${computeTAT(r.created_at, r.closed_at)}</td>
        <td>${slaTag(r)}</td>
        <td onclick="event.stopPropagation()" style="white-space:nowrap;">
          <button class="watch-btn" style="margin-bottom:4px;" onclick="openVpWatchModal(${r.id})" title="Edit flag">Edit</button>
          <button class="watch-btn active" onclick="unwatchCase(${r.id})" title="Remove from VP Watch">Remove</button>
        </td>
      </tr>`;
    }).join("");
  } catch(e) {
    tbody.innerHTML = `<tr class="loading-row"><td colspan="11">API unreachable</td></tr>`;
  }
}

// ── VP Watch — open modal to flag & escalate ──
function toggleWatch(id, currentValue) {
  if (currentValue === 1) {
    // Already watching — remove directly
    unwatchCase(id);
  } else {
    openVpWatchModal(id);
  }
}

async function toggleVpCheck(id, currentValue) {
  const newValue = currentValue === 1 ? 0 : 1;
  await apiFetch(`${API_BASE}/api/escalations/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ vp_check: newValue }),
  });
  fetchStats();
  if (currentTab === "escalations") applyFilters();
  else if (currentTab === "vpwatch") fetchVpWatch();
  showToast(newValue === 1 ? "Flagged for VP Check" : "VP Check removed");
}

async function unwatchCase(id) {
  await apiFetch(`${API_BASE}/api/escalations/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ vp_watch: 0, vp_urgency_override: "", vp_escalate_dept: "", vp_watch_note: "" }),
  });
  fetchStats();
  if (currentTab === "escalations") applyFilters();
  else if (currentTab === "vpwatch") fetchVpWatch();
}

async function openVpWatchModal(id) {
  try {
    const res = await apiFetch(`${API_BASE}/api/escalations/${id}`);
    const r = await res.json();
    document.getElementById("vp-case-id").value = id;
    document.getElementById("vp-case-summary").innerHTML =
      `<strong>#${r.id} — ${esc(r.account_name || "Unknown")}</strong><br>
       <span style="font-size:12px;color:#6b7280;">${esc((r.ai_summary || r.raw_message || "").substring(0, 120))}...</span>`;
    // Reset form
    document.querySelector('input[name="vp-urgency"][value="HIGH"]').checked = true;
    document.getElementById("vp-escalate-dept").value = "";
    document.getElementById("vp-note-input").value = r.vp_watch_note || "";
    document.getElementById("vpwatch-overlay").classList.add("open");
    document.getElementById("vpwatch-modal").classList.add("open");
  } catch(e) { console.error("VP modal load failed:", e); }
}

function closeVpWatchModal() {
  document.getElementById("vpwatch-overlay").classList.remove("open");
  document.getElementById("vpwatch-modal").classList.remove("open");
}

async function confirmVpWatch() {
  const id       = document.getElementById("vp-case-id").value;
  const urgency  = document.querySelector('input[name="vp-urgency"]:checked')?.value || "HIGH";
  const dept     = document.getElementById("vp-escalate-dept").value;
  const note     = document.getElementById("vp-note-input").value.trim();

  const payload = {
    vp_watch: 1,
    vp_urgency_override: urgency,
    vp_watch_note: note,
  };
  if (dept) payload.vp_escalate_dept = dept;

  await apiFetch(`${API_BASE}/api/escalations/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  closeVpWatchModal();
  fetchStats();
  if (currentTab === "escalations") applyFilters();
  else if (currentTab === "vpwatch") fetchVpWatch();
}

// ── Non-Escalations Tab ───────────────────────────
async function fetchNoise() {
  const tbody = document.getElementById("noise-body");
  tbody.innerHTML = `<tr class="loading-row"><td colspan="6">Loading...</td></tr>`;
  try {
    const res = await apiFetch(`${API_BASE}/api/escalations?is_escalation=0&limit=100`);
    const data = await res.json();
    const rows = data.escalations || [];
    if (rows.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state"><p>No filtered messages. All messages are escalations.</p></div></td></tr>`;
      return;
    }
    tbody.innerHTML = rows.map(r => `<tr>
      <td>#${r.id}</td>
      <td>${esc(r.sender_name || "Unknown")}</td>
      <td><span class="badge badge-${r.source_channel}">${r.source_channel}</span></td>
      <td style="font-size:12px;">${formatDate(r.received_at)}</td>
      <td class="td-summary" title="${esc(r.raw_message)}">${esc(r.raw_message.substring(0, 100))}...</td>
      <td style="font-size:12px;color:#9ca3af;">${esc(r.ai_summary || "Non-escalation")}</td>
    </tr>`).join("");
  } catch(e) {
    tbody.innerHTML = `<tr class="loading-row"><td colspan="6">API unreachable</td></tr>`;
  }
}

// ── Detail Drawer ─────────────────────────────────
async function openDrawer(id) {
  activeDrawerId = id;
  try {
    const res = await apiFetch(`${API_BASE}/api/escalations/${id}`);
    const r = await res.json();

    document.getElementById("drawer-account").textContent =
      `${r.account_name || "Unknown"} — #${r.id}`;
    document.getElementById("drawer-meta").innerHTML =
      `<span class="badge badge-${r.source_channel}">${r.source_channel}</span> &nbsp;
       <span class="dept-badge">${esc(r.assigned_department || "Account Management")}</span> &nbsp;
       Received: ${formatDate(r.received_at)} &nbsp;|&nbsp; Sender: ${esc(r.sender_name || "")} &nbsp;(${esc(r.sender_contact || "")})`;

    document.getElementById("drawer-grid").innerHTML = `
      <div class="drawer-kv"><label>Urgency</label><p><span class="badge badge-${r.urgency?.toLowerCase()}">${r.urgency}</span></p></div>
      <div class="drawer-kv"><label>Priority Score</label><p><span class="priority-score ${priorityClass(r.priority_score)}">${r.priority_score}/10</span></p></div>
      <div class="drawer-kv"><label>Category</label><p>${esc(r.issue_category || "—")}</p></div>
      <div class="drawer-kv"><label>Sentiment</label><p>${esc(r.sentiment || "—")}</p></div>
      <div class="drawer-kv"><label>Status</label><p>${esc(r.status)}</p></div>
      <div class="drawer-kv"><label>Owner</label><p>${esc(r.owner || "Unassigned")}</p></div>
      <div class="drawer-kv"><label>SLA Deadline</label><p>${formatDate(r.sla_deadline_at)}</p></div>
      <div class="drawer-kv"><label>TAT</label><p>${computeTAT(r.created_at, r.closed_at)}</p></div>
      ${r.vp_check ? `<div class="drawer-kv">
        <label>VP Check</label>
        <p><span class="vp-check-badge">✔ Flagged for VP Review</span></p>
      </div>` : ""}
      ${r.vp_watch ? `<div class="drawer-kv" style="grid-column:span 2;">
        <label>VP Watch</label>
        <p style="color:#dc2626;font-weight:700;">
          👁 Senior team watching
          ${r.vp_urgency_override ? ` &nbsp;<span class="vp-urgency-badge ${r.vp_urgency_override.toLowerCase()}">${r.vp_urgency_override === 'CRITICAL' ? '🔴' : r.vp_urgency_override === 'HIGH' ? '🟠' : '🟡'} ${r.vp_urgency_override}</span>` : ""}
          ${r.vp_escalate_dept ? ` &nbsp;→ <span class="dept-badge" style="background:#ede9fe;color:#6d28d9;">${esc(r.vp_escalate_dept)}</span>` : ""}
          ${r.vp_watch_note ? `<br><span style="font-size:12px;font-weight:400;color:#7c3aed;font-style:italic;">"${esc(r.vp_watch_note)}"</span>` : ""}
        </p>
      </div>` : ""}
    `;

    document.getElementById("drawer-raw").textContent     = r.raw_message || "—";
    document.getElementById("drawer-summary").textContent = r.ai_summary   || "—";
    document.getElementById("drawer-action").textContent  = r.action_needed || "—";
    document.getElementById("drawer-notes").value         = r.resolution_notes || "";

    document.getElementById("drawer").classList.add("open");
    document.getElementById("drawer-overlay").classList.add("open");
  } catch(e) {
    console.error("Drawer fetch failed:", e);
  }
}

function closeDrawer() {
  activeDrawerId = null;
  document.getElementById("drawer").classList.remove("open");
  document.getElementById("drawer-overlay").classList.remove("open");
}

async function saveNotes() {
  if (!activeDrawerId) return;
  const notes = document.getElementById("drawer-notes").value;
  await updateField(activeDrawerId, "resolution_notes", notes, false);
}

// ── Update Field (owner / status / notes) ─────────
async function updateField(id, field, value, doRefresh = true) {
  try {
    await apiFetch(`${API_BASE}/api/escalations/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [field]: value }),
    });
    if (doRefresh) {
      fetchStats();
      applyFilters();
    }
  } catch(e) {
    console.error("Update failed:", e);
  }
}

// ── Owner Filter Dropdown ─────────────────────────
function populateOwnerFilter(rows) {
  const owners = [...new Set(rows.map(r => r.owner).filter(o => o && o !== "Unassigned"))];
  const sel = document.getElementById("filter-owner");
  const current = sel.value;
  sel.innerHTML = `<option value="">All Owners</option>` +
    owners.map(o => `<option value="${o}" ${o===current?"selected":""}>${o}</option>`).join("");
}

// ── Utility Functions ─────────────────────────────
function computeTAT(createdAt, closedAt) {
  const start = new Date(createdAt);
  const end   = closedAt ? new Date(closedAt) : new Date();
  const diffMs = end - start;
  if (isNaN(diffMs) || diffMs < 0) return "—";
  const totalMins = Math.floor(diffMs / 60000);
  const hours = Math.floor(totalMins / 60);
  const mins  = totalMins % 60;
  if (hours === 0) return `${mins}m`;
  if (hours < 24)  return `${hours}h ${mins}m`;
  const days = Math.floor(hours / 24);
  return `${days}d ${hours % 24}h`;
}

function isSLABreached(r) {
  if (!r.sla_deadline_at) return false;
  return new Date(r.sla_deadline_at) < new Date();
}

function slaTag(r) {
  if (r.status === "Closed") return `<span class="sla-ok">Closed</span>`;
  if (isSLABreached(r)) return `<span class="sla-breached-badge">BREACHED</span>`;
  const deadline = new Date(r.sla_deadline_at);
  const hoursLeft = Math.round((deadline - new Date()) / 3600000);
  if (hoursLeft < 2) return `<span style="font-size:11px;color:#d97706;font-weight:700;">⚠ ${hoursLeft}h left</span>`;
  return `<span class="sla-ok">${formatDate(r.sla_deadline_at, true)}</span>`;
}

function formatDate(iso, short = false) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (short) return d.toLocaleDateString("en-IN", { day:"2-digit", month:"short" }) + " " +
                      d.toLocaleTimeString("en-IN", { hour:"2-digit", minute:"2-digit" });
    return d.toLocaleDateString("en-IN", { day:"2-digit", month:"short", year:"numeric" }) + " " +
           d.toLocaleTimeString("en-IN", { hour:"2-digit", minute:"2-digit" });
  } catch { return iso; }
}

function priorityClass(score) {
  if (score >= 8) return "priority-high";
  if (score >= 5) return "priority-medium";
  return "priority-low";
}

function statusClass(status) {
  const map = {
    "Open":        "status-open",
    "In Progress": "status-inprogress",
    "Blocked":     "status-blocked",
    "Closed":      "status-closed",
  };
  return map[status] || "status-open";
}

function esc(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── Connect Sources (Settings Modal) ──────────

let _sourceRefreshTimer = null;

function openSettings() {
  loadSourceStatus();
  document.getElementById("settings-overlay").classList.add("open");
  document.getElementById("settings-modal").classList.add("open");
  // Auto-refresh status every 15s while modal is open
  _sourceRefreshTimer = setInterval(loadSourceStatus, 15000);
}

function closeSettings() {
  document.getElementById("settings-overlay").classList.remove("open");
  document.getElementById("settings-modal").classList.remove("open");
  if (_sourceRefreshTimer) { clearInterval(_sourceRefreshTimer); _sourceRefreshTimer = null; }
}

async function loadSourceStatus() {
  try {
    const res = await apiFetch(`${API_BASE}/api/sources`);
    if (!res.ok) return;
    const data = await res.json();
    renderGmailChips(data.gmail || []);
    renderSlackChips(data.slack?.channels || []);
    renderStatusBadge("gmail-status-badge", data.gmail || []);
    renderStatusBadge("slack-status-badge", data.slack?.channels || []);
  } catch(e) {
    console.warn("[Sources] Could not load status:", e.message);
  }
}

function renderStatusBadge(elementId, items) {
  const el = document.getElementById(elementId);
  if (!el) return;
  if (items.length === 0) { el.innerHTML = ""; return; }
  const connected = items.filter(i => i.is_connected).length;
  const color = connected > 0 ? "green" : "red";
  const label = connected > 0 ? `${connected} connected` : "not connected";
  el.innerHTML = `<span class="status-dot ${color}"></span><span class="status-label">${label}</span>`;
}

function renderGmailChips(accounts) {
  const container = document.getElementById("gmail-chips");
  if (!container) return;
  if (accounts.length === 0) {
    container.innerHTML = `<span style="font-size:12px;color:#9ca3af;">No Gmail connected yet</span>`;
    return;
  }
  container.innerHTML = accounts.map(a => {
    const dot = a.is_connected ? "green" : a.error ? "red" : "grey";
    const info = a.is_connected
      ? `${a.messages_fetched} msgs · last ${formatRelative(a.last_polled_at)}`
      : (a.error || "not polled yet");
    return `<span class="source-chip">
      <span class="status-dot ${dot}"></span>
      ${esc(a.email)}
      <span style="font-size:10px;color:#9ca3af;margin-left:4px;">${esc(info)}</span>
      <button onclick="disconnectGmail('${a.email.replace(/'/g,"\\'")}')">✕</button>
    </span>`;
  }).join("");
}

function renderSlackChips(channels) {
  const container = document.getElementById("slack-chips");
  if (!container) return;
  if (channels.length === 0) {
    container.innerHTML = `<span style="font-size:12px;color:#9ca3af;">No Slack channels connected yet</span>`;
    return;
  }
  container.innerHTML = channels.map(c => {
    const dot = c.is_connected ? "green" : c.error ? "red" : "grey";
    const info = c.is_connected
      ? `${c.messages_fetched} msgs · last ${formatRelative(c.last_polled_at)}`
      : (c.error || "not polled yet");
    return `<span class="source-chip">
      <span class="status-dot ${dot}"></span>
      ${esc(c.channel_name || c.channel_id)}
      <span style="font-size:10px;color:#9ca3af;margin-left:4px;">${esc(info)}</span>
      <button onclick="disconnectSlackChannel('${c.channel_id}')">✕</button>
    </span>`;
  }).join("");
}

function showTestResult(elId, ok, msg) {
  const el = document.getElementById(elId);
  if (!el) return;
  el.style.cssText = `font-size:12px;padding:6px 10px;border-radius:6px;margin-bottom:8px;
    background:${ok ? "#f0fdf4" : "#fef2f2"};color:${ok ? "#166534" : "#dc2626"};
    border:1px solid ${ok ? "#bbf7d0" : "#fecaca"};`;
  el.textContent = (ok ? "✓ " : "✗ ") + msg;
}

async function testGmail() {
  const email = document.getElementById("gmail-email-input").value.trim();
  const pass  = document.getElementById("gmail-pass-input").value.trim();
  if (!email || !pass) { showTestResult("gmail-test-result", false, "Enter email and App Password first."); return; }
  showTestResult("gmail-test-result", true, "Testing connection...");
  try {
    const res = await apiFetch(`${API_BASE}/api/sources/test/gmail`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, app_password: pass }),
    });
    const data = await res.json();
    if (data.ok) {
      showTestResult("gmail-test-result", true, `Connected! Inbox has ${data.inbox_count} messages. Click Connect to start polling.`);
    } else {
      showTestResult("gmail-test-result", false, data.error || "Connection failed.");
    }
  } catch(e) { showTestResult("gmail-test-result", false, "Cannot reach server: " + e.message); }
}

async function testSlack() {
  const token = document.getElementById("slack-token-input").value.trim();
  if (!token) { showTestResult("slack-test-result", false, "Enter a Bot Token first."); return; }
  showTestResult("slack-test-result", true, "Testing token...");
  try {
    const res = await apiFetch(`${API_BASE}/api/sources/test/slack`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bot_token: token }),
    });
    const data = await res.json();
    if (data.ok) {
      showTestResult("slack-test-result", true, `Connected to workspace "${data.workspace}" as @${data.bot_name}. Now add channel IDs below.`);
    } else {
      showTestResult("slack-test-result", false, data.error || "Token invalid.");
    }
  } catch(e) { showTestResult("slack-test-result", false, "Cannot reach server: " + e.message); }
}

async function connectGmail() {
  const email = document.getElementById("gmail-email-input").value.trim();
  const pass  = document.getElementById("gmail-pass-input").value.trim();
  if (!email || !pass) { showTestResult("gmail-test-result", false, "Enter both Gmail address and App Password."); return; }
  try {
    const res = await apiFetch(`${API_BASE}/api/sources/gmail`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, app_password: pass }),
    });
    if (res.ok) {
      document.getElementById("gmail-email-input").value = "";
      document.getElementById("gmail-pass-input").value = "";
      document.getElementById("gmail-test-result").textContent = "";
      showToast(`Gmail ${email} connected — polling every 2 min`);
      loadSourceStatus();
    } else {
      const errText = await res.text();
      showTestResult("gmail-test-result", false, `Error ${res.status}: ${errText}`);
    }
  } catch(e) { showTestResult("gmail-test-result", false, "Cannot reach server: " + e.message); }
}

async function disconnectGmail(email) {
  if (!confirm(`Remove ${email}?`)) return;
  await apiFetch(`${API_BASE}/api/sources/gmail/${encodeURIComponent(email)}`, { method: "DELETE" });
  loadSourceStatus();
}

async function connectSlack() {
  const token   = document.getElementById("slack-token-input").value.trim();
  const channel = document.getElementById("slack-channel-input").value.trim();
  const name    = document.getElementById("slack-channel-name-input").value.trim();
  if (!token) { showTestResult("slack-test-result", false, "Enter a Bot Token first."); return; }
  if (!channel) { showTestResult("slack-test-result", false, "Enter a Channel ID (e.g. C01234ABCD)."); return; }
  try {
    const res = await apiFetch(`${API_BASE}/api/sources/slack`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bot_token: token, channel_id: channel, channel_name: name || channel }),
    });
    if (res.ok) {
      document.getElementById("slack-channel-input").value = "";
      document.getElementById("slack-channel-name-input").value = "";
      showToast(`Slack channel ${name || channel} added — polling every 30s`);
      loadSourceStatus();
    } else {
      showTestResult("slack-test-result", false, "Failed to save. Is the server running?");
    }
  } catch(e) { showTestResult("slack-test-result", false, "Cannot reach server: " + e.message); }
}

async function disconnectSlackChannel(channelId) {
  if (!confirm(`Remove channel ${channelId}?`)) return;
  await apiFetch(`${API_BASE}/api/sources/slack/${channelId}`, { method: "DELETE" });
  loadSourceStatus();
}

function formatRelative(iso) {
  if (!iso) return "never";
  const diff = Math.floor((Date.now() - new Date(iso)) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  return `${Math.floor(diff/3600)}h ago`;
}

// ── Upload / Paste Modal ───────────────────────
let csvRows = [];
let detectedHeaders = [];
let rawDataRows = [];

function openUpload() {
  csvRows = []; detectedHeaders = []; rawDataRows = [];
  clearFile();
  switchUploadTab("file");
  document.getElementById("upload-overlay").classList.add("open");
  document.getElementById("upload-modal").classList.add("open");
}

function closeUpload() {
  document.getElementById("upload-overlay").classList.remove("open");
  document.getElementById("upload-modal").classList.remove("open");
  document.getElementById("upload-progress").style.display = "none";
  document.getElementById("progress-bar").style.width = "0%";
}

function switchUploadTab(tab) {
  document.getElementById("upload-tab-file").style.display  = tab === "file"  ? "block" : "none";
  document.getElementById("upload-tab-paste").style.display = tab === "paste" ? "block" : "none";
  document.getElementById("utab-file").className  = "upload-tab" + (tab === "file"  ? " active" : "");
  document.getElementById("utab-paste").className = "upload-tab" + (tab === "paste" ? " active" : "");
}

// ── File handling ──────────────────────────────
function handleDrop(e) {
  e.preventDefault();
  document.getElementById("upload-zone").classList.remove("drag-over");
  const file = e.dataTransfer.files[0];
  if (file) readFile(file);
}

function handleFileSelect(e) {
  const file = e.target.files[0];
  if (file) readFile(file);
}

function readFile(file) {
  const reader = new FileReader();
  reader.onload = (e) => processRawText(e.target.result, file.name);
  reader.readAsText(file);
}

// ── Paste handling ─────────────────────────────
function parsePastedData() {
  const text = document.getElementById("paste-input").value.trim();
  if (!text) { alert("Please paste some data first."); return; }
  processRawText(text, "paste");
}

// ── Core parser — handles CSV, TSV, JSON ───────
function processRawText(text, source) {
  text = text.trim();
  let headers = [], rows = [];

  // 1. JSON array
  if (text.startsWith("[") || text.startsWith("{")) {
    try {
      let parsed = JSON.parse(text);
      if (!Array.isArray(parsed)) parsed = [parsed];
      if (parsed.length === 0) { alert("JSON array is empty."); return; }
      headers = Object.keys(parsed[0]);
      rows = parsed.map(obj => headers.map(h => String(obj[h] ?? "")));
    } catch(e) {
      alert("Looks like JSON but could not parse it. Check for syntax errors.");
      return;
    }
  }
  // 2. TSV (tab-separated, e.g. Excel paste)
  else if (text.includes("\t")) {
    const lines = text.split(/\r?\n/).filter(l => l.trim());
    headers = lines[0].split("\t").map(h => h.trim().replace(/^"|"$/g, ""));
    rows = lines.slice(1).map(l => l.split("\t").map(c => c.trim().replace(/^"|"$/g, "")));
  }
  // 3. CSV
  else {
    const lines = text.split(/\r?\n/).filter(l => l.trim());
    if (lines.length < 2) { alert("Need at least a header row and one data row."); return; }
    headers = parseDelimitedLine(lines[0], ",").map(h => h.trim().replace(/^"|"$/g, ""));
    rows = lines.slice(1).map(l => parseDelimitedLine(l, ",").map(c => c.trim().replace(/^"|"$/g, "")));
  }

  rows = rows.filter(r => r.some(c => c.length > 0));
  if (rows.length === 0) { alert("No data rows found."); return; }

  detectedHeaders = headers;
  rawDataRows = rows;

  // Check if headers already match our schema exactly
  const headersLower = headers.map(h => h.toLowerCase().trim());
  const required = ["source_channel","sender_name","sender_contact","raw_message"];
  const allMatch = required.every(r => headersLower.includes(r));

  if (allMatch) {
    // Direct convert — no mapping needed
    csvRows = rows.map(cols => {
      const row = {};
      headers.forEach((h, i) => { row[h.toLowerCase().trim()] = cols[i] || ""; });
      return row;
    }).filter(r => r.raw_message);
    hideMapper();
    renderPreview();
  } else {
    showColumnMapper(headers);
  }
}

function parseDelimitedLine(line, delim) {
  const result = [];
  let inQuotes = false, current = "";
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') { inQuotes = !inQuotes; }
    else if (ch === delim && !inQuotes) { result.push(current); current = ""; }
    else { current += ch; }
  }
  result.push(current);
  return result;
}

// ── Column Mapper ──────────────────────────────
const FIELD_DEFS = [
  { key: "source_channel",    label: "Channel",        req: true,  hint: "gmail / slack / whatsapp" },
  { key: "sender_name",       label: "Sender Name",    req: true,  hint: "person who sent the message" },
  { key: "sender_contact",    label: "Sender Contact", req: true,  hint: "email, phone, or Slack handle" },
  { key: "raw_message",       label: "Message Body",   req: true,  hint: "the full message text" },
  { key: "received_at",       label: "Received At",    req: false, hint: "timestamp (optional)" },
  { key: "source_message_id", label: "Message ID",     req: false, hint: "unique ID (optional)" },
];

// Synonyms for better auto-matching
const FIELD_SYNONYMS = {
  source_channel:    ["channel","source","type","platform","via","medium"],
  sender_name:       ["name","from","sender","person","contact","user","who","fullname","full_name"],
  sender_contact:    ["email","contact","phone","handle","address","mobile","gmail","id","account"],
  raw_message:       ["message","body","text","content","complaint","description","msg","issue","detail","comment"],
  received_at:       ["date","time","timestamp","received","sent","created","at","datetime"],
  source_message_id: ["id","msgid","message_id","uid","ref","ticket","ticket_id"],
};

function autoMatchColumn(headers, fieldKey) {
  const hl = headers.map(h => h.toLowerCase().replace(/[\s_\-\.]/g, ""));
  const fk = fieldKey.replace(/_/g, "");
  const synonyms = (FIELD_SYNONYMS[fieldKey] || []).map(s => s.replace(/[\s_\-]/g, ""));

  // Exact match first
  let idx = hl.findIndex(h => h === fk);
  if (idx >= 0) return idx;

  // Synonym exact match
  for (const syn of synonyms) {
    idx = hl.findIndex(h => h === syn);
    if (idx >= 0) return idx;
  }

  // Contains match
  idx = hl.findIndex(h => h.includes(fk) || fk.includes(h));
  if (idx >= 0) return idx;

  // Synonym contains
  for (const syn of synonyms) {
    idx = hl.findIndex(h => h.includes(syn) || syn.includes(h));
    if (idx >= 0) return idx;
  }

  return -1;
}

function showColumnMapper(headers) {
  // Show detected columns as chips
  const chipsEl = document.getElementById("mapper-detected-chips");
  chipsEl.innerHTML = `<div class="mapper-detected-label">Columns detected in your file (${headers.length}):</div>`
    + headers.map(h => `<span class="mapper-col-chip">${esc(h)}</span>`).join("");

  const grid = document.getElementById("mapper-grid");

  grid.innerHTML = FIELD_DEFS.map(f => {
    const autoIdx = autoMatchColumn(headers, f.key);
    const isMapped = autoIdx >= 0;

    // Build options with sample value in label
    const opts = [`<option value="">— skip this field —</option>`];
    headers.forEach((h, i) => {
      const sample = rawDataRows[0]?.[i] || "";
      const preview = sample ? ` · "${sample.substring(0,20)}${sample.length>20?"…":""}"` : "";
      const sel = i === autoIdx ? " selected" : "";
      opts.push(`<option value="${i}"${sel}>${esc(h)}${preview}</option>`);
    });

    // Sample value from auto-matched column
    const sampleVal = autoIdx >= 0 && rawDataRows[0] ? rawDataRows[0][autoIdx] : "";
    const sampleHtml = sampleVal
      ? `<div class="mapper-sample">e.g. "${esc(sampleVal.substring(0,40))}"</div>`
      : "";

    // Fixed value for source_channel
    const fixedHtml = f.key === "source_channel"
      ? `<div class="mapper-fixed-wrap">
           <label>or fixed:</label>
           <select id="fix-${f.key}">
             <option value="">—</option>
             <option value="gmail">gmail</option>
             <option value="slack">slack</option>
             <option value="whatsapp">whatsapp</option>
           </select>
         </div>` : "";

    const statusIcon = isMapped ? "✅" : (f.req ? "⚠️" : "➖");
    const rowClass = isMapped ? "mapped" : (f.req ? "unmapped" : "");

    return `<div class="mapper-row ${rowClass}">
      <div class="mapper-field-info">
        <div class="mapper-field-name">
          ${esc(f.label)} ${f.req ? '<span class="req">*</span>' : '<span style="font-size:10px;color:#9ca3af;">opt</span>'}
        </div>
        <div class="mapper-field-hint">${esc(f.hint)}</div>
      </div>
      <div class="mapper-select-wrap">
        <select id="map-${f.key}" onchange="updateMapperRow(this, '${f.key}')">${opts.join("")}</select>
        ${sampleHtml}
        ${fixedHtml}
      </div>
      <div class="mapper-status" id="status-${f.key}">${statusIcon}</div>
    </div>`;
  }).join("");

  document.getElementById("col-mapper").style.display = "block";
  document.getElementById("upload-preview").style.display = "none";
  document.getElementById("btn-ingest").disabled = true;
}

function updateMapperRow(selectEl, fieldKey) {
  const statusEl = document.getElementById(`status-${fieldKey}`);
  const rowEl = selectEl.closest(".mapper-row");
  const f = FIELD_DEFS.find(f => f.key === fieldKey);
  const isMapped = selectEl.value !== "";

  // Update sample value
  const idx = parseInt(selectEl.value);
  const sampleEl = rowEl.querySelector(".mapper-sample");
  if (sampleEl) {
    const sample = (!isNaN(idx) && rawDataRows[0]) ? rawDataRows[0][idx] : "";
    sampleEl.textContent = sample ? `e.g. "${sample.substring(0,40)}"` : "";
  }

  if (isMapped) {
    statusEl.textContent = "✅";
    rowEl.className = "mapper-row mapped";
  } else {
    statusEl.textContent = f?.req ? "⚠️" : "➖";
    rowEl.className = "mapper-row" + (f?.req ? " unmapped" : "");
  }
}

function hideMapper() {
  document.getElementById("col-mapper").style.display = "none";
}

function applyMapping() {
  csvRows = rawDataRows.map(cols => {
    const row = {};
    FIELD_DEFS.forEach(f => {
      const sel = document.getElementById(`map-${f.key}`);
      const fixSel = document.getElementById(`fix-${f.key}`);
      const colIdx = sel ? parseInt(sel.value) : NaN;
      if (!isNaN(colIdx) && colIdx >= 0) {
        row[f.key] = (cols[colIdx] || "").trim();
      } else if (fixSel && fixSel.value) {
        row[f.key] = fixSel.value;
      } else {
        row[f.key] = "";
      }
    });
    return row;
  }).filter(r => r.raw_message && r.raw_message.length > 0);

  if (csvRows.length === 0) {
    alert("No rows have a message body after mapping. Check that 'Message Body' is mapped to the right column.");
    return;
  }

  hideMapper();
  renderPreview();
}

// ── Preview & Ingest ───────────────────────────
function renderPreview() {
  if (csvRows.length === 0) {
    alert("No valid rows found.");
    return;
  }
  document.getElementById("preview-count").textContent = `${csvRows.length} rows ready to ingest`;
  const tbody = document.getElementById("preview-tbody");
  tbody.innerHTML = csvRows.slice(0, 10).map((r, i) => `<tr>
    <td>${i + 1}</td>
    <td><span class="badge badge-${r.source_channel || 'gmail'}">${esc(r.source_channel || "?")}</span></td>
    <td>${esc(r.sender_name || "?")}</td>
    <td style="font-size:11px;">${esc(r.sender_contact || "?")}</td>
    <td>${esc((r.raw_message || "").substring(0, 60))}${(r.raw_message || "").length > 60 ? "…" : ""}</td>
  </tr>`).join("");
  if (csvRows.length > 10) {
    tbody.innerHTML += `<tr><td colspan="5" style="text-align:center;color:#9ca3af;font-style:italic;">...and ${csvRows.length - 10} more rows</td></tr>`;
  }
  document.getElementById("upload-preview").style.display = "block";
  document.getElementById("btn-ingest").disabled = false;
  document.getElementById("btn-ingest").textContent = `Ingest ${csvRows.length} Rows →`;
}

function clearFile() {
  csvRows = []; detectedHeaders = []; rawDataRows = [];
  document.getElementById("upload-preview").style.display = "none";
  document.getElementById("upload-progress").style.display = "none";
  document.getElementById("col-mapper").style.display = "none";
  const fi = document.getElementById("csv-file-input");
  if (fi) fi.value = "";
  const pi = document.getElementById("paste-input");
  if (pi) pi.value = "";
  document.getElementById("btn-ingest").disabled = true;
  document.getElementById("btn-ingest").textContent = "Ingest Rows →";
}

async function ingestCSV() {
  if (csvRows.length === 0) return;
  document.getElementById("btn-ingest").disabled = true;
  document.getElementById("upload-preview").style.display = "none";
  document.getElementById("upload-progress").style.display = "block";

  let success = 0, failed = 0;
  for (let i = 0; i < csvRows.length; i++) {
    const r = csvRows[i];
    document.getElementById("progress-bar").style.width = Math.round(((i + 1) / csvRows.length) * 100) + "%";
    document.getElementById("progress-text").textContent =
      `Ingesting row ${i + 1} of ${csvRows.length}... (${success} done, ${failed} failed)`;
    try {
      const res = await fetch(`${API_BASE}/webhook/ingest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_channel:    r.source_channel    || "gmail",
          source_message_id: r.source_message_id || `up-${Date.now()}-${i}`,
          received_at:       r.received_at        || new Date().toISOString(),
          sender_name:       r.sender_name        || "Unknown",
          sender_contact:    r.sender_contact     || "",
          raw_message:       r.raw_message        || "",
        }),
      });
      if (res.ok) success++; else failed++;
    } catch { failed++; }
  }

  document.getElementById("progress-text").textContent =
    `Done! ${success} ingested${failed > 0 ? `, ${failed} failed` : ""}. Refreshing dashboard...`;
  document.getElementById("progress-bar").style.width = "100%";
  setTimeout(() => { closeUpload(); refreshAll(); }, 1800);
}

// ── Clear Data Modal ───────────────────────────
function exportCSV() {
  // Build query params from current filters
  const status  = document.getElementById("filter-status")?.value  || "";
  const urgency = document.getElementById("filter-urgency")?.value || "";
  const owner   = document.getElementById("filter-owner")?.value   || "";
  const tab     = document.querySelector(".tab-btn.active")?.dataset.tab;

  let url = `${API_BASE}/api/export/csv?`;
  if (status)  url += `status=${encodeURIComponent(status)}&`;
  if (urgency) url += `urgency=${encodeURIComponent(urgency)}&`;
  if (owner)   url += `owner=${encodeURIComponent(owner)}&`;
  if (tab === "escalations")     url += `is_escalation=1&`;
  if (tab === "non-escalations") url += `is_escalation=0&`;

  // Trigger download
  const a = document.createElement("a");
  a.href = url;
  a.download = "";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  showToast("CSV download started");
}

function openClearModal() {
  document.getElementById("clear-confirm-row").style.display = "none";
  document.getElementById("clear-confirm-input").value = "";
  document.querySelector('input[name="clear-scope"][value="today"]').checked = true;
  document.getElementById("clear-overlay").classList.add("open");
  document.getElementById("clear-modal").classList.add("open");

  // Show confirm input only for "all" scope
  document.querySelectorAll('input[name="clear-scope"]').forEach(r => {
    r.addEventListener("change", () => {
      document.getElementById("clear-confirm-row").style.display =
        r.value === "all" ? "block" : "none";
    });
  });
}

function closeClearModal() {
  document.getElementById("clear-overlay").classList.remove("open");
  document.getElementById("clear-modal").classList.remove("open");
}

async function executeClears() {
  const selected = document.querySelector('input[name="clear-scope"]:checked');
  const scope = selected ? selected.value : "all";

  // Require typing DELETE for full reset
  if (scope === "all") {
    const val = document.getElementById("clear-confirm-input").value.trim();
    if (val !== "DELETE") {
      alert('Type DELETE (all caps) to confirm full reset.');
      return;
    }
  }

  const btn = document.getElementById("btn-do-clear");
  btn.disabled = true;
  btn.textContent = "Deleting...";

  try {
    let url;
    if (scope.startsWith("channel-")) {
      const ch = scope.replace("channel-", "");
      url = `${API_BASE}/api/escalations?scope=channel&channel=${encodeURIComponent(ch)}`;
    } else {
      url = `${API_BASE}/api/escalations?scope=${encodeURIComponent(scope)}`;
    }

    const res = await apiFetch(url, { method: "DELETE" });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(`Server error ${res.status}: ${err}`);
    }
    const data = await res.json();
    closeClearModal();
    await refreshAll();
    showToast(`Deleted ${data.deleted} record${data.deleted !== 1 ? "s" : ""}`);
  } catch(e) {
    alert("Delete failed: " + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Delete Records";
  }
}

function showToast(msg) {
  let toast = document.getElementById("toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "toast";
    toast.style.cssText = "position:fixed;bottom:24px;right:24px;background:#1e3a5f;color:white;padding:10px 18px;border-radius:8px;font-size:13px;font-weight:600;z-index:9999;box-shadow:0 4px 12px rgba(0,0,0,0.2);transition:opacity 0.4s;";
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.style.opacity = "1";
  setTimeout(() => { toast.style.opacity = "0"; }, 2500);
}

// ── Analytics / Charts ────────────────────────────
let _charts = {};
let _analyticsPluginsRegistered = false;

function _registerChartPlugins() {
  if (_analyticsPluginsRegistered) return;
  _analyticsPluginsRegistered = true;

  // Center-text plugin for doughnut charts
  Chart.register({
    id: "doughnutCenter",
    afterDraw(chart) {
      if (chart.config.type !== "doughnut") return;
      const meta = chart.getDatasetMeta(0);
      if (!meta || !meta.data || meta.data.length === 0) return;
      const { ctx } = chart;
      const cx = meta.data[0].x;
      const cy = meta.data[0].y;
      const total = chart.data.datasets[0].data.reduce((a, b) => a + (b || 0), 0);
      ctx.save();
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.font = "bold 24px Inter, Segoe UI, sans-serif";
      ctx.fillStyle = "#1a1a2e";
      ctx.fillText(total, cx, cy - 10);
      ctx.font = "11px Inter, Segoe UI, sans-serif";
      ctx.fillStyle = "#9ca3af";
      ctx.fillText("total", cx, cy + 12);
      ctx.restore();
    },
  });
}

function _destroyChart(id) {
  if (_charts[id]) { _charts[id].destroy(); delete _charts[id]; }
}

function _setBadge(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function _makeGradient(canvas, hex, opacity = 0.45) {
  const ctx = canvas.getContext("2d");
  const grad = ctx.createLinearGradient(0, 0, 0, canvas.offsetHeight || 220);
  const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
  grad.addColorStop(0, `rgba(${r},${g},${b},${opacity})`);
  grad.addColorStop(1, `rgba(${r},${g},${b},0)`);
  return grad;
}

const _TOOLTIP_DEFAULTS = {
  backgroundColor: "rgba(15,23,42,0.92)",
  titleColor: "#f8fafc",
  bodyColor: "#cbd5e1",
  padding: 10,
  cornerRadius: 8,
  borderColor: "rgba(255,255,255,0.08)",
  borderWidth: 1,
  displayColors: true,
  boxWidth: 10,
  boxHeight: 10,
};

async function loadAnalytics() {
  _registerChartPlugins();
  try {
    const [statsRes, trendRes] = await Promise.all([
      apiFetch(`${API_BASE}/api/stats`),
      apiFetch(`${API_BASE}/api/stats/trend?days=7`),
    ]);
    const stats = await statsRes.json();
    const trend = await trendRes.json();

    renderAnalyticsSummary(stats);
    renderDeptChart(stats.by_department || {});
    renderUrgencyChart(stats.by_urgency || {});
    renderChannelChart(stats.by_channel || {});
    renderStatusChart(stats.by_status || {});
    renderTrendChart(trend.days || []);
  } catch(e) {
    console.error("[Analytics] failed:", e.message);
  }
}

function renderAnalyticsSummary(stats) {
  const bar = document.getElementById("analytics-summary-row");
  if (!bar) return;
  const total = stats.total || 0;
  const high  = stats.high_priority || 0;
  const sla   = stats.sla_breached || 0;
  const closed = stats.closed_today || 0;
  bar.innerHTML = `
    <div class="asummary-item">
      <span class="asummary-val">${total}</span>
      <span class="asummary-label">Total Escalations</span>
    </div>
    <div class="asummary-item red">
      <span class="asummary-val">${high}</span>
      <span class="asummary-label">High Priority</span>
    </div>
    <div class="asummary-item orange">
      <span class="asummary-val">${sla}</span>
      <span class="asummary-label">SLA Breached</span>
    </div>
    <div class="asummary-item green">
      <span class="asummary-val">${closed}</span>
      <span class="asummary-label">Closed Today</span>
    </div>
    ${stats.sla_resolution_rate != null ? `
    <div class="asummary-item blue">
      <span class="asummary-val">${stats.sla_resolution_rate}%</span>
      <span class="asummary-label">SLA Resolution Rate</span>
    </div>` : ""}
  `;
}

function renderDeptChart(byDept) {
  _destroyChart("dept");
  const labels = Object.keys(byDept);
  const values = Object.values(byDept);
  const total  = values.reduce((a, b) => a + b, 0);
  const colors = ["#3b82f6","#8b5cf6","#ec4899","#f97316","#22c55e","#06b6d4","#f59e0b","#ef4444","#64748b"];
  _setBadge("cbadge-dept", `${total} total`);
  const ctx = document.getElementById("chart-dept");
  if (!ctx) return;
  _charts["dept"] = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: colors.slice(0, labels.length),
        borderWidth: 3,
        borderColor: "#fff",
        hoverOffset: 6,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      cutout: "66%",
      animation: { animateRotate: true, duration: 700 },
      plugins: {
        tooltip: { ..._TOOLTIP_DEFAULTS, callbacks: {
          label: ctx => ` ${ctx.label}: ${ctx.parsed} (${Math.round(ctx.parsed/total*100)}%)`,
        }},
        legend: { position: "right", labels: { boxWidth: 10, boxHeight: 10, padding: 10, font: { size: 11 } } },
      },
    },
  });
}

function renderUrgencyChart(byUrgency) {
  _destroyChart("urgency");
  const order = ["High","Medium","Low"];
  const labels = order.filter(k => byUrgency[k] != null);
  const values = labels.map(k => byUrgency[k]);
  const total  = values.reduce((a, b) => a + b, 0);
  const COLORS = { High: "#ef4444", Medium: "#f97316", Low: "#22c55e" };
  _setBadge("cbadge-urgency", `${total} total`);
  const ctx = document.getElementById("chart-urgency");
  if (!ctx) return;
  _charts["urgency"] = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: labels.map(l => COLORS[l]),
        borderWidth: 3,
        borderColor: "#fff",
        hoverOffset: 6,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      cutout: "66%",
      animation: { animateRotate: true, duration: 700 },
      plugins: {
        tooltip: { ..._TOOLTIP_DEFAULTS, callbacks: {
          label: ctx => ` ${ctx.label}: ${ctx.parsed} (${Math.round(ctx.parsed/total*100)}%)`,
        }},
        legend: { position: "right", labels: { boxWidth: 10, boxHeight: 10, padding: 12, font: { size: 12 }, generateLabels: chart => {
          const ds = chart.data.datasets[0];
          return chart.data.labels.map((label, i) => ({
            text: `${label}  ${ds.data[i]}`,
            fillStyle: ds.backgroundColor[i],
            strokeStyle: "#fff",
            lineWidth: 2,
            index: i,
          }));
        }}},
      },
    },
  });
}

function renderChannelChart(byChannel) {
  _destroyChart("channel");
  const CH_COLORS = { gmail: "#f59e0b", slack: "#8b5cf6", whatsapp: "#22c55e" };
  const CH_BG     = { gmail: "#fef3c7", slack: "#ede9fe", whatsapp: "#dcfce7" };
  const labels = Object.keys(byChannel);
  const values = Object.values(byChannel);
  const total  = values.reduce((a, b) => a + b, 0);
  _setBadge("cbadge-channel", `${total} messages`);
  const ctx = document.getElementById("chart-channel");
  if (!ctx) return;
  _charts["channel"] = new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels.map(l => l.charAt(0).toUpperCase() + l.slice(1)),
      datasets: [{
        label: "Messages",
        data: values,
        backgroundColor: labels.map(l => CH_BG[l] || "#e0f2fe"),
        borderColor: labels.map(l => CH_COLORS[l] || "#0284c7"),
        borderWidth: 2,
        borderRadius: 10,
        borderSkipped: false,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      animation: { duration: 600 },
      plugins: {
        legend: { display: false },
        tooltip: { ..._TOOLTIP_DEFAULTS, callbacks: {
          label: ctx => ` ${ctx.parsed.y} messages (${Math.round(ctx.parsed.y/total*100)}%)`,
        }},
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 12, weight: "600" } } },
        y: { beginAtZero: true, grid: { color: "#f1f5f9" }, ticks: { stepSize: 1, font: { size: 11 } } },
      },
    },
  });
}

function renderStatusChart(byStatus) {
  _destroyChart("status");
  const order = ["Open","In Progress","Blocked","Closed"];
  const labels = order.filter(k => byStatus[k] != null);
  const values = labels.map(k => byStatus[k] || 0);
  const total  = values.reduce((a, b) => a + b, 0);
  const ST_COLORS = { Open: "#3b82f6", "In Progress": "#f59e0b", Blocked: "#ec4899", Closed: "#22c55e" };
  _setBadge("cbadge-status", `${total} total`);
  const ctx = document.getElementById("chart-status");
  if (!ctx) return;
  _charts["status"] = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Cases",
        data: values,
        backgroundColor: labels.map(l => ST_COLORS[l] + "28"),
        borderColor: labels.map(l => ST_COLORS[l]),
        borderWidth: 2,
        borderRadius: 10,
        borderSkipped: false,
      }],
    },
    options: {
      indexAxis: "y",
      responsive: true, maintainAspectRatio: false,
      animation: { duration: 600 },
      plugins: {
        legend: { display: false },
        tooltip: { ..._TOOLTIP_DEFAULTS, callbacks: {
          label: ctx => ` ${ctx.parsed.x} cases (${Math.round(ctx.parsed.x/total*100)}%)`,
        }},
      },
      scales: {
        x: { beginAtZero: true, grid: { color: "#f1f5f9" }, ticks: { stepSize: 1, font: { size: 11 } } },
        y: { grid: { display: false }, ticks: { font: { size: 12, weight: "600" } } },
      },
    },
  });
}

function renderTrendChart(days) {
  _destroyChart("trend");
  const ctx = document.getElementById("chart-trend");
  if (!ctx) return;

  const labels  = days.map(d => new Date(d.date + "T00:00:00")
    .toLocaleDateString("en-IN", { day: "2-digit", month: "short" }));
  const totals  = days.map(d => d.total  || 0);
  const highs   = days.map(d => d.high   || 0);
  const closeds = days.map(d => d.closed || 0);
  const peak    = Math.max(...totals, 1);

  _setBadge("cbadge-trend", `peak: ${peak}`);

  const gTotal  = _makeGradient(ctx, "#3b82f6", 0.35);
  const gHigh   = _makeGradient(ctx, "#ef4444", 0.22);
  const gClosed = _makeGradient(ctx, "#22c55e", 0.22);

  _charts["trend"] = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Total",
          data: totals,
          borderColor: "#3b82f6",
          backgroundColor: gTotal,
          fill: true, tension: 0.4,
          pointRadius: 5, pointBackgroundColor: "#3b82f6",
          pointHoverRadius: 7, borderWidth: 2.5,
        },
        {
          label: "High Urgency",
          data: highs,
          borderColor: "#ef4444",
          backgroundColor: gHigh,
          fill: true, tension: 0.4,
          pointRadius: 4, pointBackgroundColor: "#ef4444",
          pointHoverRadius: 6, borderWidth: 2,
        },
        {
          label: "Closed",
          data: closeds,
          borderColor: "#22c55e",
          backgroundColor: gClosed,
          fill: true, tension: 0.4,
          pointRadius: 4, pointBackgroundColor: "#22c55e",
          pointHoverRadius: 6, borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      animation: { duration: 800 },
      plugins: {
        tooltip: { ..._TOOLTIP_DEFAULTS },
        legend: {
          position: "top",
          labels: { boxWidth: 10, boxHeight: 10, padding: 16, font: { size: 12 }, usePointStyle: true, pointStyle: "circle" },
        },
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 11 } } },
        y: { beginAtZero: true, grid: { color: "#f1f5f9" }, ticks: { stepSize: 1, font: { size: 11 } } },
      },
    },
  });
}
