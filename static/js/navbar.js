$(document).ready(function () {
  $('[data-toggle="tooltip"]').tooltip();

  function updateJobIndicator() {
    $.ajax({
      url: '/jobs/status',
      method: 'GET',
      success: function (resp) {
        const count = resp.running_count || 0;
        const label = count > 0
          ? `${count} background job(s) running`
          : 'No background jobs running';
        $('#job-activity-count').text(count);
        $('#job-activity-indicator')
          .toggleClass('is-active', count > 0)
          .attr('title', label)
          .attr('aria-label', label);
      },
      complete: function () {
        setTimeout(updateJobIndicator, 2000);
      }
    });
  }

  function updateAlertIndicator() {
    $.ajax({
      url: '/alerts/status',
      method: 'GET',
      success: function (resp) {
        const count = resp.unread_count || 0;
        const label = count > 0
          ? `${count} unread new device alert(s)`
          : 'No unread new device alerts';
        $('#new-device-alert-count').text(count);
        $('#new-device-alert-indicator')
          .toggleClass('has-alerts', count > 0)
          .attr('title', label)
          .attr('aria-label', label);
      },
      complete: function () {
        setTimeout(updateAlertIndicator, 3000);
      }
    });
  }

  updateJobIndicator();
  updateAlertIndicator();
});
