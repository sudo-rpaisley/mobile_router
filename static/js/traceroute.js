$(document).ready(function () {
  $('#traceroute-btn').on('click', function (e) {
    e.preventDefault();
    const host = $('#traceroute-host').val();
    $.ajax({
      url: '/traceroute',
      method: 'POST',
      data: { host: host },
      success: function (resp) {
        let html = '<h3>Traceroute</h3>';
        if (resp.hops.length === 0) {
          html += '<p>No hops found</p>';
        } else {
          html += '<ol>';
          resp.hops.forEach(function (hop) { html += `<li>${hop}</li>`; });
          html += '</ol>';
        }
        $('#traceroute-results').html(html);
      },
      error: function () {
        $('#traceroute-results').html('<p>Traceroute failed</p>');
      }
    });
  });
});
