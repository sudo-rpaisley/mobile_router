$(document).ready(function () {
  function escapeHtml(value) {
    return $('<div>').text(value == null ? '' : value).html();
  }

  function serviceTable(items, columns) {
    if (!items || !items.length) {
      return '<p>No records discovered.</p>';
    }
    let html = '<div class="table-responsive"><table class="table theme-table"><thead><tr>';
    columns.forEach(function (column) { html += `<th>${escapeHtml(column.label)}</th>`; });
    html += '</tr></thead><tbody>';
    items.forEach(function (item) {
      html += '<tr>';
      columns.forEach(function (column) { html += `<td>${escapeHtml(item[column.key] || '')}</td>`; });
      html += '</tr>';
    });
    html += '</tbody></table></div>';
    return html;
  }

  function runDiscovery(button, url, render) {
    button.prop('disabled', true);
    $('#service-discovery-results').html('<p>Discovery running...</p>');
    $.ajax({
      url: url,
      method: 'POST',
      data: { selectedInterface: $('#interface-select-ServiceDiscovery').val() },
      success: function (response) { $('#service-discovery-results').html(render(response.result)); },
      error: function (xhr) { $('#service-discovery-results').html(`<div class="alert alert-danger">${escapeHtml(xhr.responseJSON?.message || 'Discovery failed')}</div>`); },
      complete: function () { button.prop('disabled', false); }
    });
  }

  $('#mdns-discovery-btn').on('click', function (event) {
    event.preventDefault();
    runDiscovery($(this), '/mdns-discovery', function (result) {
      return `<h3>mDNS/Bonjour</h3><p>${escapeHtml(result.message)}</p>` + serviceTable(result.services, [
        { key: 'name', label: 'Name' },
        { key: 'service_type', label: 'Service' },
        { key: 'hostname', label: 'Hostname' },
        { key: 'ip', label: 'IP' },
        { key: 'port', label: 'Port' },
        { key: 'role', label: 'Role' },
        { key: 'txt', label: 'TXT' }
      ]);
    });
  });

  $('#upnp-discovery-btn').on('click', function (event) {
    event.preventDefault();
    runDiscovery($(this), '/upnp-discovery', function (result) {
      return `<h3>UPnP/SSDP</h3><p>${escapeHtml(result.message)}</p>` + serviceTable(result.devices, [
        { key: 'friendly_name', label: 'Friendly name' },
        { key: 'ip', label: 'IP' },
        { key: 'manufacturer', label: 'Manufacturer' },
        { key: 'model', label: 'Model' },
        { key: 'service_type', label: 'Service type' },
        { key: 'control_url', label: 'Control URL' },
        { key: 'role', label: 'Role' }
      ]);
    });
  });

  $('#neighbor-discovery-btn').on('click', function (event) {
    event.preventDefault();
    runDiscovery($(this), '/neighbor-discovery', function (result) {
      return `<h3>LLDP/CDP neighbors</h3><p>${escapeHtml(result.message)}</p>` + serviceTable(result.neighbors, [
        { key: 'name', label: 'Neighbor' },
        { key: 'port_id', label: 'Port' },
        { key: 'management_address', label: 'Management address' },
        { key: 'vlans', label: 'VLANs' },
        { key: 'role', label: 'Role' },
        { key: 'description', label: 'Description' }
      ]);
    });
  });
});
