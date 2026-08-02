(function () {
    "use strict";

    var jobId = null;
    var heartbeatTimer = null;
    var statusTimer = null;

    function csrfToken() {
        return $("#Deauth-CSRF").val() || "";
    }

    function setStatus(message, isError) {
        $("#Deauth-Status")
            .toggleClass("text-danger", Boolean(isError))
            .toggleClass("text-success", !isError)
            .text(message || "");
    }

    function setActive(active) {
        $("#Deauth-Start").prop("disabled", active);
        $("#Deauth-Stop").prop("disabled", !active);
        $("#Deauth-AP, #Deauth-Target, #Deauth-Authorized, #interface-select-Deauth")
            .prop("disabled", active);
    }

    function stopTimers() {
        if (heartbeatTimer) {
            window.clearInterval(heartbeatTimer);
            heartbeatTimer = null;
        }
        if (statusTimer) {
            window.clearInterval(statusTimer);
            statusTimer = null;
        }
    }

    function renderJob(job) {
        if (!job || !job.id) {
            jobId = null;
            setActive(false);
            $("#Deauth-Progress").val(0);
            return;
        }

        jobId = job.active ? job.id : null;
        setActive(Boolean(job.active));
        var maximum = Number(job.max_run_seconds || 15);
        var remaining = Math.max(0, Number(job.remaining_seconds || 0));
        $("#Deauth-Progress").attr("max", maximum).val(maximum - remaining);

        var message = job.active
            ? "Active on " + job.interface + ": " + job.frames_sent +
              " frame(s) sent; automatic stop in " + remaining.toFixed(1) + "s."
            : "Stopped: " + (job.stop_reason || job.status || "complete") +
              ". " + (job.frames_sent || 0) + " frame(s) sent.";

        setStatus(message, job.status === "failed");
        if (!job.active) {
            stopTimers();
        }
    }

    function statusPoll() {
        $.ajax({
            url: "/deauth/status",
            type: "GET",
            success: function (response) {
                renderJob(response.job);
            },
            error: function () {
                stopTimers();
                setActive(false);
                setStatus("Unable to confirm bounded deauth job status.", true);
            }
        });
    }

    function heartbeat() {
        if (!jobId) {
            return;
        }
        $.ajax({
            url: "/deauth/heartbeat",
            type: "POST",
            data: {jobId: jobId, csrf_token: csrfToken()},
            success: function (response) {
                renderJob(response.job);
            },
            error: function () {
                stopTimers();
                statusPoll();
            }
        });
    }

    function beginMonitoring() {
        stopTimers();
        heartbeatTimer = window.setInterval(heartbeat, 2000);
        statusTimer = window.setInterval(statusPoll, 1000);
    }

    $("#Deauth-Start").on("click", function (event) {
        event.preventDefault();
        var ap = $("#Deauth-AP").val();
        var authorized = $("#Deauth-Authorized").is(":checked");
        if (!ap || !authorized) {
            if (!ap) {
                $("#Deauth-AP").addClass("input-error");
            }
            if (!authorized) {
                $("#Deauth-Authorized").addClass("input-error");
            }
            setStatus("Enter the lab AP and confirm the isolated authorized scope.", true);
            return;
        }

        $.ajax({
            url: "/deauth/start",
            type: "POST",
            data: {
                ap: ap,
                target: $("#Deauth-Target").val() || "ff:ff:ff:ff:ff:ff",
                authorized: "on",
                selectedInterface: $("#interface-select-Deauth").val(),
                csrf_token: csrfToken()
            },
            beforeSend: function () {
                $("#Deauth-Start").prop("disabled", true);
                $("#Deauth-AP, #Deauth-Authorized").removeClass("input-error");
                setStatus("Starting bounded lab transmission…", false);
            },
            success: function (response) {
                renderJob(response.job);
                beginMonitoring();
            },
            error: function (error) {
                setActive(false);
                var message = error.responseJSON && error.responseJSON.message
                    ? error.responseJSON.message
                    : "Unable to start bounded deauth lab run.";
                setStatus(message, true);
            }
        });
    });

    $("#Deauth-Stop").on("click", function (event) {
        event.preventDefault();
        $.ajax({
            url: "/deauth/stop",
            type: "POST",
            data: {jobId: jobId || "", csrf_token: csrfToken()},
            success: function (response) {
                renderJob(response.job);
                statusPoll();
            },
            error: function (error) {
                var message = error.responseJSON && error.responseJSON.message
                    ? error.responseJSON.message
                    : "Unable to stop the bounded deauth lab run.";
                setStatus(message, true);
            }
        });
    });

    $("#Deauth-Emergency-Stop").on("click", function (event) {
        event.preventDefault();
        $.ajax({
            url: "/deauth/emergency-stop",
            type: "POST",
            data: {csrf_token: csrfToken()},
            success: function (response) {
                renderJob(response.job);
                statusPoll();
            },
            error: function () {
                setStatus("Emergency-stop request failed. Use the local stop command.", true);
            }
        });
    });

    window.addEventListener("beforeunload", function () {
        if (!jobId || !navigator.sendBeacon) {
            return;
        }
        var data = new FormData();
        data.append("jobId", jobId);
        data.append("csrf_token", csrfToken());
        navigator.sendBeacon("/deauth/stop", data);
    });

    $(document).ready(function () {
        setActive(false);
        statusPoll();
    });
}());
