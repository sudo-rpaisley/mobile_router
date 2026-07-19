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
});
