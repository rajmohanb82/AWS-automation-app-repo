/* AWS Housekeeping UI — EC2 Version (AssumeRole) */

const CATEGORY_ICONS = {
  "EC2":"⚡","IAM":"🔐","S3":"🪣","Security Groups":"🛡️",
  "RDS":"🗄️","ELB":"⚖️","Lambda":"λ","CloudWatch":"📊",
  "EKS":"☸️","ECS":"🐳","KDS":"🌊","KFH":"🔥",
};

let state = {
  accounts: [], regions: [], authInfo: null,
  findings: [], findingsMap: {}, activeFilter: "ALL", remediationLog: [],
};

document.addEventListener("DOMContentLoaded", async () => {
  await loadRegions();
  await loadAccounts();
});

async function loadAccounts() {
  try {
    const res = await fetch("/api/accounts");
    const data = await res.json();
    state.accounts = data.accounts || [];
    const sel = document.getElementById("accountSelect");
    if (state.accounts.length === 0) {
      sel.innerHTML = `<option value="">No accounts in accounts.json</option>`;
      return;
    }
    sel.innerHTML = `<option value="">— Select account —</option>` +
      state.accounts.map(a => `<option value="${a.account_id}">${a.name} (${a.account_id})</option>`).join("");
  } catch (e) { console.error("Failed to load accounts:", e); }
}

async function loadRegions() {
  try {
    const res = await fetch("/api/regions");
    const data = await res.json();
    state.regions = data.regions || [];
    const sel = document.getElementById("regionSelect");
    sel.innerHTML = state.regions.map(r =>
      `<option value="${r.code}" ${r.code === "ap-south-1" ? "selected" : ""}>${r.code} — ${r.name}</option>`
    ).join("");
  } catch (e) { console.error("Failed to load regions:", e); }
}

async function startAuth() {
  const account_id = document.getElementById("accountSelect").value;
  const region = document.getElementById("regionSelect").value;
  if (!account_id) { showAuthStatus("error", "Please select an account."); return; }

  const btn = document.getElementById("loginBtn");
  btn.disabled = true;
  btn.innerHTML = `<span class="btn-icon">⏳</span> Connecting…`;
  showAuthStatus("pending", "Assuming role into account…");

  try {
    const res = await fetch("/api/verify-account", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ account_id, region }),
    });
    const data = await res.json();
    if (!res.ok) {
      showAuthStatus("error", data.error || "Connection failed.");
      btn.disabled = false; btn.innerHTML = `<span class="btn-icon">🔗</span> Connect`;
      return;
    }
    onAuthenticated(data);
  } catch (e) {
    showAuthStatus("error", "Network error: " + e.message);
    btn.disabled = false; btn.innerHTML = `<span class="btn-icon">🔗</span> Connect`;
  }
}

function onAuthenticated(data) {
  state.authInfo = { account_id: data.account_id, name: data.name, region: data.region };
  const btn = document.getElementById("loginBtn");
  btn.disabled = false; btn.innerHTML = `<span class="btn-icon">🔗</span> Connect`;
  hideAuthStatus();
  document.getElementById("idAccountId").textContent = data.account_id || "—";
  document.getElementById("idRole").textContent = data.name || "—";
  document.getElementById("idRegion").textContent = data.region || "—";
  document.getElementById("identityCard").style.display = "block";
  showAuthStatus("success", "✅ Connected successfully!");
}

async function startScan() {
  if (!state.authInfo) { alert("Please connect first."); return; }
  document.getElementById("welcomeState").style.display = "none";
  document.getElementById("resultsState").style.display = "none";
  document.getElementById("scanState").style.display = "flex";
  document.getElementById("scanBar").style.animation = "none";
  void document.getElementById("scanBar").offsetWidth;
  document.getElementById("scanBar").style.animation = "scanProgress 30s linear forwards";

  const msgs = ["Scanning EC2 instances…","Checking IAM users…","Auditing S3 buckets…",
    "Reviewing Security Groups…","Inspecting RDS…","Checking Load Balancers…",
    "Analysing Lambda…","Reviewing CloudWatch…","Compiling recommendations…"];
  let i = 0;
  const msgInt = setInterval(() => { i=(i+1)%msgs.length; document.getElementById("scanText").textContent=msgs[i]; }, 3000);

  try {
    const res = await fetch("/api/recommendations", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ account_id: state.authInfo.account_id, region: state.authInfo.region }),
    });
    const data = await res.json();
    clearInterval(msgInt);
    if (!res.ok) {
      document.getElementById("scanState").style.display = "none";
      document.getElementById("welcomeState").style.display = "flex";
      alert("Scan failed: " + (data.error || "Unknown error")); return;
    }
    state.findings = data.results || [];
    state.findingsMap = {};
    state.findings.forEach((f, i) => { state.findingsMap[i] = f; });
    renderResults();
  } catch (e) {
    clearInterval(msgInt);
    document.getElementById("scanState").style.display = "none";
    document.getElementById("welcomeState").style.display = "flex";
    alert("Network error: " + e.message);
  }
}

function renderResults() {
  document.getElementById("scanState").style.display = "none";
  document.getElementById("resultsState").style.display = "block";
  if (!document.getElementById("resultsHeader")) {
    document.getElementById("resultsState").insertAdjacentHTML("afterbegin", `
      <div id="resultsHeader" class="results-header">
        <h2 class="results-title">Housekeeping Recommendations</h2>
        <div class="results-actions">
          <button class="btn-export pdf-btn" id="reportBtn" onclick="downloadReport()">📄 PDF Report</button>
          <button class="btn-export xlsx-btn" onclick="exportXLSX()">📊 XLSX</button>
          <button class="btn-rescan" onclick="startScan()">🔄 Re-scan</button>
        </div>
      </div>`);
  }
  renderCounters(); renderCategories();
}

function renderCounters() {
  const c = {HIGH:0,MEDIUM:0,LOW:0};
  state.findings.forEach(f => { if(c[f.severity]!==undefined) c[f.severity]++; });
  document.getElementById("summaryCounters").innerHTML = `
    <div class="counter-card total" onclick="setFilter('ALL')"><div class="counter-num">${c.HIGH+c.MEDIUM+c.LOW}</div><div class="counter-label">Total</div></div>
    <div class="counter-card high" onclick="setFilter('HIGH')"><div class="counter-num">${c.HIGH}</div><div class="counter-label">🔴 High</div></div>
    <div class="counter-card medium" onclick="setFilter('MEDIUM')"><div class="counter-num">${c.MEDIUM}</div><div class="counter-label">🟡 Medium</div></div>
    <div class="counter-card low" onclick="setFilter('LOW')"><div class="counter-num">${c.LOW}</div><div class="counter-label">🟢 Low</div></div>`;
}

function filteredFindings() {
  if (state.activeFilter === "ALL") return state.findings;
  return state.findings.filter(f => f.severity === state.activeFilter);
}

function setFilter(filter) {
  state.activeFilter = filter;
  document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
  const m = {ALL:"filterAll",HIGH:"filterHigh",MEDIUM:"filterMedium",LOW:"filterLow"};
  document.getElementById(m[filter]).classList.add("active");
  renderCategories();
}

function renderCategories() {
  const container = document.getElementById("categoryContainer");
  const noIssues = document.getElementById("noIssues");
  const findings = filteredFindings();
  const groups = {};
  findings.forEach(f => { const idx=state.findings.indexOf(f); if(!groups[f.category])groups[f.category]=[]; groups[f.category].push({f,idx}); });
  if (findings.filter(f=>f.severity!=="INFO").length===0 && state.activeFilter==="ALL") { container.innerHTML=""; noIssues.style.display="block"; return; }
  noIssues.style.display = "none";
  if (!Object.keys(groups).length) { container.innerHTML=`<div class="no-issues"><h3>No ${state.activeFilter} issues</h3></div>`; return; }

  container.innerHTML = Object.entries(groups).map(([cat, entries], ci) => {
    const icon = CATEGORY_ICONS[cat]||"📋";
    const items = entries.map(e=>e.f);
    const h=items.filter(i=>i.severity==="HIGH").length, m=items.filter(i=>i.severity==="MEDIUM").length, l=items.filter(i=>i.severity==="LOW").length;
    const sid = `cat-${cat.replace(/\s+/g,"-")}`;
    const open = ci===0||h>0;
    return `<div class="category-section" id="${sid}-wrap">
      <div class="category-header ${open?"open":""}" onclick="toggleCategory('${sid}')">
        <div class="category-left"><span class="category-icon">${icon}</span><span class="category-name">${cat}</span><span class="category-count">${items.length}</span></div>
        <div class="category-right">${h?`<span class="sev-badge sev-HIGH">${h} HIGH</span>`:""} ${m?`<span class="sev-badge sev-MEDIUM">${m} MED</span>`:""} ${l?`<span class="sev-badge sev-LOW">${l} LOW</span>`:""}<span class="category-chevron">▾</span></div>
      </div>
      <div class="category-body ${open?"open":""}" id="${sid}-body">${entries.map(({f,idx})=>renderFinding(f,idx)).join("")}</div>
    </div>`;
  }).join("");
}

function renderFinding(f, idx) {
  const remediable = isRemediable(f);
  const key = `remediated_${f.category}_${f.resource_id}`;
  const done = sessionStorage.getItem(key);
  return `<div class="finding-row ${done?'finding-remediated':''}" id="finding-row-${idx}">
    <span class="sev-badge sev-${f.severity}">${f.severity}</span>
    <div class="finding-body">
      <div class="finding-title">${esc(f.title)}</div>
      <div class="finding-resource">${esc(f.resource_id)}</div>
      <div class="finding-details">${esc(f.details)}</div>
      <div class="finding-action">${esc(f.action)}</div>
    </div>
    <div class="finding-btns">
      ${done?`<span class="badge-remediated">✓ Done</span>`:(remediable?`<button class="fix-btn" onclick="openRemediationModal(${idx})">🔧 Fix</button>`:`<span class="fix-btn-na">📋 Manual</span>`)}
    </div>
  </div>`;
}

function toggleCategory(sid) {
  document.querySelector(`#${sid}-wrap .category-header`).classList.toggle("open");
  document.getElementById(`${sid}-body`).classList.toggle("open");
}

const REMEDIABLE_SIGNATURES = [
  {category:"EC2",match:"Stopped EC2"},{category:"EC2",match:"Unattached EBS"},{category:"EC2",match:"Unused Elastic IP"},
  {category:"IAM",match:"Without MFA"},{category:"IAM",match:"Access Key"},{category:"IAM",match:"Inactive IAM User"},
  {category:"S3",match:"Public Access"},{category:"S3",match:"Versioning"},
  {category:"Security Groups",match:"Open to World"},{category:"Security Groups",match:"Unused Security Group"},
  {category:"RDS",match:"Publicly Accessible"},{category:"CloudWatch",match:"INSUFFICIENT_DATA"},
  {category:"KDS",match:"Without Encryption"},{category:"VPC",match:"Flow Logs"},
];
function isRemediable(f) { return REMEDIABLE_SIGNATURES.some(s=>s.category===f.category&&f.title.includes(s.match)); }

let _remFinding=null, _remIdx=null;
function openRemediationModal(idx) {
  _remFinding=state.findingsMap[idx]; _remIdx=idx;
  if(!_remFinding) return;
  const f=_remFinding;
  document.getElementById("remTitle").textContent=f.title;
  document.getElementById("remResource").textContent=f.resource_id;
  document.getElementById("remDetails").textContent=f.details;
  document.getElementById("remAction").textContent=f.action;
  const sev=document.getElementById("remSeverity"); sev.textContent=f.severity; sev.className=`sev-badge sev-${f.severity}`;
  document.getElementById("remConfirmCheck").checked=false;
  document.getElementById("remConfirmBtn").disabled=true;
  document.getElementById("remStepsWrap").style.display="none";
  document.getElementById("remDoneMsg").style.display="none";
  document.getElementById("remConfirmSection").style.display="block";
  const destr=["Stopped EC2","Unattached EBS","Unused Security Group","Unused Elastic IP"].some(k=>f.title.includes(k));
  document.getElementById("remDestructWarn").style.display=destr?"block":"none";
  document.getElementById("remModal").style.display="flex";
  document.body.style.overflow="hidden";
}
function closeRemediationModal() { document.getElementById("remModal").style.display="none"; document.body.style.overflow=""; }
document.addEventListener("keydown",e=>{ if(e.key==="Escape")closeRemediationModal(); });
function onRemConfirmChange() { document.getElementById("remConfirmBtn").disabled=!document.getElementById("remConfirmCheck").checked; }

async function confirmRemediate() {
  if(!_remFinding||!state.authInfo) return;
  const f=_remFinding;
  document.getElementById("remConfirmSection").style.display="none";
  document.getElementById("remStepsWrap").style.display="block";
  document.getElementById("remSteps").innerHTML=`<div class="rem-step running"><span class="step-icon">⏳</span><span class="step-msg">Executing…</span></div>`;
  try {
    const res = await fetch("/api/remediate", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ account_id: state.authInfo.account_id, region: state.authInfo.region, finding: f }),
    });
    const data = await res.json();
    if(!res.ok) { document.getElementById("remSteps").innerHTML=`<div class="rem-step error"><span class="step-icon">❌</span><span class="step-msg">${esc(data.error)}</span></div>`; return; }
    const el=document.getElementById("remSteps"); el.innerHTML="";
    for(const step of (data.steps||[])) { await animateStep(el,step); }
    const done=document.getElementById("remDoneMsg"); done.style.display="block";
    if(data.overall==="success") {
      done.className="rem-done success"; done.innerHTML="🎉 Remediation completed!";
      sessionStorage.setItem(`remediated_${f.category}_${f.resource_id}`,"1");
      state.remediationLog.push({title:f.title,resource_id:f.resource_id,status:"success",timestamp:new Date().toISOString(),steps:data.steps});
      const card=document.getElementById(`finding-row-${_remIdx}`);
      if(card){card.classList.add("finding-remediated"); const b=card.querySelector(".fix-btn"); if(b)b.outerHTML=`<span class="badge-remediated">✓ Done</span>`;}
    } else { done.className="rem-done error"; done.innerHTML="⚠️ Completed with errors."; }
  } catch(e) { document.getElementById("remSteps").innerHTML=`<div class="rem-step error"><span class="step-icon">❌</span><span class="step-msg">${esc(e.message)}</span></div>`; }
}

function animateStep(container, step) {
  return new Promise(resolve => {
    const icons={success:"✅",error:"❌",skipped:"⏭️",running:"⏳"};
    const div=document.createElement("div"); div.className=`rem-step ${step.status}`;
    div.innerHTML=`<span class="step-num">Step ${step.step}</span><span class="step-icon">${icons[step.status]||"🔹"}</span><span class="step-msg">${esc(step.message)}</span>`;
    container.appendChild(div); setTimeout(resolve,400);
  });
}

async function downloadReport() {
  if(!state.findings.length){alert("No data.");return;}
  const btn=document.getElementById("reportBtn"); btn.disabled=true; btn.innerHTML="⏳ Generating…";
  try {
    const res = await fetch("/api/generate-report", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ findings:state.findings, remediations:state.remediationLog, account_id:state.authInfo?.account_id||"unknown", region:state.authInfo?.region||"unknown" }),
    });
    if(!res.ok){const e=await res.json(); throw new Error(e.error);}
    const blob=await res.blob(); const url=URL.createObjectURL(blob);
    const a=document.createElement("a"); a.href=url; a.download=`AWS_Housekeeping_Report_${new Date().toISOString().slice(0,10)}.pdf`;
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
  } catch(e){alert("PDF Error: "+e.message);} finally{btn.disabled=false; btn.innerHTML="📄 PDF Report";}
}

function exportXLSX() {
  if(!state.findings.length) return;
  if(typeof XLSX==="undefined"){const s=document.createElement("script");s.src="https://cdn.sheetjs.com/xlsx-0.20.3/package/dist/xlsx.full.min.js";s.onload=_doXLSX;document.head.appendChild(s);}else{_doXLSX();}
}
function _doXLSX() {
  const wb=XLSX.utils.book_new();
  const headers=["Category","Severity","Title","Resource ID","Details","Action"];
  const rows=state.findings.map(f=>[f.category,f.severity,f.title,f.resource_id,f.details,f.action]);
  const ws=XLSX.utils.aoa_to_sheet([headers,...rows]);
  ws["!cols"]=[{wch:18},{wch:10},{wch:40},{wch:30},{wch:60},{wch:60}];
  XLSX.utils.book_append_sheet(wb,ws,"Findings");
  XLSX.writeFile(wb,`aws-housekeeping-${state.authInfo?.account_id||"report"}-${new Date().toISOString().slice(0,10)}.xlsx`);
}

function esc(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");}
function showAuthStatus(t,html){const el=document.getElementById("authStatus");el.className=`auth-status ${t}`;el.innerHTML=html;el.style.display="block";}
function hideAuthStatus(){document.getElementById("authStatus").style.display="none";}
