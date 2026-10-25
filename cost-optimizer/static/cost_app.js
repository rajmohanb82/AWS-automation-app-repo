/* ─────────────────────────────────────────────────────────────────
   AWS Cost Optimizer — Frontend Logic (AssumeRole version)
   ────────────────────────────────────────────────────────────── */

let state = {
  accounts: [],
  regions: [],
  selectedAccount: null,
  selectedRegion: null,
  scan: null,
  advice: null,
  recFilter: "ALL",
  sortCol: "monthly_saving",
  sortDir: -1,
  charts: {},
};

// ── Bootstrap ──────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  await loadRegions();
  await loadAccounts();
});

async function loadRegions() {
  const res = await fetch("/api/regions");
  const data = await res.json();
  state.regions = data.regions || [];
  const sel = document.getElementById("regionSelect");
  sel.innerHTML = state.regions.map(r =>
    `<option value="${r.code}" ${r.code === "ap-south-1" ? "selected" : ""}>${r.code} — ${r.name}</option>`
  ).join("");
}

async function loadAccounts() {
  const res = await fetch("/api/accounts");
  const data = await res.json();
  state.accounts = data.accounts || [];
  const sel = document.getElementById("accountSelect");
  if (!state.accounts.length) {
    sel.innerHTML = `<option value="">No accounts configured</option>`;
    return;
  }
  sel.innerHTML = `<option value="">— Select client account —</option>` +
    state.accounts.map(a =>
      `<option value="${a.account_id}">${a.name} (${a.account_id})</option>`
    ).join("");
}

// ── Connect ────────────────────────────────────────────────────────
async function connectAccount() {
  const accountId = document.getElementById("accountSelect").value;
  const region = document.getElementById("regionSelect").value;
  if (!accountId) { showStatus("error", "Please select a client account."); return; }

  const btn = document.getElementById("connectBtn");
  btn.disabled = true; btn.innerHTML = "⏳ Connecting…";
  showStatus("pending", "Assuming role into client account…");

  try {
    const res = await fetch("/api/verify-account", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ account_id: accountId, region }),
    });
    const data = await res.json();

    if (!res.ok) {
      showStatus("error", data.error || "Connection failed.");
      btn.disabled = false; btn.innerHTML = "🔗 Connect";
      return;
    }

    state.selectedAccount = data;
    state.selectedRegion = region;
    showStatus("", "");
    document.getElementById("idAccount").textContent = data.account_id || "—";
    document.getElementById("idName").textContent = data.name || "—";
    document.getElementById("idRegion").textContent = data.region || "—";
    document.getElementById("idRole").textContent = data.arn.split("/").pop() || "—";
    document.getElementById("identityCard").style.display = "block";
  } catch (e) {
    showStatus("error", "Network error: " + e.message);
  } finally {
    btn.disabled = false; btn.innerHTML = "🔗 Connect";
  }
}

function showStatus(type, html) {
  const el = document.getElementById("authStatus");
  if (!type && !html) { el.style.display = "none"; return; }
  el.className = `co-auth-status ${type}`;
  el.innerHTML = html;
  el.style.display = "block";
}

// ── Scan ───────────────────────────────────────────────────────────
async function startScan() {
  if (!state.selectedAccount) { alert("Please connect to an account first."); return; }

  document.getElementById("welcomeState").style.display = "none";
  document.getElementById("resultsState").style.display = "none";
  document.getElementById("scanState").style.display = "flex";
  document.getElementById("scanBtn").disabled = true;

  const bar = document.getElementById("scanBar");
  bar.style.animation = "none"; void bar.offsetWidth;
  bar.style.animation = "scanProg 35s linear forwards";

  const steps = ["sstep1","sstep2","sstep3","sstep4","sstep5"];
  let stepIdx = 0;
  const stepInterval = setInterval(() => {
    if (stepIdx > 0) document.getElementById(steps[stepIdx-1]).classList.replace("active","done");
    if (stepIdx < steps.length) document.getElementById(steps[stepIdx]).classList.add("active");
    stepIdx++;
    if (stepIdx >= steps.length) clearInterval(stepInterval);
  }, 6000);

  try {
    const res = await fetch("/api/cost-scan", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        account_id: state.selectedAccount.account_id,
        region: state.selectedRegion,
      }),
    });
    clearInterval(stepInterval);
    const data = await res.json();

    if (!res.ok) {
      document.getElementById("scanState").style.display = "none";
      document.getElementById("welcomeState").style.display = "flex";
      alert("Scan failed: " + (data.error || "Unknown error"));
      return;
    }

    state.scan = data.scan;
    state.advice = data.advice;
    renderDashboard();
  } catch (e) {
    clearInterval(stepInterval);
    document.getElementById("scanState").style.display = "none";
    document.getElementById("welcomeState").style.display = "flex";
    alert("Network error: " + e.message);
  } finally {
    document.getElementById("scanBtn").disabled = false;
  }
}

// ── Render Dashboard ───────────────────────────────────────────────
function renderDashboard() {
  document.getElementById("scanState").style.display = "none";
  document.getElementById("resultsState").style.display = "block";

  renderKPIs();
  renderCharts();
  renderHeatmap();
  renderRecTable();
  renderErrors();
  renderSidebarKPIs();

  const model = state.advice?.model_used || "Rules Engine";
  document.getElementById("aiModelBadge").textContent = `🤖 ${model}`;
}

function renderKPIs() {
  const scan = state.scan;
  const recs = state.advice?.recommendations || [];

  const totalSpend = scan.total_cost || 0;
  const totalSaving = scan.total_saving || 0;
  const score = scan.optimization_score || 0;
  const resourceCount = scan.resources?.length || 0;
  const savePct = totalSpend > 0 ? ((totalSaving / totalSpend) * 100).toFixed(1) : "0.0";

  document.getElementById("kpiTotalSpend").textContent = `$${totalSpend.toFixed(2)}`;
  document.getElementById("kpiResourceCount").textContent = `${resourceCount} resources scanned`;
  document.getElementById("kpiTotalSaving").textContent = `$${totalSaving.toFixed(2)}`;
  document.getElementById("kpiSavingPct").textContent = `${savePct}% of total spend`;
  document.getElementById("kpiOptScore").textContent = score;
  document.getElementById("kpiScoreLabel").textContent = score >= 80 ? "Excellent 🌟" : score >= 60 ? "Good 👍" : "Needs Attention ⚠️";
  document.getElementById("kpiModelUsed").textContent = state.advice?.model_used || "—";
  document.getElementById("kpiRecCount").textContent = `${recs.length} recommendation${recs.length !== 1 ? "s" : ""}`;
}

function renderSidebarKPIs() {
  const scan = state.scan;
  document.getElementById("kpiSpend").textContent = `$${(scan.total_cost || 0).toFixed(2)}`;
  document.getElementById("kpiSaving").textContent = `$${(scan.total_saving || 0).toFixed(2)}`;
  document.getElementById("kpiScore").textContent = `${scan.optimization_score || 0}/100`;
  document.getElementById("sidebarKpis").style.display = "flex";
}

// ── Chart.js Charts ────────────────────────────────────────────────
const PALETTE = ["#10b981","#3b82f6","#f59e0b","#8b5cf6","#ef4444","#06b6d4","#ec4899","#84cc16"];

function destroyChart(key) {
  if (state.charts[key]) { state.charts[key].destroy(); delete state.charts[key]; }
}

function renderCharts() {
  const summary = state.scan?.summary || {};
  const recs = state.advice?.recommendations || [];

  destroyChart("costByService");
  const svcLabels = Object.keys(summary);
  const svcCosts = svcLabels.map(s => summary[s].total_cost);
  const svcSaving = svcLabels.map(s => summary[s].total_saving);
  const ctx1 = document.getElementById("costByServiceChart").getContext("2d");
  state.charts.costByService = new Chart(ctx1, {
    type: "bar",
    data: {
      labels: svcLabels,
      datasets: [
        { label: "Current Cost ($)", data: svcCosts, backgroundColor: svcLabels.map((_, i) => PALETTE[i % PALETTE.length] + "99"), borderColor: svcLabels.map((_, i) => PALETTE[i % PALETTE.length]), borderWidth: 1.5, borderRadius: 5 },
        { label: "Potential Saving ($)", data: svcSaving, backgroundColor: "rgba(245,158,11,0.2)", borderColor: "rgba(245,158,11,0.7)", borderWidth: 1.5, borderRadius: 5, borderDash: [4,4] },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false, indexAxis: "y",
      plugins: { legend: { display: true, labels: { color: "#8892a4", font: { size: 11 } } }, tooltip: { callbacks: { label: ctx => ` $${ctx.raw.toFixed(2)}` }, backgroundColor: "rgba(10,14,26,0.95)", borderColor: "rgba(255,255,255,0.08)", borderWidth: 1, titleColor: "#eef0f5", bodyColor: "#8892a4" } },
      scales: { x: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#8892a4", callback: v => `$${v}` } }, y: { grid: { display: false }, ticks: { color: "#8892a4" } } },
    },
  });

  destroyChart("savingsDonut");
  const donutLabels = svcLabels.filter(s => summary[s].total_saving > 0);
  const donutData = donutLabels.map(s => summary[s].total_saving);
  const donutColors = donutLabels.map((_, i) => PALETTE[i % PALETTE.length]);
  const ctx2 = document.getElementById("savingsDonutChart").getContext("2d");
  state.charts.savingsDonut = new Chart(ctx2, {
    type: "doughnut",
    data: { labels: donutLabels, datasets: [{ data: donutData, backgroundColor: donutColors.map(c => c + "bb"), borderColor: donutColors, borderWidth: 1.5, hoverOffset: 6 }] },
    options: { responsive: true, maintainAspectRatio: false, cutout: "68%", plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => ` ${ctx.label}: $${ctx.raw.toFixed(2)}` }, backgroundColor: "rgba(10,14,26,0.95)", borderColor: "rgba(255,255,255,0.08)", borderWidth: 1, titleColor: "#eef0f5", bodyColor: "#8892a4" } } },
  });

  const totalSaving = donutData.reduce((a, b) => a + b, 0);
  document.getElementById("donutLegend").innerHTML = donutLabels.map((label, i) => {
    const pct = totalSaving > 0 ? ((donutData[i] / totalSaving) * 100).toFixed(1) : "0";
    return `<div class="co-dl-row"><div class="co-dl-dot" style="background:${donutColors[i]}"></div><span class="co-dl-label">${label}</span><span class="co-dl-val">${pct}% · $${donutData[i].toFixed(2)}</span></div>`;
  }).join("");

  destroyChart("category");
  const catCounts = {}, catSavings = {};
  recs.forEach(r => { const c = r.category || "Other"; catCounts[c] = (catCounts[c] || 0) + 1; catSavings[c] = (catSavings[c] || 0) + (r.monthly_saving || 0); });
  const catLabels = Object.keys(catCounts);
  const catColors = catLabels.map((_, i) => PALETTE[(i + 2) % PALETTE.length]);
  const ctx3 = document.getElementById("categoryChart").getContext("2d");
  state.charts.category = new Chart(ctx3, {
    type: "bar",
    data: {
      labels: catLabels,
      datasets: [
        { label: "# Recommendations", data: catLabels.map(c => catCounts[c]), backgroundColor: catColors.map(c => c + "99"), borderColor: catColors, borderWidth: 1.5, borderRadius: 5, yAxisID: "y" },
        { label: "Savings ($)", data: catLabels.map(c => +(catSavings[c] || 0).toFixed(2)), backgroundColor: "rgba(245,158,11,0.25)", borderColor: "rgba(245,158,11,0.8)", borderWidth: 1.5, borderRadius: 5, type: "line", yAxisID: "y2", tension: 0.4, pointBackgroundColor: "rgba(245,158,11,0.9)", pointRadius: 4 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: true, labels: { color: "#8892a4", font: { size: 11 } } }, tooltip: { backgroundColor: "rgba(10,14,26,0.95)", titleColor: "#eef0f5", bodyColor: "#8892a4" } },
      scales: { x: { grid: { color: "rgba(255,255,255,0.04)" }, ticks: { color: "#8892a4", font: { size: 11 } } }, y: { position: "left", grid: { color: "rgba(255,255,255,0.04)" }, ticks: { color: "#8892a4" }, title: { display: true, text: "Count", color: "#4f5b6e", font: { size: 11 } } }, y2: { position: "right", grid: { display: false }, ticks: { color: "#f59e0b", callback: v => `$${v}` }, title: { display: true, text: "Savings", color: "#f59e0b", font: { size: 11 } } } },
    },
  });
}

// ── Utilization Heatmap ────────────────────────────────────────────
function renderHeatmap() {
  const resources = (state.scan?.resources || [])
    .filter(r => r.cpu_avg_pct !== null && r.cpu_avg_pct !== undefined)
    .sort((a, b) => (a.cpu_avg_pct || 0) - (b.cpu_avg_pct || 0))
    .slice(0, 20);

  if (!resources.length) {
    document.getElementById("utilizationHeatmap").innerHTML = `<p style="color:var(--text-3);font-size:13px;padding:20px">No CloudWatch utilization data available.</p>`;
    return;
  }

  const rows = resources.map(r => {
    const cpu = r.cpu_avg_pct ?? null;
    const pct = cpu !== null ? cpu : 0;
    const heatClass = pct < 20 ? "heat-low" : pct < 60 ? "heat-medium" : "heat-high";
    const cpuLabel = cpu !== null ? `${pct}%` : "N/A";
    const savingBadge = r.potential_saving > 0 ? `<span style="color:var(--orange);font-size:10px;font-family:var(--mono)">-$${r.potential_saving.toFixed(2)}/mo</span>` : "";
    return `<tr>
      <td><div class="resource-name">${escHtml(r.name || r.resource_id)}</div><div class="resource-id">${escHtml(r.resource_id)}</div></td>
      <td>${escHtml(r.service)}</td>
      <td>${escHtml(r.type || "—")}</td>
      <td class="heat-bar-cell"><div style="display:flex;align-items:center;gap:8px;"><div class="heat-bar-wrap" style="flex:1"><div class="heat-bar ${heatClass}" style="width:${Math.min(pct,100)}%"></div></div><span class="utilization-text">${cpuLabel}</span></div></td>
      <td class="cost-cell">$${(r.monthly_cost || 0).toFixed(2)}</td>
      <td>${savingBadge}</td>
    </tr>`;
  }).join("");

  document.getElementById("utilizationHeatmap").innerHTML = `
    <table class="co-heatmap-table">
      <thead><tr><th>Resource</th><th>Service</th><th>Type</th><th>CPU Utilization (14-day avg)</th><th>Monthly Cost</th><th>Saving</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

// ── Recommendations Table ──────────────────────────────────────────
function setRecFilter(f) {
  state.recFilter = f;
  ["ALL","HIGH","MEDIUM","LOW"].forEach(k => {
    const id = { ALL:"filterAll", HIGH:"filterHigh", MEDIUM:"filterMedium", LOW:"filterLow" }[k];
    document.getElementById(id).classList.toggle("active", k === f);
  });
  renderRecTable();
}

function sortTable(col) {
  if (state.sortCol === col) state.sortDir *= -1;
  else { state.sortCol = col; state.sortDir = -1; }
  renderRecTable();
}

function renderRecTable() {
  let recs = (state.advice?.recommendations || []).filter(r => {
    if (state.recFilter === "ALL") return true;
    return r.priority === state.recFilter;
  });

  const col = state.sortCol;
  recs = [...recs].sort((a, b) => {
    const va = a[col] || 0, vb = b[col] || 0;
    if (typeof va === "string") return va.localeCompare(vb) * state.sortDir;
    return (va - vb) * state.sortDir;
  });

  document.getElementById("recTableCount").textContent = `${recs.length} recommendation${recs.length !== 1 ? "s" : ""}`;

  if (!recs.length) {
    document.getElementById("recTableBody").innerHTML = `<tr><td colspan="9" style="text-align:center;padding:30px;color:var(--text-3)">No ${state.recFilter !== "ALL" ? state.recFilter + " priority " : ""}recommendations found.</td></tr>`;
    return;
  }

  document.getElementById("recTableBody").innerHTML = recs.map(r => `
    <tr>
      <td><span class="pri-badge pri-${r.priority}">${r.priority}</span></td>
      <td>${escHtml(r.service)}</td>
      <td><div class="resource-name">${escHtml(r.resource_name || r.resource_id)}</div><div class="resource-id">${escHtml(r.resource_id)}</div><div class="rec-reasoning">${escHtml(r.reasoning || "")}</div></td>
      <td class="cost-cell">$${(r.current_monthly_cost || 0).toFixed(2)}</td>
      <td class="cost-cell">$${(r.projected_monthly_cost || 0).toFixed(2)}</td>
      <td class="saving-cell">$${(r.monthly_saving || 0).toFixed(2)}</td>
      <td><span class="cat-badge">${escHtml(r.category || "—")}</span></td>
      <td style="font-size:12px;color:var(--text-2);max-width:200px">${escHtml(r.action || "—")}</td>
      <td><span class="conf-badge conf-${r.confidence || "MEDIUM"}">${r.confidence || "—"}</span></td>
    </tr>
  `).join("");
}

function renderErrors() {
  const errors = state.scan?.errors || [];
  const errDiv = document.getElementById("scanErrors");
  if (!errors.length) { errDiv.style.display = "none"; return; }
  errDiv.style.display = "block";
  errDiv.innerHTML = `⚠️ <strong>Some services couldn't be scanned:</strong><br>` +
    errors.map(e => `• ${escHtml(e)}`).join("<br>");
}

// ── XLSX Export ────────────────────────────────────────────────────
function exportCostXLSX() {
  if (!state.advice) return;
  if (typeof XLSX === "undefined") {
    const s = document.createElement("script");
    s.src = "https://cdn.sheetjs.com/xlsx-0.20.3/package/dist/xlsx.full.min.js";
    s.onload = _doXLSX;
    document.head.appendChild(s);
  } else { _doXLSX(); }
}

function _doXLSX() {
  const wb = XLSX.utils.book_new();
  const recs = state.advice?.recommendations || [];
  const scan = state.scan;
  const acct = state.selectedAccount || {};

  const summary = [
    ["AWS Cost Optimization Report"], [],
    ["Account", acct.account_id || "—"],
    ["Client Name", acct.name || "—"],
    ["Region", acct.region || "—"],
    ["Scanned At", scan?.scanned_at ? new Date(scan.scanned_at).toLocaleString() : "—"],
    ["Model Used", state.advice?.model_used || "—"], [],
    ["Total Monthly Spend", `$${(scan?.total_cost || 0).toFixed(2)}`],
    ["Potential Savings", `$${(scan?.total_saving || 0).toFixed(2)}`],
    ["Optimization Score", `${scan?.optimization_score || 0}/100`],
  ];
  XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(summary), "Summary");

  const recHeaders = ["Priority","Service","Resource ID","Resource Name","Current Cost","Projected Cost","Monthly Saving","Category","Action","Confidence","Reasoning"];
  const recRows = recs.map(r => [r.priority, r.service, r.resource_id, r.resource_name, `$${(r.current_monthly_cost||0).toFixed(2)}`, `$${(r.projected_monthly_cost||0).toFixed(2)}`, `$${(r.monthly_saving||0).toFixed(2)}`, r.category, r.action, r.confidence, r.reasoning]);
  const wsRec = XLSX.utils.aoa_to_sheet([recHeaders, ...recRows]);
  XLSX.utils.book_append_sheet(wb, wsRec, "Recommendations");

  const resHeaders = ["Service","Resource ID","Name","Type","State","Monthly Cost","CPU Avg %","Suggestion","Potential Saving"];
  const resRows = (scan?.resources || []).map(r => [r.service, r.resource_id, r.name, r.type, r.state, `$${(r.monthly_cost||0).toFixed(2)}`, r.cpu_avg_pct != null ? `${r.cpu_avg_pct}%` : "N/A", r.suggestion || "", `$${(r.potential_saving||0).toFixed(2)}`]);
  XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet([resHeaders, ...resRows]), "All Resources");

  const ts = new Date().toISOString().slice(0,10);
  XLSX.writeFile(wb, `aws-cost-optimizer-${acct.name || "report"}-${ts}.xlsx`);
}

async function downloadCostReport() {
  if (!state.scan || !state.advice) { alert("Please run a scan first."); return; }

  const btn = document.getElementById("reportBtn");
  const originalHtml = btn.innerHTML;
  btn.disabled = true; btn.innerHTML = `<span>⏳</span> Generating PDF…`;

  try {
    const res = await fetch("/api/generate-cost-report", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scan: state.scan, advice: state.advice, account_id: state.selectedAccount?.account_id || "unknown", region: state.selectedRegion || "unknown" }),
    });
    if (!res.ok) { const err = await res.json(); throw new Error(err.error || "Failed"); }
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url;
    const ts = new Date().toISOString().slice(0,16).replace(/[:T]/g,"-");
    a.download = `AWS_Cost_Optimization_Report_${ts}.pdf`;
    document.body.appendChild(a); a.click(); a.remove();
    window.URL.revokeObjectURL(url);
  } catch (e) { alert("PDF Error: " + e.message); }
  finally { btn.disabled = false; btn.innerHTML = originalHtml; }
}

function escHtml(str) {
  return String(str || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
