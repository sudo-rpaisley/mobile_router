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
});