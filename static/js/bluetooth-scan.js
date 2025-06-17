$(document).ready(function () {
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
        let btDiv = `<h1>Bluetooth Devices</h1>`;
        if (response.devices.length === 0) {
          btDiv += `<p>No devices found</p>`;
        } else {
          response.devices.forEach(function (device) {
            const name = device.name || 'Unknown';
            btDiv += `
              <div class="card mb-2">
                <div class="card-body">
                  <h5 class="card-title">${name}</h5>
                  <p class="card-text">${device.address}</p>
                </div>
              </div>
            `;
          });
        }
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
