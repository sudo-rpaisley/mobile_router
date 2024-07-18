$(document).ready(function () {
  $("button#wlan-scan").on("click", function () {
    const interfaceName = $(this).val();
    $.ajax({
      url: "/wlan-scan",
      type: "POST",
      data: { 'selectedInterface': interfaceName },
      beforeSend: function () {
        console.log(`Scanning for networks ${interfaceName}`);
      },
      success: function (response) {
        console.log(`Networks on ${interfaceName} scanned successfully`);

        const akmMap = {
          "": "Open",
          "0": "Open",
          "1": "WPA Ent",
          "2": "WPAPSK",
          "3": "WPA2 Ent",
          "4": "WPA2PSK",
          "5": "UNKNOWN"
        };

        const groupedNetworks = {};

        response.wlans.forEach(function (network) {
          if (groupedNetworks[network.ssid]) {
            groupedNetworks[network.ssid].push(network);
          } else {
            groupedNetworks[network.ssid] = [network];
          }
        });

        let wlanDiv = `<h1>Wireless Networks</h1>`;
        Object.entries(groupedNetworks).forEach(function ([ssid, bssids], index) {
          const ssidAccordionId = `ssidAccordion-${index}`;

          let accordionContent = '';
          bssids.forEach(function (network, subIndex) {
            const accessPointNumber = subIndex + 1;
            const bssidAccordionId = `bssidAccordion-${index}-${subIndex}`;

            accordionContent += `
              <div class="accordion" id="${bssidAccordionId}">
                <div class="card">
                  <div class="card-header" id="heading${bssidAccordionId}">
                    <h2 class="mb-0">
                      <button class="btn btn-link" type="button" data-toggle="collapse" data-target="#collapse${bssidAccordionId}" aria-expanded="false" aria-controls="collapse${bssidAccordionId}">
                        Access Point ${accessPointNumber} - ${network.bssid}
                      </button>
                    </h2>
                  </div>
                  <div id="collapse${bssidAccordionId}" class="collapse" aria-labelledby="heading${bssidAccordionId}" data-parent="#${bssidAccordionId}">
                    <div class="card-body">
                      <p>Manufacturer - ${network.manufacturer}</p>
                      <p>Frequency - ${network.freq}</p>
                      <p>Signal - ${network.signal}</p>
                      <p>Security - ${akmMap[network.akm]}</p>
                    </div>
                  </div>
                </div>
              </div>
            `;
          });

          const accordion =
            `<div class="accordion" id="${ssidAccordionId}">
              <div class="card">
                <div class="card-header" id="heading${ssidAccordionId}">
                  <h2 class="mb-0">
                    <button class="btn btn-link" type="button" data-toggle="collapse" data-target="#collapse${ssidAccordionId}" aria-expanded="false" aria-controls="collapse${ssidAccordionId}">
                      ${ssid}
                    </button>
                  </h2>
                </div>
                <div id="collapse${ssidAccordionId}" class="collapse" aria-labelledby="heading${ssidAccordionId}" data-parent="#${ssidAccordionId}">
                  <div class="card-body">
                  <button type="button" class="connect-button btn btn-primary" data-toggle="modal">connect</button>
                    ${accordionContent}
                  </div>
                </div>
              </div>
            </div>`;
            
          wlanDiv += accordion;
        });
        
        $("#wlans").html(wlanDiv);
      },
      error: function (error) {
        console.log("Error occurred during network scan");
      },
      complete: function () {
        console.log("Network scan completed");
      }
    });
  });
});
