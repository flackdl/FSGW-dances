"use strict";

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

let DATA = { records: [], years: [], generated: null };
let callersList = [];

const state = {
  query: "",
  year: "all",
  month: "all",
  caller: "all",
  music: "all",
  breakOnly: false,
  starredOnly: false,
  sortBy: "date",
  sortDir: "asc",
  page: 0,
  pageSize: 100,
  view: "dances",
  freqMode: "dance",
  freqQuery: "",
  freqPage: 0,
};

const $ = (sel) => document.querySelector(sel);

function fmtDate(date) {
  const [y, m, d] = date.split("-").map(Number);
  return `${MONTH_NAMES[m - 1]} ${d}, ${y}`;
}

function escapeHtml(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function musicTypeBadge(mt) {
  if (mt === "recorded") return '<span class="badge-music-type mt-recorded">Recorded</span>';
  if (mt === "live") return '<span class="badge-music-type mt-live">Live</span>';
  return "";
}

function filteredRecords() {
  const q = state.query.trim().toLowerCase();
  return DATA.records.filter((r) => {
    if (state.year !== "all" && String(r.year) !== state.year) return false;
    if (state.month !== "all" && String(r.month) !== state.month) return false;
    if (state.caller !== "all" && !r.callers.includes(state.caller)) return false;
    if (state.music !== "all" && (r.music_type || "unknown") !== state.music) return false;
    if (state.breakOnly && !r.first_after_break) return false;
    if (state.starredOnly && !r.starred) return false;
    if (q) {
      if (r.dance.toLowerCase().includes(q)) return true;
      if (r.callers.some((c) => c.toLowerCase().includes(q))) return true;
      if (r.caller && r.caller.toLowerCase().includes(q)) return true;
      if (r.music && r.music.toLowerCase().includes(q)) return true;
      if (r.host && r.host.toLowerCase().includes(q)) return true;
      return false;
    }
    return true;
  });
}

function sortKey(r) {
  switch (state.sortBy) {
    case "dance": return r.dance.toLowerCase();
    case "caller": return (r.callers[0] || "").toLowerCase();
    case "music": return (r.music || "").toLowerCase();
    default: return r.date;
  }
}

function sortedRecords(recs) {
  const dir = state.sortDir === "asc" ? 1 : -1;
  return recs.slice().sort((a, b) => {
    const av = sortKey(a), bv = sortKey(b);
    if (av < bv) return -1 * dir;
    if (av > bv) return 1 * dir;
    return a.order - b.order;
  });
}

function num(n) {
  return n.toLocaleString("en-US");
}

/* ------------------------------------------------------------------ */
/* Rendering                                                           */
/* ------------------------------------------------------------------ */

function render() {
  renderStats();
  const recs = filteredRecords();
  $("#result-count").textContent =
    `${num(recs.length)} result${recs.length === 1 ? "" : "s"}` +
    (hasActiveFilters() ? " (filtered)" : "");
  renderDanceTable(recs);
  renderFrequency(recs);
}

function hasActiveFilters() {
  return state.query || state.year !== "all" || state.month !== "all" ||
    state.caller !== "all" || state.music !== "all" ||
    state.breakOnly || state.starredOnly;
}

function renderStats() {
  $("#stat-total").textContent = num(DATA.records.length);
  $("#stat-unique").textContent = num(new Set(DATA.records.map((r) => r.dance)).size);
  $("#stat-callers").textContent = num(callersList.length);
  $("#stat-years").textContent = `${DATA.years[0]}\u2013${DATA.years[DATA.years.length - 1]}`;
  if (DATA.generated) {
    const d = new Date(DATA.generated);
    $("#generated").textContent = d.toLocaleDateString("en-US", {
      year: "numeric", month: "long", day: "numeric",
    });
  }
}

function renderDanceTable(recs) {
  const sorted = sortedRecords(recs);
  const totalPages = Math.max(1, Math.ceil(sorted.length / state.pageSize));
  if (state.page >= totalPages) state.page = totalPages - 1;
  const start = state.page * state.pageSize;
  const pageRows = sorted.slice(start, start + state.pageSize);

  const tbody = $("#dance-tbody");
  tbody.innerHTML = "";
  $("#empty-state").classList.toggle("hidden", sorted.length !== 0);
  $("#dance-table").classList.toggle("hidden", sorted.length === 0);

  for (const r of pageRows) {
    const tr = document.createElement("tr");
    const setLabel = `${r.set}.${r.pos}`;
    const markers = [];
    if (r.first_after_break) markers.push('<span class="badge" title="First after mid-evening break">~</span>');
    if (r.starred) markers.push('<span class="badge" title="Starred / Spring Ball">*</span>');
    const host = r.host ? `<span class="badge-host">Host: ${escapeHtml(r.host)}</span>` : "";
    tr.innerHTML =
      `<td class="cell-date">${fmtDate(r.date)}</td>` +
      `<td class="cell-dance">${escapeHtml(r.dance)}${markers.join("")}</td>` +
      `<td class="cell-caller">${escapeHtml(r.callers.join(" &amp; ") || "\u2014")}${host}</td>` +
      `<td class="cell-music">${escapeHtml(r.music || "\u2014")}${musicTypeBadge(r.music_type)}</td>` +
      `<td class="cell-set" title="Program set ${r.set}, position ${r.pos}">${setLabel}</td>`;
    tbody.appendChild(tr);
  }

  $("#pageinfo").textContent = sorted.length
    ? `Showing ${num(start + 1)}\u2013${num(Math.min(start + state.pageSize, sorted.length))} of ${num(sorted.length)}`
    : "0 results";
  $("#prev").disabled = state.page === 0;
  $("#next").disabled = state.page >= totalPages - 1;

  updateSortIndicators();
}

function updateSortIndicators() {
  document.querySelectorAll("#dance-table th.sortable").forEach((th) => {
    const key = th.dataset.sort;
    const arrow = th.querySelector(".sort-arrow");
    if (key === state.sortBy) {
      arrow.textContent = state.sortDir === "asc" ? "\u25b2" : "\u25bc";
      th.setAttribute("aria-sort", state.sortDir === "asc" ? "ascending" : "descending");
    } else {
      arrow.textContent = "";
      th.removeAttribute("aria-sort");
    }
  });
}

function renderFrequency(recs) {
  const counts = new Map();
  if (state.freqMode === "dance") {
    for (const r of recs) counts.set(r.dance, (counts.get(r.dance) || 0) + 1);
  } else {
    for (const r of recs) {
      for (const c of r.callers) counts.set(c, (counts.get(c) || 0) + 1);
    }
  }
  const q = state.freqQuery.trim().toLowerCase();
  const entries = [...counts.entries()]
    .filter(([name]) => !q || name.toLowerCase().includes(q))
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));

  const totalPages = Math.max(1, Math.ceil(entries.length / 100));
  if (state.freqPage >= totalPages) state.freqPage = totalPages - 1;
  const start = state.freqPage * 100;
  const pageRows = entries.slice(start, start + 100);

  $("#freq-name-col").textContent = state.freqMode === "dance" ? "Dance" : "Caller";
  const tbody = $("#freq-tbody");
  tbody.innerHTML = "";
  pageRows.forEach(([name, count], i) => {
    const tr = document.createElement("tr");
    tr.className = "freq-row";
    tr.title = `Show every time "${name}" was called`;
    tr.innerHTML =
      `<td class="col-rank">${num(start + i + 1)}</td>` +
      `<td class="freq-name">${escapeHtml(name)}</td>` +
      `<td class="freq-count-cell">${num(count)}</td>`;
    tr.addEventListener("click", () => {
      if (state.freqMode === "dance") {
        state.query = name;
        $("#search").value = name;
      } else {
        state.caller = name;
        $("#caller").value = name;
      }
      switchView("dances");
      state.page = 0;
      render();
    });
    tbody.appendChild(tr);
  });

  $("#freq-count").textContent = `${num(entries.length)} distinct ${state.freqMode === "dance" ? "dances" : "callers"}`;
  $("#freq-pageinfo").textContent = entries.length
    ? `Showing ${num(start + 1)}\u2013${num(Math.min(start + 100, entries.length))} of ${num(entries.length)}`
    : "0 results";
  $("#freq-prev").disabled = state.freqPage === 0;
  $("#freq-next").disabled = state.freqPage >= totalPages - 1;
}

/* ------------------------------------------------------------------ */
/* Controls                                                            */
/* ------------------------------------------------------------------ */

function populateControls() {
  const yearSel = $("#year");
  yearSel.innerHTML = '<option value="all">All years</option>';
  for (const y of DATA.years) {
    const o = document.createElement("option");
    o.value = y; o.textContent = y;
    yearSel.appendChild(o);
  }

  const monthSel = $("#month");
  monthSel.innerHTML = '<option value="all">All months</option>';
  MONTH_NAMES.forEach((name, i) => {
    const o = document.createElement("option");
    o.value = String(i + 1); o.textContent = name;
    monthSel.appendChild(o);
  });

  callersList = [...new Set(DATA.records.flatMap((r) => r.callers))].sort((a, b) =>
    a.localeCompare(b));
  const callerSel = $("#caller");
  callerSel.innerHTML = '<option value="all">All callers</option>';
  for (const c of callersList) {
    const o = document.createElement("option");
    o.value = c; o.textContent = c;
    callerSel.appendChild(o);
  }

  const musicSel = $("#music");
  musicSel.innerHTML =
    '<option value="all">All music</option>' +
    '<option value="live">Live music</option>' +
    '<option value="recorded">Recorded music</option>' +
    '<option value="unknown">Unknown</option>';
}

function switchView(view) {
  state.view = view;
  document.querySelectorAll(".tab").forEach((t) => {
    const active = t.dataset.view === view;
    t.classList.toggle("active", active);
    t.setAttribute("aria-selected", active ? "true" : "false");
  });
  $("#view-dances").classList.toggle("hidden", view !== "dances");
  $("#view-frequency").classList.toggle("hidden", view !== "frequency");
  if (view === "frequency") renderFrequency(filteredRecords());
}

function bindEvents() {
  let debounce;
  $("#search").addEventListener("input", (e) => {
    clearTimeout(debounce);
    debounce = setTimeout(() => {
      state.query = e.target.value;
      state.page = 0;
      render();
    }, 180);
  });

  $("#year").addEventListener("change", (e) => { state.year = e.target.value; state.page = 0; render(); });
  $("#month").addEventListener("change", (e) => { state.month = e.target.value; state.page = 0; render(); });
  $("#caller").addEventListener("change", (e) => { state.caller = e.target.value; state.page = 0; render(); });
  $("#music").addEventListener("change", (e) => { state.music = e.target.value; state.page = 0; render(); });
  $("#break").addEventListener("change", (e) => { state.breakOnly = e.target.checked; state.page = 0; render(); });
  $("#starred").addEventListener("change", (e) => { state.starredOnly = e.target.checked; state.page = 0; render(); });

  $("#clear").addEventListener("click", () => {
    state.query = ""; state.year = "all"; state.month = "all";
    state.caller = "all"; state.music = "all";
    state.breakOnly = false; state.starredOnly = false;
    state.page = 0;
    $("#search").value = ""; $("#year").value = "all"; $("#month").value = "all";
    $("#caller").value = "all"; $("#music").value = "all";
    $("#break").checked = false; $("#starred").checked = false;
    render();
  });

  document.querySelectorAll("#dance-table th.sortable").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      if (state.sortBy === key) {
        state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
      } else {
        state.sortBy = key;
        state.sortDir = key === "date" ? "asc" : "asc";
      }
      state.page = 0;
      render();
    });
  });

  $("#prev").addEventListener("click", () => { state.page--; renderDanceTable(filteredRecords()); });
  $("#next").addEventListener("click", () => { state.page++; renderDanceTable(filteredRecords()); });
  $("#freq-prev").addEventListener("click", () => { state.freqPage--; renderFrequency(filteredRecords()); });
  $("#freq-next").addEventListener("click", () => { state.freqPage++; renderFrequency(filteredRecords()); });

  document.querySelectorAll(".tab").forEach((t) =>
    t.addEventListener("click", () => switchView(t.dataset.view)));

  document.querySelectorAll(".freq-tab").forEach((t) =>
    t.addEventListener("click", () => {
      document.querySelectorAll(".freq-tab").forEach((x) => x.classList.remove("active"));
      t.classList.add("active");
      state.freqMode = t.dataset.freq;
      state.freqPage = 0;
      renderFrequency(filteredRecords());
    }));

  let freqDebounce;
  $("#freq-search").addEventListener("input", (e) => {
    clearTimeout(freqDebounce);
    freqDebounce = setTimeout(() => {
      state.freqQuery = e.target.value;
      state.freqPage = 0;
      renderFrequency(filteredRecords());
    }, 180);
  });
}

/* ------------------------------------------------------------------ */
/* Boot                                                                */
/* ------------------------------------------------------------------ */

async function init() {
  try {
    const resp = await fetch("data/dances.json");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    DATA = await resp.json();
  } catch (err) {
    $("#empty-state").classList.remove("hidden");
    $("#empty-state").textContent =
      "Could not load the dataset. Run the crawler to generate data/dances.json. (" + err.message + ")";
    return;
  }
  populateControls();
  bindEvents();
  render();
}

init();
