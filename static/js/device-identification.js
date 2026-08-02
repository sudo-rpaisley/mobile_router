$(document).ready(function () {
  const button = $('[data-ip-client-intelligence]');
  if (!button.length) return;

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function host() {
    return $('[data-ip-client-tools]').data('host') || '';
  }

  function csrfToken() {
    return $('.app-navbar').data('csrf-token') || '';
  }

  function output(html) {
    $('[data-ip-client-output]').html(html);
  }

  function badge(confidence) {
    const value = String(confidence || 'low').toLowerCase();
    if (value === 'very high') return 'success';
    if (value === 'high') return 'primary';
    if (value === 'medium') return 'warning';
    return 'secondary';
  }

  function renderEvidence(items) {
    if (!items || !items.length) return '<li class="text-muted">No identity evidence was available.</li>';
    return items.map(function (item) {
      return `<li><strong>${escapeHtml(item.source)}</strong>: ${escapeHtml(item.value)} <span class="badge badge-light border">weight ${escapeHtml(item.weight)}</span></li>`;
    }).join('');
  }

  function renderCandidates(items) {
    if (!items || !items.length) return '<p class="text-muted">No candidates were generated.</p>';
    return `<div class="port-service-grid">${items.map(function (item) {
      return `<div class="port-service-card">
        <strong>${escapeHtml(item.label)}</strong>
        <span>${escapeHtml(item.category)} · ${escapeHtml(item.score)}/100</span>
        <small>${escapeHtml((item.reasons || []).join('; ') || 'No supporting rule details')}</small>
      </div>`;
    }).join('')}</div>`;
  }

  function renderDeepProbe(probe) {
    if (!probe || !Object.keys(probe).length) return '';
    const nmap = probe.nmap || {};
    const snmp = probe.snmp || {};
    const nmapMessage = nmap.output || nmap.error || nmap.message || 'No Nmap result';
    const snmpMessage = snmp.output || snmp.error || snmp.message || 'No SNMP result';
    return `<details class="mt-3">
      <summary>Deep-probe details</summary>
      <h4 class="mt-2">Nmap OS and service detection</h4>
      <pre class="small">${escapeHtml(nmapMessage)}</pre>
      <h4>SNMP system information</h4>
      <pre class="small">${escapeHtml(snmpMessage)}</pre>
    </details>`;
  }

  function renderResult(response) {
    const result = response.identification || {};
    const limitations = (result.limitations || []).map(function (item) {
      return `<li>${escapeHtml(item)}</li>`;
    }).join('') || '<li>No specific limitations recorded.</li>';
    const signature = result.identity_signature
      ? `${result.identity_signature.slice(0, 16)}…`
      : 'Not enough stable evidence';
    return `<div class="alert alert-${badge(result.confidence)}">
        <strong>Likely device: ${escapeHtml(result.likely_device || 'Unidentified network device')}</strong><br>
        ${escapeHtml(result.category || 'Unknown category')} · ${escapeHtml(result.confidence || 'low')} confidence · ${escapeHtml(result.score || 0)}/100
      </div>
      <div class="theme-grid">
        <div class="port-service-card"><strong>Identification stage</strong><span>${escapeHtml(response.stage || 'unknown')}</span><small>Passive, safe-service, or explicitly authorised deep probes.</small></div>
        <div class="port-service-card"><strong>Stable identity signature</strong><span><code>${escapeHtml(signature)}</code></span><small>Used to correlate the same device after IP or private-MAC changes.</small></div>
        <div class="port-service-card"><strong>Evidence collected</strong><span>${escapeHtml((result.evidence || []).length)} signal(s)</span><small>Conclusions require multiple independent clues where possible.</small></div>
        <div class="port-service-card"><strong>Alternative candidates</strong><span>${escapeHtml((result.candidates || []).length)} ranked</span><small>The highest-scoring fingerprint is shown above.</small></div>
      </div>
      <h3 class="theme-subsection-title mt-3">Ranked candidates</h3>
      ${renderCandidates(result.candidates)}
      <h3 class="theme-subsection-title mt-3">Supporting evidence</h3>
      <ol>${renderEvidence(result.evidence)}</ol>
      <h3 class="theme-subsection-title mt-3">Limitations</h3>
      <ul>${limitations}</ul>
      ${renderDeepProbe(response.deep_probe)}`;
  }

  const controls = $(`
    <div class="device-identification-controls mt-2" data-device-identification-controls>
      <label class="small mb-1" for="device-identification-stage">Identification depth</label>
      <select id="device-identification-stage" class="form-control form-control-sm" data-device-identification-stage>
        <option value="passive">Passive evidence only</option>
        <option value="safe" selected>Safe service identification</option>
        <option value="deep">Deep OS, service and optional SNMP identification</option>
      </select>
      <div class="mt-2 d-none" data-device-identification-deep-options>
        <input class="form-control form-control-sm mb-2" type="password" autocomplete="off" data-device-identification-snmp placeholder="Optional SNMP read-only community">
        <label class="form-check small">
          <input class="form-check-input" type="checkbox" data-device-identification-authorized>
          <span class="form-check-label">I confirm this is an authorised device or isolated lab.</span>
        </label>
      </div>
      <p class="small text-muted mt-1 mb-0">Passive mode sends no probes. Safe mode only checks already-open services. Deep mode uses bounded Nmap and optional read-only SNMP when installed.</p>
    </div>
  `);

  button.text('Identify device');
  button.after(controls);
  button.off('click');

  controls.find('[data-device-identification-stage]').on('change', function () {
    controls.find('[data-device-identification-deep-options]').toggleClass('d-none', $(this).val() !== 'deep');
  });

  button.on('click', function () {
    const stage = controls.find('[data-device-identification-stage]').val();
    const authorized = controls.find('[data-device-identification-authorized]').is(':checked');
    if (stage === 'deep' && !authorized) {
      output('<div class="alert alert-warning">Confirm the authorised scope before running deep identification.</div>');
      return;
    }
    button.prop('disabled', true).text('Identifying…');
    output('<p class="text-muted">Combining names, vendor data, saved ports, protocol responses, certificates, discovery metadata and behaviour evidence…</p>');
    $.ajax({
      url: `/clients/${encodeURIComponent(host())}/identify`,
      method: 'POST',
      headers: { 'X-CSRF-Token': csrfToken() },
      data: {
        stage: stage,
        authorized: authorized ? 'on' : '',
        snmpCommunity: controls.find('[data-device-identification-snmp]').val(),
        csrf_token: csrfToken()
      },
      success: function (response) {
        output(renderResult(response));
      },
      error: function (xhr) {
        output(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'Device identification failed')}</div>`);
      },
      complete: function () {
        button.prop('disabled', false).text('Identify device');
      }
    });
  });
});
