$(document).ready(function () {
  $("button#wlan-scan").on("click", function () {
    const interfaceName = $(this).val();
    const resultDiv = $(`#wlans-${interfaceName}`);

    $.ajax({
      url: "/wlan-scan",
      type: "POST",
      data: { selectedInterface: interfaceName },
      beforeSend: function () {
        console.log(`Scanning for networks ${interfaceName}`);
      },
      success: function (response) {
        console.log(`Networks on ${interfaceName} scanned successfully`);

        const ssids = [];
        response.wlans.forEach(function (network) {
          if (network.ssid && !ssids.includes(network.ssid)) {
            ssids.push(network.ssid);
          }
        });

        if (ssids.length === 0) {
          resultDiv.html("<p>No networks found</p>");
          return;
        }

        let dropdown = '<select class="form-select mt-2">';
        ssids.forEach(function (ssid) {
          dropdown += `<option value="${ssid}">${ssid}</option>`;
        });
        dropdown += '</select>';

        resultDiv.html(dropdown);
      },
      error: function () {
        console.log("Error occurred during network scan");
      },
      complete: function () {
        console.log("Network scan completed");
      }
    });
  });
});
