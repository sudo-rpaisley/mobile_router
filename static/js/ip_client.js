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
    return $('[data-ip-client-tools]').data('host') || '';
  }

  function output(html) {
    $('[data-ip-client-output]').html(html);
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
      const note = (item.banner || (item.notes || []).join('; ') || 'No additional fingerprint data');
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

  $('[data-ip-client-ping]').on('click', function () {
    const host = clientHost();
    output('<p class="text-muted">Pinging client...</p>');
    $.ajax({
      url: '/ping',
      method: 'POST',
      data: { host: host, count: 4, timeout: 2 },
      success: function (resp) { output(renderPing(resp.result || {})); },
      error: function (xhr) { output(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'Ping failed')}</div>`); }
    });
  });

  $('[data-ip-client-route]').on('click', function () {
    const host = clientHost();
    output('<p class="text-muted">Checking route context...</p>');
    $.ajax({
      url: '/route-diagnostics',
      method: 'POST',
      data: { target: host },
      success: function (resp) { output(renderRoute(resp.diagnostics || {})); },
      error: function (xhr) { output(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'Route diagnostics failed')}</div>`); }
    });
  });

  $('[data-ip-client-traceroute]').on('click', function () {
    const host = clientHost();
    output('<p class="text-muted">Running traceroute...</p>');
    $.ajax({
      url: '/traceroute',
      method: 'POST',
      data: { host: host },
      success: function (resp) { output(renderTraceroute(resp.hops || [])); },
      error: function (xhr) { output(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'Traceroute failed')}</div>`); }
    });
  });

  $('[data-ip-client-evidence-form]').on('submit', function (event) {
    event.preventDefault();
    const host = clientHost();
    const notes = $('[data-ip-client-evidence-notes]').val();
    output('<p class="text-muted">Saving evidence note...</p>');
    $.ajax({
      url: '/evidence',
      method: 'POST',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      data: {
        title: `IP client note for ${host}`,
        category: 'note',
        source: 'client-detail',
        device: host,
        notes: notes,
        content: notes
      },
      success: function (resp) {
        $('[data-ip-client-evidence-notes]').val('');
        output(`<div class="alert alert-success">Evidence note saved for ${escapeHtml(resp.evidence?.device || host)}.</div>`);
      },
      error: function (xhr) { output(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'Evidence note failed')}</div>`); }
    });
  });

  $('[data-ip-client-watch]').on('click', function () {
    const button = $(this);
    const host = clientHost();
    const nextWatch = button.attr('data-watched') !== 'true';
    output('<p class="text-muted">Updating client watch...</p>');
    $.ajax({
      url: `/clients/${encodeURIComponent(host)}/watch`,
      method: 'POST',
      data: { watch: nextWatch ? 'on' : '' },
      success: function (resp) {
        button.attr('data-watched', resp.watched ? 'true' : 'false');
        button.toggleClass('btn-warning', resp.watched).toggleClass('btn-outline-warning', !resp.watched);
        button.text(resp.watched ? 'Watching client' : 'Watch this device');
        output(`<div class="alert alert-success">${escapeHtml(resp.message || 'Client watch updated.')}</div>`);
      },
      error: function (xhr) { output(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'Client watch update failed')}</div>`); }
    });
  });

  $('[data-ip-client-http-inspect]').on('click', function () {
    const host = clientHost();
    output('<p class="text-muted">Inspecting saved web-service candidates...</p>');
    $.ajax({
      url: `/clients/${encodeURIComponent(host)}/http-inspect`,
      method: 'POST',
      success: function (resp) { output(renderHttpInspect(resp.results || [])); },
      error: function (xhr) { output(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'HTTP inspection failed')}</div>`); }
    });
  });

  $('[data-ip-client-fingerprint]').on('click', function () {
    const host = clientHost();
    output('<p class="text-muted">Fingerprinting saved service candidates...</p>');
    $.ajax({
      url: `/clients/${encodeURIComponent(host)}/fingerprint`,
      method: 'POST',
      success: function (resp) { output(renderFingerprints(resp.fingerprints || [])); },
      error: function (xhr) { output(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'Service fingerprint failed')}</div>`); }
    });
  });

  $('[data-ip-client-intelligence]').on('click', function () {
    const host = clientHost();
    output('<p class="text-muted">Gathering device intelligence from saved profile data and safe service probes...</p>');
    $.ajax({
      url: `/clients/${encodeURIComponent(host)}/intelligence`,
      method: 'POST',
      data: { activeProbe: 'on' },
      success: function (resp) { output(renderIntelligence(resp.intelligence || {})); },
      error: function (xhr) { output(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'Device intelligence failed')}</div>`); }
    });
  });

  $('[data-ip-client-baseline]').on('click', function () {
    const host = clientHost();
    output('<p class="text-muted">Saving current device baseline...</p>');
    $.ajax({
      url: `/clients/${encodeURIComponent(host)}/baseline`,
      method: 'POST',
      success: function (resp) { output(`<div class="alert alert-success">${escapeHtml(resp.message || 'Client baseline saved.')}</div>`); },
      error: function (xhr) { output(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'Baseline save failed')}</div>`); }
    });
  });

  $('[data-ip-client-metadata-form]').on('submit', function (event) {
    event.preventDefault();
    const host = clientHost();
    output('<p class="text-muted">Saving client profile metadata...</p>');
    $.ajax({
      url: `/clients/${encodeURIComponent(host)}/metadata`,
      method: 'POST',
      data: {
        tags: $('[data-ip-client-tags]').val(),
        owner: $('[data-ip-client-owner]').val(),
        location: $('[data-ip-client-location]').val(),
        expectedPorts: $('[data-ip-client-expected-ports]').val(),
        notes: $('[data-ip-client-notes]').val()
      },
      success: function (resp) { output(`<div class="alert alert-success">${escapeHtml(resp.message || 'Client metadata saved.')}</div>`); },
      error: function (xhr) { output(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'Client metadata save failed')}</div>`); }
    });
  });

  $('[data-ip-client-scheduled-form]').on('submit', function (event) {
    event.preventDefault();
    const host = clientHost();
    output('<p class="text-muted">Saving scheduled check plan...</p>');
    $.ajax({
      url: `/clients/${encodeURIComponent(host)}/scheduled-check`,
      method: 'POST',
      data: {
        intervalMinutes: $('[data-ip-client-check-interval]').val(),
        checks: $('[data-ip-client-checks]').val()
      },
      success: function (resp) { output(`<div class="alert alert-success">${escapeHtml(resp.message || 'Scheduled check saved.')}</div>`); },
      error: function (xhr) { output(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'Scheduled check save failed')}</div>`); }
    });
  });
});
