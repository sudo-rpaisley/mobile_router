$(document).ready(function () {
  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  $(document).on('click', '[data-interface-power]', function () {
    const button = $(this);
    const interfaceName = button.data('interface');
    const state = button.data('state');
    const output = $('[data-interface-power-output]');
    $.ajax({
      url: `/interfaces/${encodeURIComponent(interfaceName)}/state`,
      type: 'POST',
      data: { state: state },
      beforeSend: function () {
        button.prop('disabled', true);
        output.removeClass('d-none alert-danger alert-success').addClass('alert-info').text(`${state === 'up' ? 'Turning on' : 'Turning off'} ${interfaceName}...`);
      },
      success: function (response) {
        output.removeClass('alert-info alert-danger').addClass('alert-success').html(escapeHtml(response.message || 'Interface state updated.'));
      },
      error: function (xhr) {
        const message = xhr.responseJSON?.message || 'Unable to update interface state';
        output.removeClass('alert-info alert-success').addClass('alert-danger').html(escapeHtml(message));
      },
      complete: function () {
        button.prop('disabled', false);
      }
    });
  });
});
