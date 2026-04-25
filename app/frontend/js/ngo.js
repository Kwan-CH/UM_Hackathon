function getSession() {
  try {
    const raw = localStorage.getItem("ngoSession");
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function setStatus(text, type) {
  const pill = document.getElementById("statusPill");
  if (!pill) return;
  pill.classList.toggle("err", type === "err");
  pill.textContent = text;
}

function setLastUpdated(date) {
  const el = document.getElementById("lastUpdated");
  if (!el) return;
  el.textContent = `Last updated: ${date.toLocaleString()}`;
}

function safe(v) {
  if (v === null || v === undefined) return "—";
  if (typeof v === "string") return v;
  return JSON.stringify(v);
}

function prettyDate(value) {
  const d = value ? new Date(value) : null;
  if (!d || Number.isNaN(d.getTime())) return safe(value);

  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(d);
}

const API_BASE_URL = "http://localhost:8000";
const POLL_MS = 10000;

const session = getSession();
if (!session?.id) {
  window.location.href = "login.html";
}

const ngoTitle = document.getElementById("ngoTitle");
const ngoSub = document.getElementById("ngoSub");
const pendingHeader = document.getElementById("pendingHeader");
const requestList = document.getElementById("requestList");
const emptyState = document.getElementById("emptyState");
const refreshBtn = document.getElementById("refreshBtn");
const logoutBtn = document.getElementById("logoutBtn");

if (ngoTitle) ngoTitle.textContent = `Assigned requests for ${session.name}`;
if (ngoSub) ngoSub.textContent = `${session.email} • ${session.id}`;

let pollingHandle = null;
let inFlight = false;


function renderRequests(requests) {
  if (!requestList || !emptyState) return;

  const list = Array.isArray(requests) ? requests : [];
  const pending = list.filter((r) => (r?.status || "pending") === "pending");

  requestList.innerHTML = "";

  if (pendingHeader) {
    pendingHeader.textContent = `Pending requests (${pending.length})`;
  }

  if (pending.length === 0) {
    emptyState.style.display = "block";
    return;
  }

  emptyState.style.display = "none";

  for (const r of pending) {
    const card = document.createElement("div");
    card.className = "request-card";

    const top = document.createElement("div");
    top.className = "request-top";

    const id = document.createElement("div");
    id.className = "request-id";
    id.textContent = `Request ${safe(r.id)}`;

    const meta = document.createElement("div");
    meta.className = "request-meta";
    meta.textContent = `Created: ${prettyDate(r.created_at)}`;

    top.appendChild(id);
    top.appendChild(meta);

    const grid = document.createElement("div");
    grid.className = "request-grid";

    const foodItems = Array.isArray(r?.food_items) ? r.food_items : [];
    const summary = foodItems.length
      ? foodItems
          .map((it) => `${safe(it.quantity)} ${safe(it.name)}`.trim())
          .join(", ")
      : "—";

    grid.appendChild(field("Restaurant", r?.restaurant_name ?? "—"));
    grid.appendChild(field("Contact", r?.contact_number ?? "—"));
    grid.appendChild(field("Food Items", summary));
    grid.appendChild(field("Pickup Time", prettyDate(r?.pickup_time)));
    grid.appendChild(field("Expiry Time", prettyDate(r?.expiry_time)));
    grid.appendChild(field("Location", r?.location ?? "—"));
    grid.appendChild(field("Distance (km)", r?.distance_km ?? "N/A"));
    grid.appendChild(field("Status", r?.ngo_status ?? "pending"));

    const actions = document.createElement("div");
    actions.className = "request-actions";

    const acceptBtn = document.createElement("button");
    acceptBtn.className = "btn-primary";
    acceptBtn.type = "button";
    acceptBtn.textContent = "Accept";
    acceptBtn.addEventListener("click", () => decide(r, "accept", acceptBtn));

    const rejectBtn = document.createElement("button");
    rejectBtn.className = "btn-danger";
    rejectBtn.type = "button";
    rejectBtn.textContent = "Reject";
    rejectBtn.addEventListener("click", () => decide(r, "reject", rejectBtn));

    actions.appendChild(acceptBtn);
    actions.appendChild(rejectBtn);

    card.appendChild(top);
    card.appendChild(grid);
    card.appendChild(actions);

    requestList.appendChild(card);
  }
}

function field(label, value) {
  const wrap = document.createElement("div");
  wrap.className = "field";

  const k = document.createElement("div");
  k.className = "k";
  k.textContent = label;

  const v = document.createElement("div");
  v.className = "v";
  v.textContent = safe(value);

  wrap.appendChild(k);
  wrap.appendChild(v);
  return wrap;
}

async function fetchRequests() {
  const url = `${API_BASE_URL}/api/ngo/requests?ngo_id=${encodeURIComponent(session.id)}`;
  const res = await fetch(url, { method: "GET" });
  if (!res.ok) throw new Error(`Fetch failed: ${res.status}`);
  const data = await res.json();
  return Array.isArray(data?.requests) ? data.requests : [];
}

async function decide(request, decision, btn) {
  const requestId = request?.request_id || request?.id;
  if (!requestId) return;
  if (btn) btn.disabled = true;

  try {
    setStatus("Submitting decision…", "ok");

    const url = `${API_BASE_URL}/api/ngo/requests/decision`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        request_id: requestId,
        ngo_id: session.id,
        decision
      })
    });

    if (!res.ok) throw new Error(`Decision failed: ${res.status}`);

    await refresh();
    setStatus("Updated.", "ok");
  } catch (e) {
    setStatus(`Error: ${e.message}`, "err");
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function refresh() {
  if (inFlight) return;
  inFlight = true;

  try {
    setStatus("Refreshing…", "ok");
    const requests = await fetchRequests();
    renderRequests(requests);
    setLastUpdated(new Date());
    setStatus("Idle", "ok");
  } catch (e) {
    setStatus(`Error: ${e.message}`, "err");
    renderRequests([]);
  } finally {
    inFlight = false;
  }
}

function startPolling() {
  stopPolling();
  pollingHandle = setInterval(refresh, POLL_MS);
}

function stopPolling() {
  if (!pollingHandle) return;
  clearInterval(pollingHandle);
  pollingHandle = null;
}

if (refreshBtn) refreshBtn.addEventListener("click", refresh);

if (logoutBtn) {
  logoutBtn.addEventListener("click", () => {
    localStorage.removeItem("ngoSession");
    window.location.href = "login.html";
  });
}


refresh();
startPolling();