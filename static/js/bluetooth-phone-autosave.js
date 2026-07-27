$(document).ready(function () {
  function statusBox(form) {
    return form.find('[data-bluetooth-phone-status]');
  }

  function setStatus(form, message, style) {
    statusBox(form)
      .removeClass('d-none alert-info alert-success alert-warning alert-danger')
      .addClass(`alert-${style || 'info'}`)
      .text(message);
  }

  let saveTimer = null;
  function saveForm(form, immediate) {
    window.clearTimeout(saveTimer);
    const runSave = function () {
      $.ajax({
        url: form.attr('action'),
        type: 'POST',
        data: form.serialize(),
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        beforeSend: function () {
          setStatus(form, 'Saving Bluetooth phone settings...', 'info');
        },
        success: function (response) {
          setStatus(form, response.notice || response.message || 'Bluetooth phone settings saved.', response.notice_style || 'success');
        },
        error: function (xhr) {
          const message = xhr.responseJSON?.notice || xhr.responseJSON?.message || 'Unable to save Bluetooth phone settings.';
          setStatus(form, message, 'danger');
        }
      });
    };
    if (immediate) {
      runSave();
    } else {
      saveTimer = window.setTimeout(runSave, 600);
    }
  }

  $(document).on('input', '.bluetooth-phone-form input[type="text"]', function () {
    saveForm($(this).closest('form'), false);
  });

  $(document).on('change', '.bluetooth-phone-form input[type="checkbox"]', function () {
    saveForm($(this).closest('form'), true);
  });
});
