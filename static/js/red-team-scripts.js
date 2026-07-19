$(document).ready(function () {
    $("#DoS-Submit").on("click", function(event) {
        event.preventDefault(); //stop the form submitting
    
        var $destinationAddressInput = $("#inlineFormInputDestination");
        var $destinationPortInput = $("#inlineFormInputPort");
        var $framesInput = $("#inlineFormInputFrames");
        var destinationAddress = $destinationAddressInput.val();
        var destinationPort = $destinationPortInput.val();
        var frames = $framesInput.val();
        var selectedInterface = $("#interface-select-DoS").val();
    
        var $submitButton = $('#DoS-Submit');
        var originalButtonClass = $submitButton.attr('class');
        var originalButtonStyle = $submitButton.attr('style');
        var originalButtonText = $submitButton.text(); // store the original button text
    
        function setErrorStyles($input) {
            $input.addClass("input-error"); // add error class
            $input.attr("placeholder", "Please enter a value"); // set placeholder text
        }
    
        switch (true) {
            case !destinationAddress:
                setErrorStyles($destinationAddressInput);
                break;
            
            case !destinationPort:
                setErrorStyles($destinationPortInput);
                break;
                
            case !frames:
                setErrorStyles($framesInput);
                break;
            
            case !destinationAddress || !destinationPort || !frames:
                console.log("there was an error in the input");
                return;
        }
        
    
        $.ajax({
            url: "/syn-flood",
            type: "POST",
            data: {
                destinationAddress: destinationAddress,
                destinationPort: destinationPort,
                frames: frames,
                selectedInterface: selectedInterface
            },
            beforeSend: function() {
                $submitButton.prop("disabled", true);
                $submitButton.attr('class', 'spinner-border text-primary');
                $submitButton.text(''); // clear the button text
                $destinationAddressInput.removeClass("input-error");
                $destinationPortInput.removeClass("input-error");
                $framesInput.removeClass("input-error");
            },
            success: function(response) {
                console.log("DoS Was Successfull. YAY!!!, red-team-scripts.js success function");
                console.log(response);
            },
            error: function(error) {
                console.log(error);
            },
            complete: function() {
                $submitButton.attr('class', originalButtonClass);
                $submitButton.attr('style', originalButtonStyle);
                $submitButton.text(originalButtonText); // restore the original button text
                $submitButton.prop("disabled", false);
            }
        });
    });
    

    $("#DoS-Broadcast-Submit").on("click", function(event) {
        event.preventDefault(); //stop the form submitting
    
        var $framesInput = $("#Broadcast-DoS-Frames"); // variable for frames input
        var frames = $framesInput.val(); // get frames value
        var selectedInterface = $("#interface-select-Broadcast").val();
    
        var $submitButton = $('#DoS-Broadcast-Submit');
        var originalButtonClass = $submitButton.attr('class');
        var originalButtonStyle = $submitButton.attr('style');
        var originalButtonText = $submitButton.text(); // store the original button text
    
        function setErrorStyles($input) {
            $input.addClass("input-error"); // add error class
            $input.attr("placeholder", "Please enter a value"); // set placeholder text
        }
    
        if (!frames) { // if frames input is empty, set error styles
            setErrorStyles($framesInput);
        }
    
        if (!frames) {
            console.log("there was an error in the input");
            return;
        }
    
        $.ajax({
            url: "/syn-flood-broadcast",
            type: "POST",
            data: {
                frames: frames,
                selectedInterface: selectedInterface
            },
            beforeSend: function() {
                $submitButton.prop("disabled", true);
                $submitButton.attr('class', 'spinner-border text-primary');
                $submitButton.text(''); // clear the button text
                $framesInput.removeClass("input-error"); // remove error class from frames input
            },
            success: function(response) {
                console.log("DoS Was Successfull. YAY!!!");
                console.log(response);
            },
            error: function(error) {
                console.log(error);
            },
            complete: function() {
                $submitButton.attr('class', originalButtonClass);
                $submitButton.attr('style', originalButtonStyle);
                $submitButton.text(originalButtonText); // restore the original button text
                $submitButton.prop("disabled", false);
            }
        });
    });


    $("#Beacon-Advertise-Submit").on("click", function(event) {
        event.preventDefault();

        var $ssidInput = $("#Beacon-SSID");
        var $framesInput = $("#Beacon-Frames");
        var $srcInput = $("#Beacon-Src-Mac");
        var $bssidInput = $("#Beacon-BSSID");
        var ssid = $ssidInput.val();
        var frames = $framesInput.val();
        var srcMac = $srcInput.val();
        var bssid = $bssidInput.val();
        var selectedInterface = $("#interface-select-BeaconAdvertise").val();

        if (!ssid || !frames) {
            if (!ssid) { $ssidInput.addClass("input-error"); }
            if (!frames) { $framesInput.addClass("input-error"); }
            return;
        }

        var $submitButton = $("#Beacon-Advertise-Submit");
        var originalButtonClass = $submitButton.attr('class');
        var originalButtonStyle = $submitButton.attr('style');
        var originalButtonText = $submitButton.text();

        $.ajax({
            url: "/beacon-advertise",
            type: "POST",
            data: {
                ssid: ssid,
                frames: frames,
                srcMac: srcMac,
                bssid: bssid,
                selectedInterface: selectedInterface
            },
            beforeSend: function() {
                $submitButton.prop("disabled", true);
                $submitButton.attr('class', 'spinner-border text-primary');
                $submitButton.text('');
                $ssidInput.removeClass("input-error");
                $framesInput.removeClass("input-error");
            },
            success: function(response) {
                console.log(response);
            },
            error: function(error) {
                console.log(error);
            },
            complete: function() {
                $submitButton.attr('class', originalButtonClass);
                $submitButton.attr('style', originalButtonStyle);
                $submitButton.text(originalButtonText);
                $submitButton.prop("disabled", false);
            }
        });
    });


    $("#Deauth-Submit").on("click", function(event) {
        event.preventDefault();

        var $apInput = $("#Deauth-AP");
        var $targetInput = $("#Deauth-Target");
        var $framesInput = $("#Deauth-Frames");
        var ap = $apInput.val();
        var target = $targetInput.val() || "ff:ff:ff:ff:ff:ff";
        var frames = $framesInput.val();
        var authorized = $("#Deauth-Authorized").is(":checked");
        var selectedInterface = $("#interface-select-Deauth").val();

        if (!ap || !frames || !authorized) {
            if (!ap) { $apInput.addClass("input-error"); }
            if (!frames) { $framesInput.addClass("input-error"); }
            if (!authorized) { $("#Deauth-Authorized").addClass("input-error"); }
            return;
        }

        var $submitButton = $("#Deauth-Submit");
        var originalButtonClass = $submitButton.attr('class');
        var originalButtonStyle = $submitButton.attr('style');
        var originalButtonText = $submitButton.text();

        $.ajax({
            url: "/deauth",
            type: "POST",
            data: {
                ap: ap,
                target: target,
                frames: frames,
                authorized: authorized ? "on" : "",
                selectedInterface: selectedInterface
            },
            beforeSend: function() {
                $submitButton.prop("disabled", true);
                $submitButton.attr('class', 'spinner-border text-primary');
                $submitButton.text('');
                $apInput.removeClass("input-error");
                $framesInput.removeClass("input-error");
                $("#Deauth-Authorized").removeClass("input-error");
            },
            success: function(response) {
                console.log(response);
            },
            error: function(error) {
                console.log(error);
            },
            complete: function() {
                $submitButton.attr('class', originalButtonClass);
                $submitButton.attr('style', originalButtonStyle);
                $submitButton.text(originalButtonText);
                $submitButton.prop("disabled", false);
            }
        });
    });

    $("#EvilTwin-Submit").on("click", function(event) {
        event.preventDefault();

        var $ssidInput = $("#EvilTwin-SSID");
        var $bssidInput = $("#EvilTwin-BSSID");
        var $channelInput = $("#EvilTwin-Channel");
        var $authorizedInput = $("#EvilTwin-Authorized");
        var $status = $("#EvilTwin-Status");
        var ssid = $ssidInput.val();
        var bssid = $bssidInput.val();
        var channel = $channelInput.val();
        var authorized = $authorizedInput.is(":checked");

        if (!ssid || !bssid || !channel || !authorized) {
            if (!ssid) { $ssidInput.addClass("input-error"); }
            if (!bssid) { $bssidInput.addClass("input-error"); }
            if (!channel) { $channelInput.addClass("input-error"); }
            if (!authorized) { $authorizedInput.addClass("input-error"); }
            $status.removeClass("text-success").addClass("text-danger").text("Complete SSID, BSSID, channel, and authorization confirmation.");
            return;
        }

        var $submitButton = $("#EvilTwin-Submit");
        var originalButtonClass = $submitButton.attr('class');
        var originalButtonStyle = $submitButton.attr('style');
        var originalButtonText = $submitButton.text();

        $.ajax({
            url: "/evil-twin-lab",
            type: "POST",
            data: {
                action: $("#EvilTwin-Action").val(),
                ssid: ssid,
                bssid: bssid,
                channel: channel,
                durationMinutes: $("#EvilTwin-Duration").val(),
                portalMessage: $("#EvilTwin-Portal-Message").val(),
                authorized: authorized ? "on" : "",
                selectedInterface: $("#interface-select-EvilTwin").val()
            },
            beforeSend: function() {
                $submitButton.prop("disabled", true);
                $submitButton.attr('class', 'spinner-border text-primary');
                $submitButton.text('');
                $ssidInput.removeClass("input-error");
                $bssidInput.removeClass("input-error");
                $channelInput.removeClass("input-error");
                $authorizedInput.removeClass("input-error");
                $status.removeClass("text-danger text-success").text('');
            },
            success: function(response) {
                var guidance = response.run && response.run.detection_guidance ? response.run.detection_guidance[0] : '';
                $status.removeClass("text-danger").addClass("text-success").text((response.message || "Lab workflow recorded.") + " " + guidance);
            },
            error: function(error) {
                var message = error.responseJSON && error.responseJSON.message ? error.responseJSON.message : "Failed to prepare lab workflow.";
                $status.removeClass("text-success").addClass("text-danger").text(message);
            },
            complete: function() {
                $submitButton.attr('class', originalButtonClass);
                $submitButton.attr('style', originalButtonStyle);
                $submitButton.text(originalButtonText);
                $submitButton.prop("disabled", false);
            }
        });
    });

    $("#Pineap-Submit").on("click", function(event) {
        event.preventDefault();
        var $status = $("#Pineap-Status");
        var authorized = $("#Pineap-Authorized").is(":checked");
        if (!authorized) {
            $("#Pineap-Authorized").addClass("input-error");
            $status.removeClass("text-success").addClass("text-danger").text("Confirm the isolated authorized lab scope before running a campaign workflow.");
            return;
        }
        var $submitButton = $("#Pineap-Submit");
        var originalButtonClass = $submitButton.attr('class');
        var originalButtonStyle = $submitButton.attr('style');
        var originalButtonText = $submitButton.text();
        $.ajax({
            url: "/pineap-lab",
            type: "POST",
            data: {
                action: $("#Pineap-Action").val(),
                ssid: $("#Pineap-SSID").val(),
                bssid: $("#Pineap-BSSID").val(),
                channel: $("#Pineap-Channel").val(),
                modules: $("#Pineap-Modules").val(),
                notes: $("#Pineap-Notes").val(),
                authorized: authorized ? "on" : "",
                selectedInterface: $("#interface-select-Pineap").val()
            },
            beforeSend: function() {
                $submitButton.prop("disabled", true);
                $submitButton.attr('class', 'spinner-border text-primary');
                $submitButton.text('');
                $("#Pineap-Authorized").removeClass("input-error");
                $status.removeClass("text-danger text-success").text('');
            },
            success: function(response) {
                var count = response.run && response.run.recon ? response.run.recon.length : 0;
                $status.removeClass("text-danger").addClass("text-success").text((response.message || "Campaign workflow recorded.") + " Recon networks: " + count + ".");
            },
            error: function(error) {
                var message = error.responseJSON && error.responseJSON.message ? error.responseJSON.message : "Failed to run campaign workflow.";
                $status.removeClass("text-success").addClass("text-danger").text(message);
            },
            complete: function() {
                $submitButton.attr('class', originalButtonClass);
                $submitButton.attr('style', originalButtonStyle);
                $submitButton.text(originalButtonText);
                $submitButton.prop("disabled", false);
            }
        });
    });

    $("#Handshake-Submit").on("click", function(event) {
        event.preventDefault();
        var $status = $("#Handshake-Status");
        var required = [$("#Handshake-SSID"), $("#Handshake-BSSID"), $("#Handshake-Channel")];
        var missing = false;
        required.forEach(function($input) {
            if (!$input.val()) {
                $input.addClass("input-error");
                missing = true;
            }
        });
        if (!$("#Handshake-Authorized").is(":checked")) {
            $("#Handshake-Authorized").addClass("input-error");
            missing = true;
        }
        if (missing) {
            $status.removeClass("text-success").addClass("text-danger").text("Complete SSID, BSSID, channel, and authorization confirmation.");
            return;
        }
        var $submitButton = $("#Handshake-Submit");
        var originalButtonClass = $submitButton.attr('class');
        var originalButtonStyle = $submitButton.attr('style');
        var originalButtonText = $submitButton.text();
        var formData = new FormData($(".handshake-lab-card form")[0]);
        formData.set("authorized", "on");
        formData.set("selectedInterface", $("#interface-select-Handshake").val());
        $.ajax({
            url: "/handshake-lab",
            type: "POST",
            data: formData,
            processData: false,
            contentType: false,
            beforeSend: function() {
                $submitButton.prop("disabled", true);
                $submitButton.attr('class', 'spinner-border text-primary');
                $submitButton.text('');
                required.forEach(function($input) { $input.removeClass("input-error"); });
                $("#Handshake-Authorized").removeClass("input-error");
                $status.removeClass("text-danger text-success").text('');
            },
            success: function(response) {
                var status = response.record && response.record.validation_status ? response.record.validation_status : "cataloged";
                $status.removeClass("text-danger").addClass("text-success").text((response.message || "Evidence cataloged.") + " Status: " + status + ".");
            },
            error: function(error) {
                var message = error.responseJSON && error.responseJSON.message ? error.responseJSON.message : "Failed to catalog evidence.";
                $status.removeClass("text-success").addClass("text-danger").text(message);
            },
            complete: function() {
                $submitButton.attr('class', originalButtonClass);
                $submitButton.attr('style', originalButtonStyle);
                $submitButton.text(originalButtonText);
                $submitButton.prop("disabled", false);
            }
        });
    });

    $("#Aireplay-Deauth-Submit").on("click", function(event) {
        event.preventDefault();

        var $apInput = $("#Aireplay-Deauth-AP");
        var $targetInput = $("#Aireplay-Deauth-Target");
        var $framesInput = $("#Aireplay-Deauth-Frames");
        var ap = $apInput.val();
        var target = $targetInput.val() || "ff:ff:ff:ff:ff:ff";
        var frames = $framesInput.val();
        var selectedInterface = $("#interface-select-AireplayDeauth").val();

        if (!ap || !frames) {
            if (!ap) { $apInput.addClass("input-error"); }
            if (!frames) { $framesInput.addClass("input-error"); }
            return;
        }

        var $submitButton = $("#Aireplay-Deauth-Submit");
        var originalButtonClass = $submitButton.attr('class');
        var originalButtonStyle = $submitButton.attr('style');
        var originalButtonText = $submitButton.text();

        $.ajax({
            url: "/aireplay-deauth",
            type: "POST",
            data: {
                ap: ap,
                target: target,
                frames: frames,
                selectedInterface: selectedInterface
            },
            beforeSend: function() {
                $submitButton.prop("disabled", true);
                $submitButton.attr('class', 'spinner-border text-primary');
                $submitButton.text('');
                $apInput.removeClass("input-error");
                $framesInput.removeClass("input-error");
            },
            success: function(response) {
                console.log(response);
            },
            error: function(error) {
                console.log(error);
            },
            complete: function() {
                $submitButton.attr('class', originalButtonClass);
                $submitButton.attr('style', originalButtonStyle);
                $submitButton.text(originalButtonText);
                $submitButton.prop("disabled", false);
            }
        });
    });

});
