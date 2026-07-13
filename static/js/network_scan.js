$(document).ready(function () {
  $('#active-scan-btn').on('click', function (e) {
    e.preventDefault();
    const iface = $('#interface-select-Scan').val();
    $.ajax({
      url: '/active-scan',
      method: 'POST',
      data: { selectedInterface: iface },
      success: function (resp) {
        let html = '<h3>Active Scan Results</h3>';
        if (resp.hosts.length === 0) {
          html += '<p>No hosts found</p>';
        } else {
          html += '<div class="table-responsive"><table class="table theme-table"><thead><tr><th>IP</th><th>MAC</th><th>Manufacturer</th></tr></thead><tbody>';
          resp.hosts.forEach(function (host) {
            const display = host.ip || 'Unknown IP';
            const macParam = host.mac ? host.mac : host.ip;
            const link = `/clients/${encodeURIComponent(macParam)}`;
            html += `<tr><td><a href="${link}">${display}</a></td><td>${host.mac || '—'}</td><td>${host.manufacturer || 'Unknown'}</td></tr>`;
          });
          html += '</tbody></table></div><p><a href="/inventory">View full device inventory</a></p>';
        }
        $('#scan-results').html(html);
      },
      error: function () {
        $('#scan-results').html('<p>Scan failed</p>');
      }
    });
  });

  $('#passive-scan-btn').on('click', function (e) {
    e.preventDefault();
    const iface = $('#interface-select-Scan').val();
    $.ajax({
      url: '/passive-scan',
      method: 'POST',
      data: { selectedInterface: iface },
      success: function (resp) {
        let html = '<h3>Passive Scan Results</h3>';
        if (resp.devices.length === 0) {
          html += '<p>No devices found</p>';
        } else {
          html += '<div class="table-responsive"><table class="table theme-table"><thead><tr><th>IP</th><th>MAC</th><th>Manufacturer</th></tr></thead><tbody>';
          resp.devices.forEach(function (dev) {
            const link = `/clients/${encodeURIComponent(dev.mac)}`;
            html += `<tr><td>${dev.ip || '—'}</td><td><a href="${link}">${dev.mac}</a></td><td>${dev.manufacturer || 'Unknown'}</td></tr>`;
          });
          html += '</tbody></table></div><p><a href="/inventory">View full device inventory</a></p>';
        }
        $('#scan-results').html(html);
      },
      error: function () {
        $('#scan-results').html('<p>Scan failed</p>');
      }
    });
  });
});
