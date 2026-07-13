$(document).ready(function () {
  function escapeHtml(value) {
    return $('<div>').text(value).html();
  }

  $('#minecraft-attack-btn').on('click', function (e) {
    e.preventDefault();

    const authorized = $('#minecraft-authorized').is(':checked');
    if (!authorized) {
      $('#minecraft-attack-results').html('<p class="text-danger">Confirm that you are authorized to test this server.</p>');
      return;
    }

    const payload = {
      host: $('#minecraft-host').val().trim(),
      port: $('#minecraft-port').val(),
      requests: $('#minecraft-requests').val(),
      concurrency: $('#minecraft-concurrency').val(),
      timeout: $('#minecraft-timeout').val(),
      authorized: 'true'
    };

    $('#minecraft-attack-results').html('<p>Running Minecraft status-query demo...</p>');
    $('#minecraft-attack-btn').prop('disabled', true);

    $.ajax({
      url: '/minecraft-attack',
      method: 'POST',
      data: payload,
      success: function (resp) {
        const result = resp.result;
        let html = '<h3>Results</h3>';
        html += '<ul>';
        html += `<li>Attempted: ${result.attempted}</li>`;
        html += `<li>Successful: ${result.successful}</li>`;
        html += `<li>Failed: ${result.failed}</li>`;
        html += `<li>Elapsed: ${result.elapsed_seconds}s</li>`;
        html += '</ul>';

        if (result.sample_status) {
          const description = result.sample_status.description;
          const version = result.sample_status.version ? result.sample_status.version.name : 'Unknown';
          const online = result.sample_status.players ? result.sample_status.players.online : 'Unknown';
          const max = result.sample_status.players ? result.sample_status.players.max : 'Unknown';
          html += '<h4>Sample Server Status</h4>';
          html += '<ul>';
          html += `<li>Version: ${escapeHtml(version)}</li>`;
          html += `<li>Players: ${escapeHtml(`${online}/${max}`)}</li>`;
          html += `<li>Description: ${escapeHtml(typeof description === 'string' ? description : JSON.stringify(description))}</li>`;
          html += '</ul>';
        }

        if (Object.keys(result.errors).length > 0) {
          html += '<h4>Errors</h4><ul>';
          Object.entries(result.errors).forEach(function ([message, count]) {
            html += `<li>${escapeHtml(message)}: ${count}</li>`;
          });
          html += '</ul>';
        }

        $('#minecraft-attack-results').html(html);
      },
      error: function (xhr) {
        const message = xhr.responseJSON && xhr.responseJSON.message ? xhr.responseJSON.message : 'Minecraft demo failed';
        $('#minecraft-attack-results').html(`<p class="text-danger">${escapeHtml(message)}</p>`);
      },
      complete: function () {
        $('#minecraft-attack-btn').prop('disabled', false);
      }
    });
  });

  $('.minecraft-mob-toggle').on('click', function () {
    const button = $(this);
    const mobId = button.data('mob-id');
    const mobName = button.data('mob-name');
    const nextState = button.data('state') === 'on' ? 'off' : 'on';
    const authorized = $('#minecraft-authorized').is(':checked');

    if (!authorized) {
      $('#minecraft-mob-results').html('<p class="text-danger">Confirm that you are authorized to test this server.</p>');
      return;
    }

    const payload = {
      host: $('#minecraft-host').val().trim(),
      state: nextState,
      timeout: $('#minecraft-timeout').val(),
      authorized: 'true'
    };

    button.prop('disabled', true);
    $('#minecraft-mob-results').html(`<p>Turning ${escapeHtml(mobName)} ${nextState}...</p>`);

    $.ajax({
      url: `/minecraft-attack/mobs/${encodeURIComponent(mobId)}/toggle`,
      method: 'POST',
      data: payload,
      success: function (resp) {
        const state = resp.result.state;
        const isOn = state === 'on';
        button.data('state', state);
        button.toggleClass('btn-success', isOn);
        button.toggleClass('btn-secondary', !isOn);
        button.html(`${escapeHtml(mobName)}: ${isOn ? 'On' : 'Off'} <small>port ${resp.result.mob.port}</small>`);
        $('#minecraft-mob-results').html(`<p>${escapeHtml(mobName)} is now ${state}.</p>`);
      },
      error: function (xhr) {
        const message = xhr.responseJSON && xhr.responseJSON.message ? xhr.responseJSON.message : 'Mob toggle failed';
        $('#minecraft-mob-results').html(`<p class="text-danger">${escapeHtml(message)}</p>`);
      },
      complete: function () {
        button.prop('disabled', false);
      }
    });
  });

});
