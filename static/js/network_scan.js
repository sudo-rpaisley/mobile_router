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
          html += '<ul>';
          resp.hosts.forEach(function (host) {
            const display = host.ip;
            const macParam = host.mac ? host.mac : host.ip;
            const link = `/clients/${encodeURIComponent(macParam)}`;
            html += `<li><a href="${link}">${display}</a>`;
            if (host.mac) {
              html += ` (${host.mac})`;
            }
            html += `</li>`;

          });
          html += '</ul>';
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
          html += '<ul>';
          resp.devices.forEach(function (dev) {
            const link = `/clients/${encodeURIComponent(dev.mac)}`;

            html += `<li><a href="${link}">${dev.ip}</a> (${dev.mac})</li>`;
          });
          html += '</ul>';
        }
        $('#scan-results').html(html);
      },
      error: function () {
        $('#scan-results').html('<p>Scan failed</p>');
      }
    });
  });
});
