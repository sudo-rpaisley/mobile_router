$(document).ready(function () {
  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  const bluetoothActions = [
    { action: 'info', label: 'Info', style: 'outline-secondary', icon: 'circle-info' },
    { action: 'connect', label: 'Connect', style: 'outline-primary', icon: 'link' },
    { action: 'disconnect', label: 'Disconnect', style: 'outline-warning', icon: 'link-slash' },
    { action: 'pair', label: 'Pair', style: 'outline-primary', icon: 'handshake' },
    { action: 'trust', label: 'Trust', style: 'outline-success', icon: 'shield-halved' },
    { action: 'untrust', label: 'Untrust', style: 'outline-secondary', icon: 'shield' },
    { action: 'block', label: 'Block', style: 'outline-danger', icon: 'ban' },
    { action: 'unblock', label: 'Unblock', style: 'outline-success', icon: 'check' },
    { action: 'remove', label: 'Remove', style: 'outline-danger', icon: 'trash' }
  ];

  function renderDevice(device, actionCapability) {
    const name = device.name || 'Unknown';
    const address = device.address || '';
    const manufacturer = device.manufacturer || 'Unknown manufacturer';
    const actionsAvailable = Boolean(actionCapability?.available);
    const disabled = actionsAvailable ? '' : 'disabled';
    const disabledTitle = actionsAvailable ? '' : `title="${escapeHtml(actionCapability?.message || 'Bluetooth actions are unavailable on this host.')}"`;
    const actionButtons = bluetoothActions.map(function (item) {
      return `<button type="button" class="btn btn-${item.style} btn-sm bluetooth-action" data-action="${escapeHtml(item.action)}" data-address="${escapeHtml(address)}" ${disabled} ${disabledTitle}><i class="fa-solid fa-${item.icon}"></i> ${escapeHtml(item.label)}</button>`;
    }).join('');

    return `
      <article class="wireless-network-card bluetooth-device-card">
        <div class="wireless-network-main">
          <div>
            <h3 class="wireless-network-ssid mb-1">${escapeHtml(name)}</h3>
            <p class="wireless-network-meta mb-0"><i class="fa-brands fa-bluetooth-b"></i> ${escapeHtml(address || 'Unknown address')}</p>
            <p class="wireless-network-meta mb-0"><i class="fa-solid fa-industry"></i> ${escapeHtml(manufacturer)}</p>
          </div>
          <span class="badge badge-info">Bluetooth</span>
        </div>
        <div class="bluetooth-action-grid mt-3">${actionButtons}</div>
        <pre class="bluetooth-action-output d-none mt-3 mb-0"></pre>
      </article>
    `;
  }

  $(document).on("click", "button#bluetooth-scan", function () {
    const button = $(this);
    const interfaceName = button.val();
    const result = $("#bluetooth-devices");
    $.ajax({
      url: "/bluetooth-scan",
      type: "POST",
      data: { 'selectedInterface': interfaceName },
      beforeSend: function () {
        button.prop('disabled', true).text('Scanning...');
        result.html(`<div class="wireless-scan-state card shadow-sm"><div class="card-body d-flex align-items-center"><div class="spinner-border text-primary mr-3" role="status" aria-hidden="true"></div><div><strong>Scanning ${escapeHtml(interfaceName)}</strong><p class="text-muted mb-0">Looking for nearby Bluetooth devices.</p></div></div></div>`);
      },
      success: function (response) {
        const devices = Array.isArray(response.devices) ? response.devices : [];
        const actionCapability = response.action_capability || { available: false, message: 'Bluetooth action capability is unknown.' };
        let btDiv = `<section class="wireless-results card shadow-sm"><div class="card-body"><div class="wireless-results-header"><div><p class="interface-kicker mb-1">Bluetooth Scan</p><h2 class="interface-section-title mb-0">Bluetooth Devices</h2></div><span class="badge badge-primary">${devices.length} found</span></div><div class="alert alert-secondary small" role="alert"><strong>Training note:</strong> actions operate through this adapter against devices you own or are authorized to test. Bluetooth does not provide a legitimate generic way to force a third-party device to disconnect from another third-party device.</div>`;
        if (!actionCapability.available) {
          btDiv += `<div class="alert alert-warning small" role="alert"><strong>Bluetooth actions unavailable:</strong> ${escapeHtml(actionCapability.message || 'Install bluetoothctl to enable actions.')}</div>`;
        }
        if (devices.length === 0) {
          btDiv += `<div class="alert alert-info mb-0" role="alert">No Bluetooth devices found. Make sure nearby devices are discoverable; paired classic devices may appear even when not actively advertising.</div>`;
        } else {
          btDiv += `<div class="wireless-network-grid">${devices.map(function (device) { return renderDevice(device, actionCapability); }).join('')}</div>`;
        }
        btDiv += `</div></section>`;
        result.html(btDiv);
      },
      error: function (xhr) {
        const message = xhr.responseJSON?.message || 'Error occurred during Bluetooth scan';
        result.html(`<div class="alert alert-danger mt-3" role="alert">${escapeHtml(message)}</div>`);
      },
      complete: function () {
        button.prop('disabled', false).text('Scan for Devices');
      }
    });
  });

  $(document).on('click', '.bluetooth-action', function () {
    const button = $(this);
    const card = button.closest('.bluetooth-device-card');
    const output = card.find('.bluetooth-action-output');
    $.ajax({
      url: '/bluetooth-action',
      type: 'POST',
      data: { action: button.data('action'), address: button.data('address') },
      beforeSend: function () {
        button.prop('disabled', true);
        output.removeClass('d-none text-danger text-success').addClass('text-muted').text('Running action...');
      },
      success: function (response) {
        output.removeClass('text-muted text-danger').addClass('text-success').text(response.output || response.message || 'Action completed.');
      },
      error: function (xhr) {
        const message = xhr.responseJSON?.message || 'Bluetooth action failed';
        output.removeClass('text-muted text-success').addClass('text-danger').text(message);
      },
      complete: function () {
        button.prop('disabled', false);
      }
    });
  });
});
