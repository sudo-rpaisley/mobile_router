// Handle automatic network adapter updates from the server without full page reloads.
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
        addresses: iface.addresses,
        manufacturer: iface.manufacturer
      };
    }));
  }

  function replaceHtml(selector, html) {
    var current = document.querySelector(selector);
    if (current && html) {
      current.innerHTML = html;
      return true;
    }
    return false;
  }

  function applyFragments(fragments) {
    var replaced = false;
    fragments = fragments || {};
    replaced = replaceHtml('#primary-nav-links', fragments.primary_nav_links) || replaced;
    replaced = replaceHtml('.interface-category-page', fragments.interface_categories) || replaced;
    if (replaced) {
      document.dispatchEvent(new CustomEvent('adapter-fragments-updated'));
    }
    return replaced;
  }

  function requestAdapterUpdate(force) {
    return fetch('/adapters/updates', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'adapter-fragment'
      },
      body: JSON.stringify({ snapshot: force ? null : lastSnapshot, title: document.title || 'Home' })
    })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        lastSnapshot = data.snapshot || lastSnapshot;
        if (data.changed) {
          setStatus('Adapters changed. Updating...');
          setStatus(applyFragments(data.fragments) ? 'Auto updating' : 'No visible adapter changes');
        } else {
          setStatus(socketConnected ? 'Auto updating' : 'Auto update polling');
        }
        return data;
      })
      .catch(function () {
        setStatus('Adapter update failed');
      });
  }

  function handleAdapterChange(interfaces) {
    var nextSnapshot = snapshot(interfaces);
    if (lastSnapshot === null) {
      lastSnapshot = nextSnapshot;
      return;
    }
    if (nextSnapshot !== lastSnapshot) {
      requestAdapterUpdate(true);
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
    requestAdapterUpdate(false);
  }

  requestAdapterUpdate(true);
  window.setInterval(pollAdapters, pollIntervalMs);
});
