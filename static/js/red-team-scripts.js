$(document).ready(function () {
    function isRedTeamAuthorized() {
        return $("#red-team-authorization").is(":checked");
    }

    function requireRedTeamAuthorization() {
        if (isRedTeamAuthorized()) {
            return true;
        }
        alert("Confirm authorization before running red-team actions.");
        $("#red-team-authorization").focus();
        return false;
    }

    function authorizationPayload() {
        return isRedTeamAuthorized() ? "true" : "false";
    }

    function syncRedTeamButtons() {
        $(".red-team-grid button").prop("disabled", !isRedTeamAuthorized());
    }

    $("#red-team-authorization").on("change", syncRedTeamButtons);
    syncRedTeamButtons();

    $("#DoS-Submit").on("click", function(event) {
        event.preventDefault(); //stop the form submitting
        if (!requireRedTeamAuthorization()) { return; }
    
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
                selectedInterface: selectedInterface,
                authorizationConfirmed: authorizationPayload()
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
                syncRedTeamButtons();
            }
        });
    });
    

    $("#DoS-Broadcast-Submit").on("click", function(event) {
        event.preventDefault(); //stop the form submitting
        if (!requireRedTeamAuthorization()) { return; }
    
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
                selectedInterface: selectedInterface,
                authorizationConfirmed: authorizationPayload()
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
                syncRedTeamButtons();
            }
        });
    });


    $("#Beacon-Advertise-Submit").on("click", function(event) {
        event.preventDefault();
        if (!requireRedTeamAuthorization()) { return; }

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
                selectedInterface: selectedInterface,
                authorizationConfirmed: authorizationPayload()
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
                syncRedTeamButtons();
            }
        });
    });


    $("#Deauth-Submit").on("click", function(event) {
        event.preventDefault();
        if (!requireRedTeamAuthorization()) { return; }

        var $apInput = $("#Deauth-AP");
        var $targetInput = $("#Deauth-Target");
        var $framesInput = $("#Deauth-Frames");
        var ap = $apInput.val();
        var target = $targetInput.val() || "ff:ff:ff:ff:ff:ff";
        var frames = $framesInput.val();
        var selectedInterface = $("#interface-select-Deauth").val();

        if (!ap || !frames) {
            if (!ap) { $apInput.addClass("input-error"); }
            if (!frames) { $framesInput.addClass("input-error"); }
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
                selectedInterface: selectedInterface,
                authorizationConfirmed: authorizationPayload()
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
                syncRedTeamButtons();
            }
        });
    });

    $("#Aireplay-Deauth-Submit").on("click", function(event) {
        event.preventDefault();
        if (!requireRedTeamAuthorization()) { return; }

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
                selectedInterface: selectedInterface,
                authorizationConfirmed: authorizationPayload()
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
                syncRedTeamButtons();
            }
        });
    });

});
