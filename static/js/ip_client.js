$(document).ready(function () {
  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function clientHost() {
    return $('[data-device-workspace]').attr('data-host')
      || $('[data-ip-client-tools]').first().data('host')
      || '';
  }

  function output(html) {
    const $target = $('[data-ip-client-global-output]').first().length
      ? $('[data-ip-client-global-output]').first()
      : $('[data-ip-client-output]').first();
    $target.html(html);
  }

  function notifyFormSaved(form) {
    document.dispatchEvent(new CustomEvent('device-workspace:form-saved', {
      detail: { form: form },
    }));
  }

  function renderPing(result) {
    const reachable = result.reachable ? 'reachable' : 'unreachable';
    const loss = result.packet_loss_percent !== null && result.packet_loss_percent !== undefined ? `${result.packet_loss_percent}% loss` : 'loss unknown';
    const avg = result.avg_latency_ms !== null && result.avg_latency_ms !== undefined ? `${result.avg_latency_ms} ms avg` : 'latency unknown';
    return `<div class="alert alert-${result.reachable ? 'success' : 'warning'}"><strong>Ping ${escapeHtml(reachable)}</strong>: ${escapeHtml(loss)} · ${escapeHtml(avg)}</div>`;
  }

  function renderRoute(diagnostics) {
    const gateways = (diagnostics.default_gateways || []).map((item) => `${item.gateway || 'unknown'} via ${item.interface || 'unknown'}`).join(', ') || 'No default gateway detected';
    const vpnHints = (diagnostics.vpn_hints || []).map((item) => item.interface).join(', ') || 'No VPN route hints';
    const scanPath = diagnostics.scan_path_context || 'No scan-path context returned';
    return `<div class="alert alert-info"><strong>Route diagnostics</strong><br>Gateways: ${escapeHtml(gateways)}<br>VPN hints: ${escapeHtml(vpnHints)}<br><small>${escapeHtml(scanPath)}</small></div>`;
  }

  function renderTraceroute(hops) {
    if (!hops || !hops.length) return '<div class="alert alert-warning">Traceroute returned no hops.</div>';
    return `<div class="alert alert-info"><strong>Traceroute hops</strong><ol class="mb-0">${hops.map((hop) => `<li>${escapeHtml(typeof hop === 'string' ? hop : JSON.stringify(hop))}</li>`).join('')}</ol></div>`;
  }

  function renderHttpInspect(results) {
    if (!results || !results.length) return '<div class="alert alert-warning">No web services were inspected.</div>';
    return `<div class="alert alert-info"><strong>HTTP service inspection</strong></div><div class="port-service-grid">${results.map((item) => `
      <div class="port-service-card">
        <strong>${escapeHtml(item.port)}/tcp</strong>
        <span>${escapeHtml(item.title || item.status || 'No title/status')}</span>
        <small>${escapeHtml(item.server || item.error || item.url)}</small>
      </div>`).join('')}</div>`;
  }

  function renderFingerprints(results) {
    if (!results || !results.length) return '<div class="alert alert-warning">No saved services are available to fingerprint.</div>';
    return `<div class="alert alert-info"><strong>Service fingerprints</strong></div><div class="port-service-grid">${results.map((item) => {
      const web = item.http ? ` · ${item.http.title || item.http.server || item.http.status || item.http.error || 'HTTP checked'}` : '';
      const note = item.banner || (item.notes || []).join('; ') || 'No additional fingerprint data';
      return `<div class="port-service-card">
        <strong>${escapeHtml(item.port)}/tcp ${escapeHtml(item.service)}</strong>
        <span>Confidence: ${escapeHtml(item.confidence)}${escapeHtml(web)}</span>
        <small>${escapeHtml(note)}</small>
      </div>`;
    }).join('')}</div>`;
  }

  function renderIntelligence(info) {
    const names = (info.names || []).join(', ') || 'No learned names yet';
    const dnsForward = ((info.dns || {}).forward || []).map((item) => `${item.name}: ${(item.addresses || []).join(', ') || 'no current answers'}`).join('; ') || 'No forward DNS checks';
    const services = info.services || {};
    const stability = info.stability || {};
    const recommendations = (info.recommendations || []).map((item) => `<li>${escapeHtml(item)}</li>`).join('') || '<li>No recommendations returned.</li>';
    return `<div class="alert alert-info"><strong>Device intelligence snapshot</strong></div>
      <div class="theme-grid">
        <div class="port-service-card"><strong>Names</strong><span>${escapeHtml(names)}</span><small>DHCP: ${escapeHtml((info.dhcp || {}).hostname || 'none')} · PTR: ${escapeHtml((info.dns || {}).reverse || 'none')}</small></div>
        <div class="port-service-card"><strong>OS hint</strong><span>${escapeHtml((info.os_hint || {}).hint || 'Unknown')}</span><small>${escapeHtml(((info.os_hint || {}).evidence || []).join('; ') || 'No TTL evidence yet')}</small></div>
        <div class="port-service-card"><strong>Services</strong><span>${escapeHtml(services.open_port_count || 0)} saved · ${escapeHtml(services.web_port_count || 0)} web · ${escapeHtml(services.sensitive_port_count || 0)} sensitive</span><small>${escapeHtml((services.fingerprints || []).length)} fingerprint probe result(s)</small></div>
        <div class="port-service-card"><strong>Stability</strong><span>${escapeHtml((stability.sources || []).join(', ') || 'No sources')}</span><small>Interfaces: ${escapeHtml((stability.interfaces || []).join(', ') || 'none')} · DNS: ${escapeHtml(dnsForward)}</small></div>
      </div>
      <h3 class="theme-subsection-title mt-3">Recommended next checks</h3>
      <ul>${recommendations}</ul>`;
  }

  $(document).on('click', '[data-ip-client-ping]', function () {
    const host = clientHost();
    output('<p class="text-muted">Pinging client...</p>');
    $.ajax({
      url: '/ping', method: 'POST', data: { host: host, count: 4, timeout: 2 },
      success: function (resp) { output(renderPing(resp.result || {})); },
      error: function (xhr) { output(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'Ping failed')}</div>`); }
    });
  });

  $(document).on('click', '[data-ip-client-route]', function () {
    const host = clientHost();
    output('<p class="text-muted">Checking route context...</p>');
    $.ajax({
      url: '/route-diagnostics', method: 'POST', data: { target: host },
      success: function (resp) { output(renderRoute(resp.diagnostics || {})); },
      error: function (xhr) { output(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'Route diagnostics failed')}</div>`); }
    });
  });

  $(document).on('click', '[data-ip-client-traceroute]', function () {
    const host = clientHost();
    output('<p class="text-muted">Running traceroute...</p>');
    $.ajax({
      url: '/traceroute', method: 'POST', data: { host: host },
      success: function (resp) { output(renderTraceroute(resp.hops || [])); },
      error: function (xhr) { output(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'Traceroute failed')}</div>`); }
    });
  });

  $(document).on('submit', '[data-ip-client-evidence-form]', function (event) {
    event.preventDefault();
    const form = this;
    const host = clientHost();
    const notes = $(form).find('[data-ip-client-evidence-notes]').val();
    output('<p class="text-muted">Saving evidence note...</p>');
    $.ajax({
      url: '/evidence', method: 'POST', headers: { 'X-Requested-With': 'XMLHttpRequest' },
      data: { title: `IP client note for ${host}`, category: 'note', source: 'client-detail', device: host, notes: notes, content: notes },
      success: function (resp) {
        $(form).find('[data-ip-client-evidence-notes]').val('');
        notifyFormSaved(form);
        output(`<div class="alert alert-success">Evidence note saved for ${escapeHtml(resp.evidence?.device || host)}.</div>`);
      },
      error: function (xhr) { output(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'Evidence note failed')}</div>`); }
    });
  });

  $(document).on('click', '[data-ip-client-watch]', function () {
    const host = clientHost();
    const nextWatch = $(this).attr('data-watched') !== 'true';
    output('<p class="text-muted">Updating client watch...</p>');
    $.ajax({
      url: `/clients/${encodeURIComponent(host)}/watch`, method: 'POST', data: { watch: nextWatch ? 'on' : '' },
      success: function (resp) {
        const $buttons = $('[data-ip-client-watch]');
        $buttons.attr('data-watched', resp.watched ? 'true' : 'false');
        $buttons.toggleClass('btn-warning', resp.watched).toggleClass('btn-outline-warning', !resp.watched);
        $buttons.each(function () { $(this).text(resp.watched ? ($(this).closest('.device-compact-actions').length ? 'Watching' : 'Watching client') : ($(this).closest('.device-compact-actions').length ? 'Watch' : 'Watch this device')); });
        output(`<div class="alert alert-success">${escapeHtml(resp.message || 'Client watch updated.')}</div>`);
      },
      error: function (xhr) { output(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'Client watch update failed')}</div>`); }
    });
  });

  $(document).on('click', '[data-ip-client-http-inspect]', function () {
    const host = clientHost();
    output('<p class="text-muted">Inspecting saved web-service candidates...</p>');
    $.ajax({
      url: `/clients/${encodeURIComponent(host)}/http-inspect`, method: 'POST',
      success: function (resp) { output(renderHttpInspect(resp.results || [])); },
      error: function (xhr) { output(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'HTTP inspection failed')}</div>`); }
    });
  });

  $(document).on('click', '[data-ip-client-fingerprint]', function () {
    const host = clientHost();
    output('<p class="text-muted">Fingerprinting saved service candidates...</p>');
    $.ajax({
      url: `/clients/${encodeURIComponent(host)}/fingerprint`, method: 'POST',
      success: function (resp) { output(renderFingerprints(resp.fingerprints || [])); },
      error: function (xhr) { output(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'Service fingerprint failed')}</div>`); }
    });
  });

  $(document).on('click', '[data-ip-client-intelligence]', function () {
    const host = clientHost();
    output('<p class="text-muted">Gathering device intelligence from saved profile data and safe service probes...</p>');
    $.ajax({
      url: `/clients/${encodeURIComponent(host)}/intelligence`, method: 'POST', data: { activeProbe: 'on' },
      success: function (resp) { output(renderIntelligence(resp.intelligence || {})); },
      error: function (xhr) { output(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'Device intelligence failed')}</div>`); }
    });
  });

  $(document).on('click', '[data-ip-client-baseline]', function () {
    const host = clientHost();
    output('<p class="text-muted">Saving current device baseline...</p>');
    $.ajax({
      url: `/clients/${encodeURIComponent(host)}/baseline`, method: 'POST',
      success: function (resp) { output(`<div class="alert alert-success">${escapeHtml(resp.message || 'Client baseline saved.')}</div>`); },
      error: function (xhr) { output(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'Baseline save failed')}</div>`); }
    });
  });

  $(document).on('submit', '[data-ip-client-metadata-form]', function (event) {
    event.preventDefault();
    const form = this;
    const host = clientHost();
    const $form = $(form);
    output('<p class="text-muted">Saving client profile metadata...</p>');
    $.ajax({
      url: `/clients/${encodeURIComponent(host)}/metadata`, method: 'POST',
      data: {
        tags: $form.find('[data-ip-client-tags]').val(),
        owner: $form.find('[data-ip-client-owner]').val(),
        location: $form.find('[data-ip-client-location]').val(),
        expectedPorts: $form.find('[data-ip-client-expected-ports]').val(),
        notes: $form.find('[data-ip-client-notes]').val()
      },
      success: function (resp) {
        notifyFormSaved(form);
        output(`<div class="alert alert-success">${escapeHtml(resp.message || 'Client metadata saved.')}</div>`);
      },
      error: function (xhr) { output(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'Client metadata save failed')}</div>`); }
    });
  });

  $(document).on('submit', '[data-ip-client-scheduled-form]', function (event) {
    event.preventDefault();
    const form = this;
    const host = clientHost();
    const $form = $(form);
    output('<p class="text-muted">Saving scheduled check plan...</p>');
    $.ajax({
      url: `/clients/${encodeURIComponent(host)}/scheduled-check`, method: 'POST',
      data: { intervalMinutes: $form.find('[data-ip-client-check-interval]').val(), checks: $form.find('[data-ip-client-checks]').val() },
      success: function (resp) {
        notifyFormSaved(form);
        output(`<div class="alert alert-success">${escapeHtml(resp.message || 'Scheduled check saved.')}</div>`);
      },
      error: function (xhr) { output(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'Scheduled check save failed')}</div>`); }
    });
  });

  $(document).on('click', '[data-ip-client-run-scheduled]', function () {
    const host = clientHost();
    output('<p class="text-muted">Running saved scheduled checks now...</p>');
    $.ajax({
      url: `/clients/${encodeURIComponent(host)}/scheduled-check/run`, method: 'POST',
      success: function (resp) {
        const resultKeys = Object.keys((resp.plan || {}).last_result || {}).join(', ') || 'no checks';
        output(`<div class="alert alert-success">${escapeHtml(resp.message || 'Scheduled checks ran.')} Results: ${escapeHtml(resultKeys)}.</div>`);
      },
      error: function (xhr) { output(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'Scheduled check run failed')}</div>`); }
    });
  });
});