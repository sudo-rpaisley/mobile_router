// Handle automatic network adapter updates from the server without full page reloads.
document.addEventListener('DOMContentLoaded', function () {
  var status = document.getElementById('adapter-auto-update-status');
  var pollIntervalMs = 5000;
  var lastSnapshot = null;
  var socketConnected = false;
  var lastInterfaces = null;

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

  function replaceFragment(nextDocument, selector) {
    var current = document.querySelector(selector);
    var next = nextDocument.querySelector(selector);
    if (current && next) {
      current.replaceWith(next);
      return true;
    }
    return false;
  }

  function refreshPageFragments() {
    setStatus('Adapters changed. Updating...');
    return fetch(window.location.href, { headers: { 'X-Requested-With': 'fetch-fragment' } })
      .then(function (response) { return response.text(); })
      .then(function (html) {
        var nextDocument = new DOMParser().parseFromString(html, 'text/html');
        var replaced = false;
        [
          '#primary-nav-links',
          '.interface-category-page',
          '.interface-detail-page .interface-badges',
          '.interface-detail-page .interface-detail-grid'
        ].forEach(function (selector) {
          replaced = replaceFragment(nextDocument, selector) || replaced;
        });
        setStatus(replaced ? 'Auto updating' : 'No visible adapter changes');
      })
      .catch(function () {
        setStatus('Adapter update failed');
      });
  }

  function announceNewInterfaces(interfaces) {
    if (!lastInterfaces || !window.deviceAlerts) {
      lastInterfaces = interfaces || [];
      return;
    }
    var known = new Set(lastInterfaces.map(function (iface) { return iface.name; }));
    (interfaces || []).forEach(function (iface) {
      if (!known.has(iface.name)) {
        window.deviceAlerts.notify('New adapter detected', `${iface.name} (${iface.interface_type || 'Unknown'})`);
      }
    });
    lastInterfaces = interfaces || [];
  }

  function handleAdapterChange(interfaces) {
    var nextSnapshot = snapshot(interfaces);
    if (lastSnapshot === null) {
      lastSnapshot = nextSnapshot;
      announceNewInterfaces(interfaces);
      return;
    }
    if (nextSnapshot !== lastSnapshot) {
      lastSnapshot = nextSnapshot;
      announceNewInterfaces(interfaces);
      refreshPageFragments();
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
      handleAdapterChange(data.interfaces || []);
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
        handleAdapterChange(data.interfaces || []);
      })
      .catch(function () {
        setStatus('Auto update unavailable');
      });
  }

  pollAdapters();
  window.setInterval(pollAdapters, pollIntervalMs);
});
