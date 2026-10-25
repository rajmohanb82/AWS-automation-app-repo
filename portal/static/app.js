function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[char]));
}

async function api(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": window.CSRF },
    body: JSON.stringify(body || {}),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || "The request failed.");
  return data;
}

function fillSelect(select, options, selected) {
  select.innerHTML = "";
  if (!options.length) {
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "None yet";
    select.appendChild(empty);
    return;
  }
  options.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.value;
    option.textContent = item.label;
    if (String(item.value) === String(selected)) option.selected = true;
    select.appendChild(option);
  });
}

function requireScope() {
  const account = document.getElementById("sel-account");
  const region = document.getElementById("sel-region");
  if (!account || !account.value) {
    throw new Error("Add an account in Scope, then choose it in the header.");
  }
  return { account_pk: Number(account.value), region: region.value };
}

function accountLabel() {
  const select = document.getElementById("sel-account");
  return select && select.selectedOptions[0] ? select.selectedOptions[0].textContent : "account";
}

function initScope() {
  const data = window.APP || {};
  const account = document.getElementById("sel-account");
  const region = document.getElementById("sel-region");
  if (!account || !region || !data.regions) return;
  const selection = data.selection || {};
  fillSelect(region, data.regions.map((item) => ({ value: item.code, label: item.name })), selection.region || "ap-south-1");

  const save = () => {
    const payload = {
      account_pk: account.value,
      region: region.value,
      customer_id: document.getElementById("sel-customer")?.value,
      product_id: document.getElementById("sel-product")?.value,
      environment_id: document.getElementById("sel-environment")?.value,
    };
    api("/api/selection", payload).catch(() => {});
  };

  if (data.mode === "msp") {
    const customer = document.getElementById("sel-customer");
    const customers = data.customers || [];
    fillSelect(customer, customers.map((item) => ({ value: item.id, label: item.name })), selection.customer_id);
    const paintAccounts = () => {
      const current = customers.find((item) => String(item.id) === String(customer.value));
      const options = (current?.accounts || []).map((item) => ({
        value: item.id,
        label: `${item.name} (${item.account_id})`,
        region: item.default_region,
      }));
      fillSelect(account, options, selection.account_pk);
    };
    customer.addEventListener("change", () => { paintAccounts(); save(); });
    paintAccounts();
  } else {
    const products = data.products || [];
    const productSelect = document.getElementById("sel-product");
    const environment = document.getElementById("sel-environment");
    if (productSelect) {
      fillSelect(productSelect, products.map((item) => ({ value: item.id, label: item.name })), selection.product_id);
    }
    const currentProduct = () => {
      if (productSelect && productSelect.value) {
        return products.find((item) => String(item.id) === String(productSelect.value));
      }
      return products[0];
    };
    const paintEnvironments = () => {
      const product = currentProduct();
      const options = (product?.environments || []).map((item) => ({ value: item.id, label: item.name }));
      fillSelect(environment, options, selection.environment_id);
      paintAccounts();
    };
    const paintAccounts = () => {
      const product = currentProduct();
      const env = (product?.environments || []).find((item) => String(item.id) === String(environment.value));
      const options = (env?.accounts || []).map((item) => ({
        value: item.id,
        label: `${item.name} (${item.account_id})`,
        region: item.default_region,
      }));
      fillSelect(account, options, selection.account_pk);
    };
    productSelect?.addEventListener("change", () => { paintEnvironments(); save(); });
    environment?.addEventListener("change", () => { paintAccounts(); save(); });
    paintEnvironments();
  }

  account.addEventListener("change", () => {
    const chosenRegion = account.selectedOptions[0]?.dataset?.region;
    if (chosenRegion) region.value = chosenRegion;
    save();
  });
  region.addEventListener("change", save);
  save();
}

function setStatus(text, isError) {
  const box = document.getElementById("work-status");
  if (!box) return;
  box.hidden = !text;
  box.textContent = text || "";
  box.className = isError ? "note flash-error" : "note";
}

function pill(value) {
  const severity = String(value || "INFO").toLowerCase();
  return `<span class="pill pill-${escapeHtml(severity)}">${escapeHtml(value || "INFO")}</span>`;
}

function initHousekeeping() {
  const button = document.getElementById("scan-btn");
  if (!button) return;
  let findings = [];
  let severity = "ALL";
  const draw = () => {
    const rows = findings.filter((item) => severity === "ALL" || item.severity === severity);
    const target = document.getElementById("work-results");
    if (!rows.length) {
      target.innerHTML = `<p class="empty">${findings.length ? "Nothing in this severity." : "This scan returned no findings."}</p>`;
      return;
    }
    const admin = window.APP.role === "admin";
    target.innerHTML = `<table><thead><tr><th>Severity</th><th>Finding</th><th>Resource</th><th>Evidence</th><th></th></tr></thead><tbody>${
      rows.map((item, index) => `<tr>
        <td>${pill(item.severity)}</td>
        <td><strong>${escapeHtml(item.title)}</strong><br><a href="${escapeHtml(item.documentation_url)}" target="_blank" rel="noreferrer">AWS documentation</a></td>
        <td class="mono">${escapeHtml(item.resource_id)}</td>
        <td>${escapeHtml(item.details)}<br><span class="hint">${escapeHtml(item.action)}</span></td>
        <td>${admin && item.severity !== "INFO" ? `<button type="button" class="secondary" data-fix="${index}">Apply fix</button>` : ""}</td>
      </tr>`).join("")
    }</tbody></table>`;
    target.querySelectorAll("[data-fix]").forEach((fix) => {
      fix.addEventListener("click", async () => {
        if (!window.confirm("Apply this fix in the AWS account? It changes live resources.")) return;
        fix.disabled = true;
        try {
          const result = await api("/api/housekeeping/remediate", { ...requireScope(), finding: rows[Number(fix.dataset.fix)] });
          const messages = (result.steps || []).map((step) => step.message).join(" ");
          setStatus(`${result.overall}. ${messages}`, result.overall === "error");
        } catch (error) {
          setStatus(error.message, true);
        } finally {
          fix.disabled = false;
        }
      });
    });
  };
  document.getElementById("severity-filters").addEventListener("click", (event) => {
    const chip = event.target.closest("[data-severity]");
    if (!chip) return;
    severity = chip.dataset.severity;
    document.querySelectorAll("#severity-filters .chip").forEach((item) => {
      item.setAttribute("aria-pressed", item === chip ? "true" : "false");
    });
    draw();
  });
  button.addEventListener("click", async () => {
    button.disabled = true;
    setStatus("Scanning the selected account and region.");
    try {
      const result = await api("/api/housekeeping/scan", requireScope());
      findings = result.findings || [];
      document.getElementById("severity-filters").hidden = false;
      const summary = document.getElementById("work-summary");
      const counts = result.summary?.counts || {};
      summary.hidden = false;
      summary.innerHTML = ["HIGH", "MEDIUM", "LOW", "INFO"].map((key) => `<article><span>${key}</span><strong>${counts[key] || 0}</strong></article>`).join("");
      setStatus(`${findings.length} findings.`);
      draw();
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      button.disabled = false;
    }
  });
  document.getElementById("pdf-btn").addEventListener("click", () => downloadPdf("/api/housekeeping/pdf", { findings }));
}

let costState = { recommendations: [], notes: [] };

function drawCost(recommendations) {
  const target = document.getElementById("work-results");
  if (!recommendations.length) {
    target.innerHTML = `<p class="empty">No recommendations in this response.</p>`;
    return;
  }
  target.innerHTML = `<table><thead><tr><th>Priority</th><th>Resource</th><th>Advice</th><th>Saving / month</th><th>Source</th></tr></thead><tbody>${
    recommendations.map((item) => `<tr>
      <td>${pill(item.priority)}</td>
      <td><strong>${escapeHtml(item.resource_name || item.resource_id)}</strong><br><span class="mono">${escapeHtml(item.service)}</span></td>
      <td>${escapeHtml(item.action)}<br><span class="hint">${escapeHtml(item.reasoning)}</span><br><span class="hint">${escapeHtml(item.evidence || "")}</span><br><a href="${escapeHtml(item.documentation_url)}" target="_blank" rel="noreferrer">AWS documentation</a></td>
      <td class="mono">$${Number(item.monthly_saving || 0).toFixed(2)}</td>
      <td>${escapeHtml(item.source)}</td>
    </tr>`).join("")
  }</tbody></table>`;
}

function initCost() {
  const native = document.getElementById("native-btn");
  if (!native) return;
  const run = async (url, button) => {
    button.disabled = true;
    setStatus("Contacting AWS for this account.");
    try {
      const result = await api(url, requireScope());
      costState = result;
      const notes = (result.notes || []).concat(result.errors || []);
      setStatus(notes.join(" "));
      const kpis = document.getElementById("cost-kpis");
      if (result.actual_30d_ce_cost != null) {
        kpis.hidden = false;
        kpis.innerHTML = `<article><span>Cost Explorer, 30 days</span><strong>$${Number(result.actual_30d_ce_cost).toFixed(2)}</strong></article>
          <article><span>List-price inventory</span><strong>$${Number(result.total_cost || 0).toFixed(2)}</strong></article>
          <article><span>Estimated saving</span><strong>$${Number(result.total_saving || 0).toFixed(2)}</strong></article>`;
      } else {
        kpis.hidden = true;
      }
      drawCost(result.recommendations || []);
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      button.disabled = false;
    }
  };
  native.addEventListener("click", () => run("/api/cost/recommendations", native));
  const inventory = document.getElementById("inventory-btn");
  inventory.addEventListener("click", () => run("/api/cost/inventory", inventory));
  document.getElementById("pdf-btn").addEventListener("click", () => downloadPdf("/api/cost/pdf", {
    recommendations: costState.recommendations || [],
    notes: costState.notes || [],
  }));
}

function initGovernance() {
  const button = document.getElementById("scan-btn");
  if (!button) return;
  let findings = [];
  let pillar = "All";
  const draw = () => {
    const rows = findings.filter((item) => pillar === "All" || item.pillar === pillar);
    const target = document.getElementById("work-results");
    if (!rows.length) {
      target.innerHTML = `<p class="empty">No findings in this pillar.</p>`;
      return;
    }
    target.innerHTML = `<table><thead><tr><th>Pillar</th><th>Severity</th><th>Finding</th><th>Resource</th></tr></thead><tbody>${
      rows.map((item) => `<tr>
        <td>${escapeHtml(item.pillar)}</td>
        <td>${pill(item.severity)}</td>
        <td><strong>${escapeHtml(item.title)}</strong><br><span class="hint">${escapeHtml(item.action)}</span><br><a href="${escapeHtml(item.documentation_url)}" target="_blank" rel="noreferrer">AWS documentation</a></td>
        <td class="mono">${escapeHtml(item.resource_id)}<br><span class="hint">${escapeHtml(item.details)}</span></td>
      </tr>`).join("")
    }</tbody></table>`;
  };
  button.addEventListener("click", async () => {
    button.disabled = true;
    setStatus("Assessing the selected account.");
    try {
      const result = await api("/api/governance/scan", requireScope());
      findings = result.findings || [];
      const filters = document.getElementById("pillar-filters");
      const names = ["All", ...Object.keys(result.pillars || {})];
      filters.hidden = false;
      filters.innerHTML = names.map((name) => {
        const count = name === "All" ? findings.length : (result.pillars[name] || 0);
        return `<button type="button" class="chip" data-pillar="${escapeHtml(name)}" aria-pressed="${name === "All"}">${escapeHtml(name)} ${count}</button>`;
      }).join("");
      filters.onclick = (event) => {
        const chip = event.target.closest("[data-pillar]");
        if (!chip) return;
        pillar = chip.dataset.pillar;
        filters.querySelectorAll(".chip").forEach((item) => item.setAttribute("aria-pressed", item === chip ? "true" : "false"));
        draw();
      };
      const advisorBox = document.getElementById("advisor-note");
      const trusted = result.trusted_advisor || {};
      advisorBox.hidden = false;
      if (trusted.available) {
        const lines = (trusted.recommendations || []).slice(0, 8).map((item) => `${item.name} (${item.status || "open"})`);
        advisorBox.textContent = lines.length
          ? `Trusted Advisor: ${lines.join("; ")}`
          : "Trusted Advisor returned no recommendation summaries.";
      } else {
        advisorBox.textContent = trusted.reason || "Trusted Advisor was not queried.";
      }
      setStatus(`${findings.length} posture findings.`);
      draw();
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      button.disabled = false;
    }
  });
}

async function downloadPdf(url, extra) {
  try {
    const scope = requireScope();
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": window.CSRF },
      body: JSON.stringify({ ...extra, ...scope, account_name: accountLabel() }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.error || "The PDF could not be created.");
    }
    const blob = await response.blob();
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "report.pdf";
    link.click();
    URL.revokeObjectURL(link.href);
  } catch (error) {
    setStatus(error.message, true);
  }
}

function showNote(id, text, isError) {
  const box = document.getElementById(id);
  if (!box) return;
  box.hidden = !text;
  box.textContent = text || "";
  box.className = isError ? "note flash-error" : "note";
}

function initSettings() {
  const test = document.getElementById("aws-test");
  if (!test) return;
  test.addEventListener("click", async () => {
    test.disabled = true;
    showNote("aws-result", "Testing the saved connection.");
    try {
      const region = document.getElementById("link-region")?.value || "us-east-1";
      const selected = document.querySelector('input[name="mode"]:checked');
      const result = await api("/api/aws/test", {
        region,
        mode: selected ? selected.value : "",
        profile_name: document.getElementById("profile_name")?.value,
        sso_start_url: document.getElementById("sso_start_url")?.value,
        sso_region: document.getElementById("sso_region")?.value,
        sso_account_id: document.getElementById("sso_account_id")?.value,
        sso_role_name: document.getElementById("sso_role_name")?.value,
      });
      showNote("aws-result", `Connected as ${result.arn} in account ${result.account}.`);
    } catch (error) {
      showNote("aws-result", error.message, true);
    } finally {
      test.disabled = false;
    }
  });
  const start = document.getElementById("sso-start");
  start.addEventListener("click", async () => {
    start.disabled = true;
    const ssoMode = document.querySelector('input[name="mode"][value="sso"]');
    if (ssoMode) ssoMode.checked = true;
    try {
      const result = await api("/api/aws/sso/start", {
        sso_start_url: document.getElementById("sso_start_url").value,
        sso_region: document.getElementById("sso_region").value,
        sso_account_id: document.getElementById("sso_account_id").value,
        sso_role_name: document.getElementById("sso_role_name").value,
      });
      const box = document.getElementById("sso-box");
      box.hidden = false;
      box.innerHTML = `Approve access at <a href="${escapeHtml(result.verification_uri)}" target="_blank" rel="noreferrer">${escapeHtml(result.verification_uri)}</a>. Code <strong>${escapeHtml(result.user_code || "")}</strong>.`;
      pollSso(0);
    } catch (error) {
      showNote("aws-result", error.message, true);
      start.disabled = false;
    }
  });
}

async function pollSso(attempt) {
  if (attempt > 40) {
    showNote("aws-result", "The Identity Center prompt expired. Start sign-in again.", true);
    document.getElementById("sso-start").disabled = false;
    return;
  }
  try {
    const result = await api("/api/aws/sso/poll", {});
    if (result.status === "pending") {
      setTimeout(() => pollSso(attempt + 1), 3000);
      return;
    }
    if (result.status === "expired") {
      showNote("aws-result", "The Identity Center code expired. Start sign-in again.", true);
    } else {
      showNote("aws-result", "Identity Center sign-in completed. Save the connection if you have not already.");
    }
  } catch (error) {
    showNote("aws-result", error.message, true);
  }
  document.getElementById("sso-start").disabled = false;
}

function initSetup() {
  const cardinality = document.getElementById("cardinality");
  const modes = document.querySelectorAll('input[name="mode"]');
  if (!cardinality || !modes.length) return;
  const sync = () => {
    const selected = document.querySelector('input[name="mode"]:checked');
    cardinality.hidden = !selected || selected.value === "msp";
  };
  modes.forEach((input) => input.addEventListener("change", sync));
  sync();
}

document.addEventListener("DOMContentLoaded", () => {
  const page = document.body.dataset.page;
  initScope();
  initSetup();
  if (page === "housekeeping") initHousekeeping();
  if (page === "cost") initCost();
  if (page === "governance") initGovernance();
  if (page === "settings") initSettings();
});
