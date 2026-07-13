// Handle automatic network adapter updates from the server.
document.addEventListener('DOMContentLoaded', function () {
  var status = document.getElementById('adapter-auto-update-status');
  var pollIntervalMs = 5000;
  var lastSnapshot = null;
  var socketConnected = false;

  function setStatus(message) {
    if (status) {
      status.textContent = message;
    }
  }

  function snapshot(interfaces) {
    return JSON.stringify((interfaces || []).map(function (iface) {
      return {
        name: iface.name,
        interface_type: iface.interface_type,
        state: iface.state,
        addresses: iface.addresses
      };
    }));
  }

  function reloadForAdapterChange(interfaces) {
    var nextSnapshot = snapshot(interfaces);
    if (lastSnapshot === null) {
      lastSnapshot = nextSnapshot;
      return;
    }
    if (nextSnapshot !== lastSnapshot) {
      setStatus('Adapters changed. Refreshing...');
      window.location.reload();
    }
  }

  if (window.io) {
    var socket = io();
    socket.on('connect', function () {
      socketConnected = true;
      setStatus('Auto updating');
    });
    socket.on('disconnect', function () {
      socketConnected = false;
      setStatus('Auto update polling');
    });
    socket.on('update_interfaces', function (data) {
      setStatus('Adapters changed. Refreshing...');
      window.location.reload();
    });
  } else {
    setStatus('Auto update polling');
  }

  function pollAdapters() {
    if (socketConnected) {
      return;
    }
    fetch('/adapters', { method: 'POST' })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        setStatus('Auto update polling');
        reloadForAdapterChange(data.interfaces || []);
      })
      .catch(function () {
        setStatus('Auto update unavailable');
      });
  }

  pollAdapters();
  window.setInterval(pollAdapters, pollIntervalMs);
});
