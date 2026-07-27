$(document).ready(function () {
  function escapeHtml(value) {
    return $('<div>').text(value == null ? '' : value).html();
  }

  function latencyText(result) {
    const latency = result.latency || {};
    if (latency.avg_ms == null) { return 'No latency stats'; }
    return `min ${latency.min_ms} ms · avg ${latency.avg_ms} ms · max ${latency.max_ms} ms`;
  }

  function renderPingResult(result) {
    return `<div class="alert ${result.reachable ? 'alert-success' : 'alert-warning'}">
      <strong>${escapeHtml(result.host)}</strong> ${result.reachable ? 'reachable' : 'not reachable'}<br>
      Loss: ${escapeHtml(result.packet_loss_percent)}% · ${escapeHtml(latencyText(result))}
    </div>`;
  }

  $('#ping-btn').on('click', function (event) {
    event.preventDefault();
    $.ajax({
      url: '/ping',
      method: 'POST',
      data: { host: $('#ping-host').val() },
      success: function (response) { $('#ping-results').html(renderPingResult(response.result)); },
      error: function (xhr) { $('#ping-results').html(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'Ping failed')}</div>`); }
    });
  });

  $('#ping-sweep-btn').on('click', function (event) {
    event.preventDefault();
    $.ajax({
      url: '/ping-sweep',
      method: 'POST',
      data: { cidr: $('#ping-cidr').val() },
      success: function (response) {
        let html = `<h3>Sweep ${escapeHtml(response.sweep.cidr)}</h3><p>${response.sweep.reachable_hosts}/${response.sweep.total_hosts} hosts reachable</p>`;
        response.sweep.results.forEach(function (result) { html += renderPingResult(result); });
        $('#ping-results').html(html);
      },
      error: function (xhr) { $('#ping-results').html(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'Sweep failed')}</div>`); }
    });
  });

  $('#route-diagnostics-btn').on('click', function (event) {
    event.preventDefault();
    $.ajax({
      url: '/route-diagnostics',
      method: 'POST',
      data: { target: $('#route-target').val() },
      success: function (response) {
        const data = response.diagnostics;
        let html = `<h3>Default gateways</h3>`;
        if (!data.default_gateways.length) {
          html += '<p>No default gateways parsed.</p>';
        } else {
          html += '<ul>';
          data.default_gateways.forEach(function (route) { html += `<li>${escapeHtml(route.gateway || 'direct')} via ${escapeHtml(route.interface || 'unknown')} metric ${escapeHtml(route.metric || 'n/a')}</li>`; });
          html += '</ul>';
        }
        html += `<h3>VPN route hints</h3><p>${data.vpn_hints.length ? data.vpn_hints.map(function (route) { return escapeHtml(route.raw); }).join('<br>') : 'No VPN-like interfaces detected in parsed routes.'}</p>`;
        html += `<h3>Scan-path context</h3><pre>${escapeHtml(data.scan_path_context || 'No target route requested.')}</pre>`;
        html += '<h3>Routes</h3><div class="table-responsive"><table class="table theme-table"><thead><tr><th>Family</th><th>Destination</th><th>Gateway</th><th>Interface</th><th>Metric</th></tr></thead><tbody>';
        data.routes.forEach(function (route) { html += `<tr><td>${escapeHtml(route.family)}</td><td>${escapeHtml(route.destination)}</td><td>${escapeHtml(route.gateway || 'direct')}</td><td>${escapeHtml(route.interface || '')}</td><td>${escapeHtml(route.metric || '')}</td></tr>`; });
        html += '</tbody></table></div>';
        $('#route-results').html(html);
      },
      error: function (xhr) { $('#route-results').html(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'Route diagnostics failed')}</div>`); }
    });
  });
});
