(function () {
  "use strict";

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function csrfToken() {
    return String(document.querySelector(".app-navbar")?.dataset.csrfToken || "");
  }

  function clientHost() {
    return String(document.querySelector("[data-ip-client-tools]")?.dataset.host || "");
  }

  function post(url, data) {
    const body = new URLSearchParams({ csrf_token: csrfToken(), ...data });
    return fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest"
      },
      body: body.toString()
    }).then(async function (response) {
      const payload = await response.json().catch(function () { return {}; });
      if (!response.ok) throw new Error(payload.message || `Request failed (${response.status})`);
      return payload;
    });
  }

  function status(message, error) {
    const target = document.querySelector("[data-port-knowledge-status]");
    if (!target) return;
    target.className = `alert ${error ? "alert-danger" : "alert-info"} mt-3`;
    target.textContent = message;
  }

  function mappingForPort(mappings, port, protocol) {
    return (mappings || []).find(function (item) {
      return Number(item.port) === Number(port) && String(item.protocol) === String(protocol || "tcp");
    });
  }

  function renderOpenPorts(knowledge) {
    const identity = knowledge.identity || {};
    return (knowledge.open_ports || []).map(function (port) {
      const protocol = port.protocol || "tcp";
      const mapping = mappingForPort(knowledge.mappings, port.port, protocol);
      const scannedService = port.service || "Unknown";
      const mapped = mapping
        ? `<div><strong>${escapeHtml(mapping.service)}</strong><br><small>${escapeHtml(mapping.description || "")}</small></div>`
        : `<span class="text-muted">No reusable mapping</span>`;
      const source = mapping && mapping.source_url
        ? `<a href="${escapeHtml(mapping.source_url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(mapping.source_name || "Source")}</a>`
        : escapeHtml(mapping?.source_name || "");
      return `
        <tr>
          <td><strong>${escapeHtml(port.port)}/${escapeHtml(protocol)}</strong></td>
          <td>${escapeHtml(scannedService)}${port.description ? `<br><small>${escapeHtml(port.description)}</small>` : ""}</td>
          <td>${mapped}${source ? `<br><small>${source}</small>` : ""}</td>
          <td>
            <details>
              <summary>${mapping ? "Update mapping" : "Add mapping"}</summary>
              <form data-port-mapping-form data-port="${escapeHtml(port.port)}" data-protocol="${escapeHtml(protocol)}" class="mt-2">
                <input class="form-control form-control-sm mb-1" name="service" value="${escapeHtml(mapping?.service || (scannedService === "Unknown" ? "" : scannedService))}" placeholder="Service name" required>
                <input class="form-control form-control-sm mb-1" name="description" value="${escapeHtml(mapping?.description || port.description || "")}" placeholder="What this port does">
                <input class="form-control form-control-sm mb-1" name="sourceName" value="${escapeHtml(mapping?.source_name || "Manual research")}" placeholder="Source name">
                <input class="form-control form-control-sm mb-1" name="sourceUrl" value="${escapeHtml(mapping?.source_url || "")}" placeholder="https://source.example/...">
                <button class="btn btn-primary btn-sm" type="submit">Save for ${escapeHtml(identity.model || "this model")}</button>
              </form>
            </details>
          </td>
        </tr>`;
    }).join("") || `<tr><td colspan="4" class="text-muted">Run a port scan first.</td></tr>`;
  }

  function renderMappings(knowledge) {
    return (knowledge.mappings || []).map(function (item) {
      return `<li>
        <strong>${escapeHtml(item.port)}/${escapeHtml(item.protocol)}</strong>
        — ${escapeHtml(item.service)}
        <span class="badge badge-light border">${escapeHtml(item.confidence)}</span>
        ${item.description ? `<small>${escapeHtml(item.description)}</small>` : ""}
        <button class="btn btn-link btn-sm text-danger" data-delete-port-mapping="${escapeHtml(item.id)}" type="button">Delete</button>
      </li>`;
    }).join("") || `<li class="text-muted">No approved mappings for this model yet.</li>`;
  }

  function renderCandidates(knowledge) {
    return (knowledge.candidates || []).map(function (item) {
      return `<li>
        <strong>${escapeHtml(item.port)}/${escapeHtml(item.protocol)}</strong>
        — ${escapeHtml(item.service)}
        <small>${escapeHtml(item.description || "")}</small>
        <span class="badge badge-light border">${escapeHtml(item.observations)} observations · ${escapeHtml(item.distinct_devices)} devices</span>
        <button class="btn btn-outline-success btn-sm" data-approve-port-candidate="${escapeHtml(item.id)}" type="button">Approve</button>
      </li>`;
    }).join("") || `<li class="text-muted">No unapproved learned candidates.</li>`;
  }

  function render(payload) {
    const knowledge = payload.knowledge || payload;
    const identity = knowledge.identity || {};
    const root = document.querySelector("[data-port-knowledge]");
    if (!root) return;
    root.innerHTML = `
      <div class="card-body">
        <div class="d-flex justify-content-between align-items-start flex-wrap">
          <div>
            <h2 class="theme-section-title">Model Port Knowledge</h2>
            <p class="text-muted">Save researched port meanings once and reuse them for every device identified as the same model.</p>
          </div>
          <a class="btn btn-outline-secondary btn-sm" href="/port-knowledge/export.json">Export registry</a>
        </div>

        <div class="form-row">
          <div class="col-md-5">
            <label>Manufacturer</label>
            <input class="form-control" data-port-knowledge-manufacturer value="${escapeHtml(identity.manufacturer || "")}" placeholder="Sky, Synology, Ubiquiti">
          </div>
          <div class="col-md-7">
            <label>Exact model</label>
            <input class="form-control" data-port-knowledge-model value="${escapeHtml(identity.model || "")}" placeholder="SR203, RT6600ax, UDM-Pro">
          </div>
        </div>
        <p class="small text-muted mt-2">Correct these fields before saving a mapping if the automatic model is too broad.</p>

        <div class="theme-actions">
          <button class="btn btn-outline-primary" type="button" data-port-knowledge-learn>Learn from saved scan</button>
          <button class="btn btn-outline-info" type="button" data-port-knowledge-probe>Use safe probes and learn</button>
          ${knowledge.configured_registry_count ? `<button class="btn btn-outline-success" type="button" data-port-knowledge-sync>Sync ${escapeHtml(knowledge.configured_registry_count)} configured registry source(s)</button>` : ""}
        </div>
        <div data-port-knowledge-status class="alert alert-light mt-3">Ready.</div>

        <div class="table-responsive">
          <table class="table table-sm">
            <thead><tr><th>Port</th><th>Scan result</th><th>Model knowledge</th><th>Research mapping</th></tr></thead>
            <tbody>${renderOpenPorts(knowledge)}</tbody>
          </table>
        </div>

        <div class="row">
          <div class="col-lg-6">
            <h3 class="theme-subsection-title">Approved mappings</h3>
            <ul>${renderMappings(knowledge)}</ul>
          </div>
          <div class="col-lg-6">
            <h3 class="theme-subsection-title">Learned candidates</h3>
            <ul>${renderCandidates(knowledge)}</ul>
          </div>
        </div>

        <details class="mt-3">
          <summary>Import a structured port registry</summary>
          <p class="small text-muted mt-2">Use the exported <code>mobile-router-port-knowledge-v1</code> JSON format. Imported entries retain their source URLs.</p>
          <textarea class="form-control" rows="5" data-port-registry-json placeholder='{"schema":"mobile-router-port-knowledge-v1","mappings":[]}'></textarea>
          <button class="btn btn-outline-secondary btn-sm mt-2" type="button" data-port-registry-import>Import JSON</button>
        </details>
      </div>`;
  }

  function reload() {
    const host = clientHost();
    if (!host) return Promise.resolve();
    return fetch(`/clients/${encodeURIComponent(host)}/port-knowledge`, {
      headers: { "X-Requested-With": "XMLHttpRequest" }
    })
      .then(async function (response) {
        const payload = await response.json().catch(function () { return {}; });
        if (!response.ok) throw new Error(payload.message || "Unable to load port knowledge");
        render(payload.knowledge);
        if (payload.knowledge.needs_application) {
          const key = `mobile-router:port-knowledge:${host}:${payload.knowledge.application_token}`;
          if (!window.sessionStorage.getItem(key)) {
            window.sessionStorage.setItem(key, "1");
            status("Applying reusable mappings for this model…");
            return post(`/clients/${encodeURIComponent(host)}/port-knowledge/learn`, {})
              .then(function (learned) {
                render(learned.knowledge);
                status("Reusable model mappings applied automatically.");
              });
          }
        }
        return null;
      })
      .catch(function (error) { status(error.message, true); });
  }

  function inject() {
    const tools = document.querySelector("[data-ip-client-tools]");
    if (!tools || document.querySelector("[data-port-knowledge]")) return;
    const section = document.createElement("section");
    section.className = "theme-card card";
    section.setAttribute("data-port-knowledge", "");
    section.innerHTML = `<div class="card-body"><p class="text-muted mb-0">Loading model port knowledge…</p></div>`;
    tools.parentNode.insertBefore(section, tools);
    reload();
  }

  document.addEventListener("submit", function (event) {
    const form = event.target.closest("[data-port-mapping-form]");
    if (!form) return;
    event.preventDefault();
    const host = clientHost();
    const data = new FormData(form);
    status("Saving reusable model mapping…");
    post(`/clients/${encodeURIComponent(host)}/port-knowledge/mappings`, {
      manufacturer: document.querySelector("[data-port-knowledge-manufacturer]")?.value || "",
      model: document.querySelector("[data-port-knowledge-model]")?.value || "",
      port: form.dataset.port,
      protocol: form.dataset.protocol,
      service: data.get("service") || "",
      description: data.get("description") || "",
      sourceName: data.get("sourceName") || "",
      sourceUrl: data.get("sourceUrl") || ""
    }).then(function (payload) {
      render(payload.knowledge);
      status("Mapping saved and applied to this device.");
    }).catch(function (error) { status(error.message, true); });
  });

  document.addEventListener("click", function (event) {
    const host = clientHost();
    if (!host) return;

    if (event.target.closest("[data-port-knowledge-learn]")) {
      status("Recording candidates and applying known mappings…");
      post(`/clients/${encodeURIComponent(host)}/port-knowledge/learn`, {})
        .then(function (payload) {
          render(payload.knowledge);
          status("Saved scan processed.");
        }).catch(function (error) { status(error.message, true); });
    }

    if (event.target.closest("[data-port-knowledge-probe]")) {
      status("Running bounded safe probes against already-open ports…");
      post(`/clients/${encodeURIComponent(host)}/port-knowledge/learn`, { activeProbe: "on" })
        .then(function (payload) {
          render(payload.knowledge);
          status("Safe probes completed and candidates updated.");
        }).catch(function (error) { status(error.message, true); });
    }

    const approve = event.target.closest("[data-approve-port-candidate]");
    if (approve) {
      status("Approving learned mapping…");
      post(`/clients/${encodeURIComponent(host)}/port-knowledge/candidates/${approve.dataset.approvePortCandidate}/approve`, {})
        .then(function (payload) {
          render(payload.knowledge);
          status("Candidate approved and applied.");
        }).catch(function (error) { status(error.message, true); });
    }

    const remove = event.target.closest("[data-delete-port-mapping]");
    if (remove) {
      status("Deleting mapping…");
      post(`/clients/${encodeURIComponent(host)}/port-knowledge/mappings/${remove.dataset.deletePortMapping}/delete`, {})
        .then(function (payload) {
          render(payload.knowledge);
          status("Mapping deleted.");
        }).catch(function (error) { status(error.message, true); });
    }

    if (event.target.closest("[data-port-knowledge-sync]")) {
      status("Synchronising configured registries…");
      post("/port-knowledge/sync", {})
        .then(function () {
          status("Registry synchronisation completed.");
          return reload();
        }).catch(function (error) { status(error.message, true); });
    }

    if (event.target.closest("[data-port-registry-import]")) {
      const registryJson = document.querySelector("[data-port-registry-json]")?.value || "";
      status("Importing registry…");
      post("/port-knowledge/import", { registryJson: registryJson })
        .then(function () {
          status("Registry imported.");
          return reload();
        }).catch(function (error) { status(error.message, true); });
    }
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", inject);
  } else {
    inject();
  }
}());
