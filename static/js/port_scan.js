$(document).ready(function () {
  $('#port-scan-btn').on('click', function (e) {
    e.preventDefault();
    const host = $('#scan-host').val();
    const start = $('#scan-start').val();
    const end = $('#scan-end').val();
    $.ajax({
      url: '/port-scan',
      method: 'POST',
      data: { host: host, start: start, end: end },
      success: function (resp) {
        let html = '<h3>Open Ports</h3>';
        if (resp.ports.length === 0) {
          html += '<p>No open ports found</p>';
        } else {
          html += '<ul>';
          resp.ports.forEach(function (p) { html += `<li>${p}</li>`; });
          html += '</ul>';
        }
        $('#port-scan-results').html(html);
      },
      error: function () {
        $('#port-scan-results').html('<p>Scan failed</p>');
      }
    });
  });
});
