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

  async function jsonRequest(url, options) {
    const response = await fetch(url, options || {});
    const payload = await response.json().catch(function () { return {}; });
    if (!response.ok) {
      const error = new Error(payload.message || `Request failed (${response.status})`);
      error.payload = payload;
      throw error;
    }
    return payload;
  }

  function post(url, data) {
    const body = new URLSearchParams({ csrf_token: csrfToken(), ...(data || {}) });
    return jsonRequest(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest"
      },
      body: body.toString()
    });
  }

  function formDataObject(form) {
    const result = {};
    new FormData(form).forEach(function (value, name) {
      if (form.elements[name]?.type === "checkbox") {
        result[name] = form.elements[name].checked ? "on" : "";
      } else {
        result[name] = value;
      }
    });
    return result;
  }

  function status(target, message, error) {
    if (!target) return;
    target.className = `alert ${error ? "alert-danger" : "alert-info"} mt-3`;
    target.textContent = message;
  }

  function badge(value, style) {
    return `<span class="badge badge-${style || "light"} border">${escapeHtml(value)}</span>`;
  }

  function riskBadge(risk) {
    const style = {
      critical: "danger", high: "danger", medium: "warning",
      low: "info", info: "light", none: "success"
    }[risk] || "secondary";
    return badge(risk || "info", style);
  }

  function profileName(profile) {
    if (profile.scope === "manufacturer") return `${profile.manufacturer} defaults`;
    if (profile.scope === "family") return `${profile.manufacturer} ${profile.family} family`;
    return `${profile.manufacturer} ${profile.model}`;
  }

  async function loadLibrary() {
    const root = document.querySelector("[data-model-library]");
    if (!root) return;
    const output = root.querySelector("[data-model-profile-list]");
    const state = root.querySelector("[data-model-library-status]");
    const query = root.querySelector("[data-model-search]")?.value || "";
    const scope = root.querySelector("[data-model-scope-filter]")?.value || "";
    status(state, "Loading profiles…");
    try {
      const payload = await jsonRequest(`/api/model-profiles?q=${encodeURIComponent(query)}&scope=${encodeURIComponent(scope)}`);
      output.innerHTML = payload.profiles.map(function (profile) {
        const applicability = [
          profile.hardware_revision ? `HW ${profile.hardware_revision}` : "All hardware",
          profile.firmware_min || profile.firmware_max
            ? `FW ${profile.firmware_min || "*"}–${profile.firmware_max || "*"}`
            : "All firmware"
        ].join(" · ");
        return `<article class="port-service-card">
          <div class="d-flex justify-content-between align-items-start">
            <div>
              <strong>${escapeHtml(profileName(profile))}</strong>
              <small>${escapeHtml(applicability)}</small>
            </div>
            ${badge(profile.scope, "info")}
          </div>
          <p class="mb-1">${escapeHtml(profile.notes || "No profile notes yet.")}</p>
          <small>${escapeHtml(profile.port_count)} port rule(s) · ${escapeHtml((profile.aliases || []).join(", ") || "No aliases")}</small>
          <a class="btn btn-outline-primary btn-sm mt-2" href="/models/${profile.id}">Open Profile</a>
        </article>`;
      }).join("") || `<p class="text-muted">No matching model profiles.</p>`;
      status(state, `${payload.profiles.length} profile(s) loaded.`);
    } catch (error) {
      status(state, error.message, true);
    }
  }

  function setupLibrary() {
    const root = document.querySelector("[data-model-library]");
    if (!root) return;
    root.querySelector("[data-model-search]")?.addEventListener("input", function () {
      window.clearTimeout(root._modelSearchTimer);
      root._modelSearchTimer = window.setTimeout(loadLibrary, 180);
    });
    root.querySelector("[data-model-scope-filter]")?.addEventListener("change", loadLibrary);
    root.querySelector("[data-model-new-toggle]")?.addEventListener("click", function () {
      root.querySelector("[data-model-new-panel]")?.classList.toggle("d-none");
    });
    root.querySelector("[data-model-profile-create]")?.addEventListener("submit", async function (event) {
      event.preventDefault();
      const state = root.querySelector("[data-model-library-status]");
      status(state, "Creating profile…");
      try {
        const payload = await post("/api/model-profiles", formDataObject(event.target));
        window.location.href = `/models/${payload.profile.id}`;
      } catch (error) {
        status(state, error.message, true);
      }
    });
    root.querySelector("[data-model-registry-preview]")?.addEventListener("click", async function () {
      const registryJson = root.querySelector("[data-model-registry-json]")?.value || "";
      const output = root.querySelector("[data-model-registry-output]");
      try {
        const payload = await post("/api/model-registry/preview", {
          registryJson: registryJson,
          requireSignature: root.querySelector("[data-model-registry-require-signature]")?.checked ? "on" : ""
        });
        output.textContent = JSON.stringify(payload, null, 2);
      } catch (error) {
        output.textContent = error.message;
      }
    });
    root.querySelector("[data-model-registry-import]")?.addEventListener("click", async function () {
      const registryJson = root.querySelector("[data-model-registry-json]")?.value || "";
      const output = root.querySelector("[data-model-registry-output]");
      try {
        const payload = await post("/api/model-registry/import", {
          registryJson: registryJson,
          requireSignature: root.querySelector("[data-model-registry-require-signature]")?.checked ? "on" : ""
        });
        output.textContent = JSON.stringify(payload, null, 2);
        await loadLibrary();
      } catch (error) {
        output.textContent = error.message;
      }
    });
    root.querySelector("[data-model-registry-sync]")?.addEventListener("click", async function () {
      const output = root.querySelector("[data-model-registry-output]");
      try {
        const payload = await post("/api/model-registry/sync", {});
        output.textContent = JSON.stringify(payload, null, 2);
        await loadLibrary();
      } catch (error) {
        output.textContent = error.message;
      }
    });
    loadLibrary();
  }

  function populateProfileForm(root, profile) {
    const form = root.querySelector("[data-model-profile-update]");
    if (!form) return;
    const values = {
      scope: profile.scope,
      manufacturer: profile.manufacturer,
      model: profile.model,
      family: profile.family,
      hardwareRevision: profile.hardware_revision,
      firmwareMin: profile.firmware_min,
      firmwareMax: profile.firmware_max,
      aliases: (profile.aliases || []).join(", "),
      manufacturerAliases: (profile.manufacturer_aliases || []).join(", "),
      notes: profile.notes,
      riskNotes: profile.risk_notes
    };
    Object.keys(values).forEach(function (name) {
      if (form.elements[name]) form.elements[name].value = values[name] || "";
    });
  }

  function renderPortRules(root, profile) {
    const target = root.querySelector("[data-model-port-list]");
    if (!target) return;
    target.innerHTML = (profile.ports || []).map(function (rule) {
      const applicability = [
        rule.hardware_revision ? `HW ${rule.hardware_revision}` : "all hardware",
        rule.firmware_min || rule.firmware_max
          ? `FW ${rule.firmware_min || "*"}–${rule.firmware_max || "*"}`
          : "all firmware"
      ].join(" · ");
      const source = rule.source_url
        ? `<a href="${escapeHtml(rule.source_url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(rule.source_name || "Source")}</a>`
        : escapeHtml(rule.source_name || "Local");
      return `<tr>
        <td><strong>${escapeHtml(rule.port)}/${escapeHtml(rule.protocol)}</strong></td>
        <td><strong>${escapeHtml(rule.service)}</strong><br><small>${escapeHtml(rule.description || "")}</small></td>
        <td>${badge(rule.classification, rule.classification === "deprecated" ? "danger" : "info")}<br><small>${escapeHtml(rule.exposure)}</small></td>
        <td><small>${escapeHtml(applicability)}</small></td>
        <td>${riskBadge(rule.risk)}<br><small>${escapeHtml(rule.remediation || "")}</small></td>
        <td><small>${source}<br>Reliability ${escapeHtml(rule.source_reliability)}/100</small></td>
        <td><button class="btn btn-link btn-sm text-danger" type="button" data-model-rule-delete="${rule.id}">Delete</button></td>
      </tr>`;
    }).join("") || `<tr><td colspan="7" class="text-muted">No port rules yet.</td></tr>`;
  }

  function renderConflicts(root, profile) {
    const target = root.querySelector("[data-model-conflicts]");
    if (!target) return;
    target.innerHTML = (profile.conflicts || []).map(function (conflict) {
      const current = conflict.current || {};
      const incoming = conflict.incoming || {};
      return `<article class="alert alert-warning">
        <strong>${escapeHtml(conflict.port)}/${escapeHtml(conflict.protocol)} conflict</strong>
        <p class="mb-1">Current: ${escapeHtml(current.service)} · ${escapeHtml(current.classification)}</p>
        <p class="mb-1">Incoming: ${escapeHtml(incoming.service)} · ${escapeHtml(incoming.classification)}</p>
        <textarea class="form-control form-control-sm mb-2" data-conflict-note="${conflict.id}" placeholder="Resolution note"></textarea>
        <button class="btn btn-outline-secondary btn-sm" type="button" data-conflict-resolve="${conflict.id}" data-choice="current">Keep Current</button>
        <button class="btn btn-outline-primary btn-sm" type="button" data-conflict-resolve="${conflict.id}" data-choice="incoming">Accept Incoming</button>
      </article>`;
    }).join("") || `<p class="text-muted">No unresolved conflicts.</p>`;
  }

  function renderHistory(root, history) {
    const target = root.querySelector("[data-model-history]");
    if (!target) return;
    target.innerHTML = (history || []).map(function (item) {
      return `<div class="d-flex justify-content-between align-items-start border-bottom py-2">
        <div><strong>Revision ${escapeHtml(item.revision)} · ${escapeHtml(item.action)}</strong><br><small>${escapeHtml(item.actor || "system")} · ${escapeHtml(new Date(item.created_at * 1000).toLocaleString())} · ${escapeHtml(item.note || "")}</small></div>
        <button class="btn btn-outline-warning btn-sm" type="button" data-model-rollback="${item.revision}">Rollback</button>
      </div>`;
    }).join("") || `<p class="text-muted">No revision history.</p>`;
  }

  function renderFleet(root, fleet) {
    const target = root.querySelector("[data-model-fleet]");
    if (!target) return;
    const devices = (fleet.devices || []).map(function (device) {
      return `<tr>
        <td>${device.ip ? `<a href="/clients/${encodeURIComponent(device.ip)}">${escapeHtml(device.display_name)}</a>` : escapeHtml(device.display_name)}</td>
        <td>${escapeHtml(device.firmware)}</td>
        <td>${escapeHtml(device.hardware_revision || "Unknown")}</td>
        <td>${riskBadge(device.drift.severity)} ${escapeHtml(device.drift.score)}/100</td>
        <td>${escapeHtml(device.drift.unexpected.length)} unexpected · ${escapeHtml(device.drift.missing_expected.length)} missing</td>
      </tr>`;
    }).join("") || `<tr><td colspan="5" class="text-muted">No matching inventory devices.</td></tr>`;
    const common = (fleet.common_ports || []).slice(0, 20).map(function (item) {
      return `<li>${escapeHtml(item.port)}/${escapeHtml(item.protocol)} · ${escapeHtml(item.devices)} device(s)</li>`;
    }).join("") || `<li class="text-muted">No common ports yet.</li>`;
    target.innerHTML = `
      <div class="alert alert-info">${escapeHtml(fleet.device_count)} matching device(s); ${escapeHtml(fleet.drifted_devices)} with profile drift.</div>
      <div class="row"><div class="col-lg-8"><div class="table-responsive"><table class="table table-sm"><thead><tr><th>Device</th><th>Firmware</th><th>Hardware</th><th>Drift</th><th>Summary</th></tr></thead><tbody>${devices}</tbody></table></div></div><div class="col-lg-4"><h3 class="theme-subsection-title">Common Ports</h3><ul>${common}</ul><h3 class="theme-subsection-title">Firmware Distribution</h3><pre>${escapeHtml(JSON.stringify(fleet.firmware_counts || {}, null, 2))}</pre></div></div>`;
  }

  async function loadProfileDetail() {
    const root = document.querySelector("[data-model-profile-detail]");
    if (!root) return;
    const profileId = root.dataset.profileId;
    const state = root.querySelector("[data-model-profile-status]");
    try {
      const [profilePayload, fleetPayload] = await Promise.all([
        jsonRequest(`/api/model-profiles/${profileId}`),
        jsonRequest(`/api/model-profiles/${profileId}/fleet`)
      ]);
      root._profile = profilePayload.profile;
      populateProfileForm(root, profilePayload.profile);
      renderPortRules(root, profilePayload.profile);
      renderConflicts(root, profilePayload.profile);
      renderHistory(root, profilePayload.history);
      renderFleet(root, fleetPayload.fleet);
      status(state, `Profile loaded with ${profilePayload.profile.ports.length} rule(s).`);
    } catch (error) {
      status(state, error.message, true);
    }
  }

  function setupProfileDetail() {
    const root = document.querySelector("[data-model-profile-detail]");
    if (!root) return;
    const profileId = root.dataset.profileId;
    root.querySelector("[data-model-port-toggle]")?.addEventListener("click", function () {
      root.querySelector("[data-model-port-panel]")?.classList.toggle("d-none");
    });
    root.querySelector("[data-model-profile-update]")?.addEventListener("submit", async function (event) {
      event.preventDefault();
      const state = root.querySelector("[data-model-profile-status]");
      try {
        await post(`/api/model-profiles/${profileId}`, formDataObject(event.target));
        status(state, "Profile saved.");
        await loadProfileDetail();
      } catch (error) {
        status(state, error.message, true);
      }
    });
    root.querySelector("[data-model-port-form]")?.addEventListener("submit", async function (event) {
      event.preventDefault();
      const state = root.querySelector("[data-model-profile-status]");
      try {
        await post(`/api/model-profiles/${profileId}/ports`, formDataObject(event.target));
        event.target.reset();
        status(state, "Port rule saved.");
        await loadProfileDetail();
      } catch (error) {
        const conflict = error.payload?.result?.conflict_id;
        status(state, conflict ? `A conflict was recorded as #${conflict}. Review it below.` : error.message, true);
        await loadProfileDetail();
      }
    });
    root.addEventListener("click", async function (event) {
      const state = root.querySelector("[data-model-profile-status]");
      const remove = event.target.closest("[data-model-rule-delete]");
      if (remove) {
        try {
          await post(`/api/model-profiles/${profileId}/ports/${remove.dataset.modelRuleDelete}/delete`, {});
          status(state, "Port rule deleted.");
          await loadProfileDetail();
        } catch (error) { status(state, error.message, true); }
      }
      const conflict = event.target.closest("[data-conflict-resolve]");
      if (conflict) {
        try {
          const note = root.querySelector(`[data-conflict-note="${conflict.dataset.conflictResolve}"]`)?.value || "";
          await post(`/api/model-profile-conflicts/${conflict.dataset.conflictResolve}/resolve`, {
            choice: conflict.dataset.choice,
            note: note
          });
          status(state, "Conflict resolved.");
          await loadProfileDetail();
        } catch (error) { status(state, error.message, true); }
      }
      const rollback = event.target.closest("[data-model-rollback]");
      if (rollback) {
        try {
          await post(`/api/model-profiles/${profileId}/rollback/${rollback.dataset.modelRollback}`, {
            note: "Rollback requested from the model library"
          });
          status(state, `Rolled back to revision ${rollback.dataset.modelRollback}.`);
          await loadProfileDetail();
        } catch (error) { status(state, error.message, true); }
      }
    });
    loadProfileDetail();
  }

  function renderDriftList(items, empty) {
    return (items || []).map(function (item) {
      return `<li><strong>${escapeHtml(item.port)}/${escapeHtml(item.protocol)}</strong> — ${escapeHtml(item.service || item.reason || "Unknown")}${item.risk ? ` ${riskBadge(item.risk)}` : ""}</li>`;
    }).join("") || `<li class="text-muted">${escapeHtml(empty)}</li>`;
  }

  async function loadProfileOptions(select) {
    const payload = await jsonRequest("/api/model-profiles");
    select.innerHTML = `<option value="">Choose a profile…</option>` + payload.profiles.map(function (profile) {
      return `<option value="${profile.id}">${escapeHtml(profileName(profile))}</option>`;
    }).join("");
  }

  function renderClientProfile(root, payload) {
    const result = payload.result || {};
    const device = payload.device || result.device || {};
    const drift = result.drift || device.model_port_drift || {
      severity: "none", score: 0, unexpected: [], missing_expected: [], deprecated: []
    };
    const profiles = result.profiles || device.model_profile_matches || [];
    const primary = result.primary_profile || profiles[profiles.length - 1];
    const layers = profiles.map(function (profile) {
      return `<li><a href="/models/${profile.id}">${escapeHtml(profile.manufacturer)} ${escapeHtml(profile.model || profile.family || "defaults")}</a> ${badge(profile.match_level, "info")}</li>`;
    }).join("") || `<li class="text-muted">No matching profile. Create or manually assign one.</li>`;
    const tasks = (result.remediation || device.model_remediation_tasks || []).map(function (item) {
      return `<li>${riskBadge(item.severity)} ${escapeHtml(item.task)}${item.port ? ` (${escapeHtml(item.port)}/${escapeHtml(item.protocol)})` : ""}</li>`;
    }).join("") || `<li class="text-muted">No remediation tasks.</li>`;
    const unexpectedRows = (drift.unexpected || []).map(function (item) {
      return `<tr>
        <td>${escapeHtml(item.port)}/${escapeHtml(item.protocol)}</td>
        <td>${escapeHtml(item.service || "Unknown")}</td>
        <td>${riskBadge(item.risk)}</td>
        <td><button class="btn btn-outline-info btn-sm" type="button" data-model-investigate="${item.port}" data-protocol="${item.protocol}">Investigate</button> <button class="btn btn-outline-secondary btn-sm" type="button" data-model-local-override="${item.port}" data-protocol="${item.protocol}" data-service="${escapeHtml(item.service || "")}">Mark Local</button></td>
      </tr>`;
    }).join("") || `<tr><td colspan="4" class="text-muted">No unexpected services.</td></tr>`;
    root.innerHTML = `<div class="card-body">
      <div class="d-flex justify-content-between align-items-start flex-wrap">
        <div><h2 class="theme-section-title">Device Model Profile</h2><p class="text-muted">Inherited model knowledge, firmware/hardware applicability, fleet comparison, drift, and remediation.</p></div>
        ${primary ? `<a class="btn btn-outline-primary btn-sm" href="/models/${primary.id}">Open ${escapeHtml(primary.model || primary.family || "Profile")}</a>` : `<a class="btn btn-outline-primary btn-sm" href="/models">Open Model Library</a>`}
      </div>
      <div class="alert alert-${drift.severity === "critical" || drift.severity === "high" ? "danger" : drift.severity === "medium" ? "warning" : "success"}">
        Drift: <strong>${escapeHtml(drift.severity)}</strong> · ${escapeHtml(drift.score)}/100 · ${escapeHtml((drift.unexpected || []).length)} unexpected · ${escapeHtml((drift.missing_expected || []).length)} missing expected · ${escapeHtml((drift.deprecated || []).length)} deprecated
      </div>
      <div class="row"><div class="col-lg-6"><h3 class="theme-subsection-title">Profile Layers</h3><ul>${layers}</ul></div><div class="col-lg-6"><h3 class="theme-subsection-title">Manual Assignment</h3><div class="input-group"><select class="form-control" data-client-profile-select></select><div class="input-group-append"><button class="btn btn-outline-primary" type="button" data-client-profile-assign>Assign</button></div></div></div></div>
      <div class="theme-actions"><button class="btn btn-primary" type="button" data-client-profile-apply>Reassess Model Drift</button></div>
      <h3 class="theme-subsection-title mt-3">Unexpected Services</h3>
      <div class="table-responsive"><table class="table table-sm"><thead><tr><th>Port</th><th>Observed</th><th>Risk</th><th>Action</th></tr></thead><tbody>${unexpectedRows}</tbody></table></div>
      <div class="row"><div class="col-lg-6"><h3 class="theme-subsection-title">Missing Expected</h3><ul>${renderDriftList(drift.missing_expected, "No expected services missing.")}</ul></div><div class="col-lg-6"><h3 class="theme-subsection-title">Remediation Checklist</h3><ul>${tasks}</ul></div></div>
      <pre class="theme-results mt-3" data-client-profile-output>Ready.</pre>
    </div>`;
    const select = root.querySelector("[data-client-profile-select]");
    if (select) loadProfileOptions(select).catch(function () {});
  }

  async function loadClientProfile(root) {
    const host = clientHost();
    if (!host) return;
    try {
      const payload = await jsonRequest(`/clients/${encodeURIComponent(host)}/model-profile`);
      renderClientProfile(root, payload);
    } catch (error) {
      root.innerHTML = `<div class="card-body"><h2 class="theme-section-title">Device Model Profile</h2><div class="alert alert-danger">${escapeHtml(error.message)}</div></div>`;
    }
  }

  function setupClientProfile() {
    const tools = document.querySelector("[data-ip-client-tools]");
    if (!tools || document.querySelector("[data-client-model-profile]")) return;
    const root = document.createElement("section");
    root.className = "theme-card card";
    root.setAttribute("data-client-model-profile", "");
    root.innerHTML = `<div class="card-body"><p class="text-muted">Loading device model profile…</p></div>`;
    tools.parentNode.insertBefore(root, tools);
    root.addEventListener("click", async function (event) {
      const host = clientHost();
      const output = root.querySelector("[data-client-profile-output]");
      try {
        if (event.target.closest("[data-client-profile-apply]")) {
          output.textContent = "Applying profile hierarchy and checking drift…";
          const payload = await post(`/clients/${encodeURIComponent(host)}/model-profile/apply`, {});
          renderClientProfile(root, payload);
        }
        if (event.target.closest("[data-client-profile-assign]")) {
          const profileId = root.querySelector("[data-client-profile-select]")?.value || "";
          if (!profileId) throw new Error("Choose a profile first.");
          const payload = await post(`/clients/${encodeURIComponent(host)}/model-profile/assign`, { profileId: profileId });
          renderClientProfile(root, payload);
        }
        const investigate = event.target.closest("[data-model-investigate]");
        if (investigate) {
          output.textContent = "Running the bounded unknown-port investigation…";
          const payload = await post(`/clients/${encodeURIComponent(host)}/model-profile/investigate`, {
            port: investigate.dataset.modelInvestigate,
            protocol: investigate.dataset.protocol,
            activeProbe: "on"
          });
          output.textContent = JSON.stringify(payload.investigation, null, 2);
        }
        const local = event.target.closest("[data-model-local-override]");
        if (local) {
          const payload = await post(`/clients/${encodeURIComponent(host)}/model-profile/override`, {
            port: local.dataset.modelLocalOverride,
            protocol: local.dataset.protocol,
            service: local.dataset.service,
            classification: "local-configuration",
            description: "Approved as a device-specific local configuration.",
            risk: "info"
          });
          renderClientProfile(root, payload);
        }
      } catch (error) {
        if (output) output.textContent = error.message;
      }
    });
    loadClientProfile(root);
  }

  function start() {
    setupLibrary();
    setupProfileDetail();
    setupClientProfile();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
}());
