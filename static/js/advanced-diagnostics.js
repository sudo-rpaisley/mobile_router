$(document).ready(function () {
  function escapeHtml(value) { return $('<div>').text(value == null ? '' : value).html(); }
  function show(title, result) { $('#advanced-diagnostics-results').html(`<h3>${escapeHtml(title)}</h3><pre>${escapeHtml(JSON.stringify(result, null, 2))}</pre>`); }
  function post(url, data, title) {
    $('#advanced-diagnostics-results').html('<p>Running...</p>');
    $.ajax({
      url: url,
      method: 'POST',
      data: data,
      success: function (response) { show(title, response.result); },
      error: function (xhr) { $('#advanced-diagnostics-results').html(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'Request failed')}</div>`); }
    });
  }
  $('#vlan-discovery-btn').on('click', function (event) {
    event.preventDefault();
    post('/vlan-discovery', { ssid: $('#vlan-ssid').val(), vlanId: $('#vlan-id').val(), notes: $('#vlan-notes').val() }, 'VLAN context');
  });
  $('#egress-diagnostics-btn').on('click', function (event) {
    event.preventDefault();
    post('/egress-diagnostics', { selectedInterface: $('#interface-select-AdvancedDiagnostics').val() }, 'Egress diagnostics');
  });
  $('#iperf-client-btn').on('click', function (event) {
    event.preventDefault();
    post('/iperf3-test', { mode: 'client', host: $('#iperf-host').val(), port: $('#iperf-port').val(), seconds: $('#iperf-seconds').val() }, 'iperf3 result');
  });
  $('#snmp-discovery-btn').on('click', function (event) {
    event.preventDefault();
    post('/snmp-discovery', { host: $('#snmp-host').val(), community: $('#snmp-community').val(), authorized: $('#snmp-authorized').is(':checked') ? 'on' : '' }, 'SNMP inventory');
  });
  $('#ipv6-assessment-btn').on('click', function (event) {
    event.preventDefault();
    post('/ipv6-assessment', { host: $('#ipv6-host').val(), ports: $('#ipv6-ports').val() }, 'IPv6 assessment');
  });
});
