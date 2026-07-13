$(document).ready(function () {
  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  $("button#bluetooth-scan").on("click", function () {
    const interfaceName = $(this).val();
    $.ajax({
      url: "/bluetooth-scan",
      type: "POST",
      data: { 'selectedInterface': interfaceName },
      beforeSend: function () {
        console.log(`Scanning for Bluetooth devices on ${interfaceName}`);
      },
      success: function (response) {
        console.log(`Bluetooth scan on ${interfaceName} successful`);
        let btDiv = `<section class="wireless-results card shadow-sm"><div class="card-body"><div class="wireless-results-header"><div><p class="interface-kicker mb-1">Bluetooth Scan</p><h2 class="interface-section-title mb-0">Bluetooth Devices</h2></div></div>`;
        if (response.devices.length === 0) {
          btDiv += `<div class="alert alert-info mb-0" role="alert">No Bluetooth devices found. Make sure nearby devices are discoverable; paired classic devices may appear even when not actively advertising.</div>`;
        } else {
          response.devices.forEach(function (device) {
            const name = device.name || 'Unknown';
            btDiv += `
              <div class="wireless-network-card mb-2">
                <div>
                  <h5 class="card-title">${escapeHtml(name)}</h5>
                  <p class="card-text">${escapeHtml(device.address)}</p>
                </div>
              </div>
            `;
          });
        }
        btDiv += `</div></section>`;
        $("#bluetooth-devices").html(btDiv);
      },
      error: function (error) {
        console.log("Error occurred during bluetooth scan");
      },
      complete: function () {
        console.log("Bluetooth scan completed");
      }
    });
  });
});
