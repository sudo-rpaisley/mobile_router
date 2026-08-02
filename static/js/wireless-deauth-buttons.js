(function () {
  'use strict';

  const BROADCAST_MAC = 'ff:ff:ff:ff:ff:ff';
  const MAC_PATTERN = /^([0-9a-f]{2}:){5}[0-9a-f]{2}$/i;
  const HEARTBEAT_INTERVAL_MS = 2000;
  const forms = new Set();
  let activeJob = null;
  let heartbeatTimer = null;
  let startedHere = false;

  function csrfToken() {
    const navbar = document.querySelector('.app-navbar');
    return navbar ? String(navbar.dataset.csrfToken || '') : '';
  }

  function boundedText(value) {
    return String(value || '').trim().slice(0, 500);
  }

  async function postForm(url, values) {
    const body = new URLSearchParams(values || {});
    body.set('csrf_token', csrfToken());
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      body: body,
      credentials: 'same-origin'
    });
    const payload = await response.json().catch(function () {
      return { status: 'error', message: `Request failed (${response.status})` };
    });
    if (!response.ok || payload.status === 'error') {
      throw new Error(payload.message || `Request failed (${response.status})`);
    }
    return payload;
  }

  async function fetchStatus() {
    if (!csrfToken()) return null;
    const response = await fetch('/deauth/status', { credentials: 'same-origin' });
    if (!response.ok) return null;
    const payload = await response.json().catch(function () { return null; });
    return payload && payload.status === 'success' ? payload.job : null;
  }

  function formValues(form) {
    const apInput = form.querySelector('[data-deauth-ap-input]');
    const interfaceInput = form.querySelector('[data-deauth-interface-input]');
    return {
      ap: boundedText(apInput ? apInput.value : form.dataset.ap).toLowerCase(),
      target: boundedText(form.dataset.target || BROADCAST_MAC).toLowerCase(),
      selectedInterface: boundedText(interfaceInput ? interfaceInput.value : form.dataset.interface),
      authorized: 'on'
    };
  }

  function matchesJob(form, job) {
    if (!job || !job.active) return false;
    const values = formValues(form);
    return values.ap === String(job.ap || '').toLowerCase()
      && values.target === String(job.target || '').toLowerCase()
      && values.selectedInterface === String(job.interface || '');
  }

  function statusElement(form) {
    return form.querySelector('[data-deauth-session-status]');
  }

  function setStatus(form, message, kind) {
    const status = statusElement(form);
    if (!status) return;
    status.textContent = boundedText(message);
    status.classList.remove('text-muted', 'text-success', 'text-danger', 'text-warning');
    status.classList.add(kind === 'success' ? 'text-success' : kind === 'error' ? 'text-danger' : kind === 'warning' ? 'text-warning' : 'text-muted');
  }

  function renderForms() {
    forms.forEach(function (form) {
      if (!document.documentElement.contains(form)) {
        forms.delete(form);
        return;
      }
      const button = form.querySelector('[data-deauth-session-button]');
      if (!button) return;
      const matching = matchesJob(form, activeJob);
      if (matching) {
        button.disabled = false;
        button.className = 'btn btn-danger btn-sm';
        button.textContent = 'Stop deauth';
        setStatus(form, `${Math.ceil(Number(activeJob.remaining_seconds || 0))}s remaining · ${Number(activeJob.frames_sent || 0)} frames sent`, 'warning');
      } else if (activeJob && activeJob.active) {
        button.disabled = true;
        button.className = 'btn btn-outline-secondary btn-sm';
        button.textContent = 'Another deauth session is active';
        setStatus(form, `Active on ${activeJob.interface || 'another adapter'} for ${activeJob.target || 'another target'}.`, 'warning');
      } else {
        button.disabled = !csrfToken() || button.dataset.permanentlyDisabled === 'true';
        button.className = 'btn btn-outline-danger btn-sm';
        button.textContent = form.dataset.target === BROADCAST_MAC ? 'Start AP deauth' : 'Start device deauth';
        if (!csrfToken()) {
          setStatus(form, 'Administrator login is required.', 'error');
        } else if (activeJob && !activeJob.active && activeJob.stop_reason) {
          setStatus(form, `Stopped: ${String(activeJob.stop_reason).replaceAll('_', ' ')}.`, activeJob.error ? 'error' : 'success');
        }
      }
    });
  }

  function stopHeartbeat() {
    if (heartbeatTimer) window.clearInterval(heartbeatTimer);
    heartbeatTimer = null;
  }

  function beginHeartbeat() {
    stopHeartbeat();
    if (!activeJob || !activeJob.active) return;
    heartbeatTimer = window.setInterval(async function () {
      if (!activeJob || !activeJob.active) {
        stopHeartbeat();
        return;
      }
      try {
        const payload = await postForm('/deauth/heartbeat', { jobId: activeJob.id });
        activeJob = payload.job;
      } catch (error) {
        activeJob = await fetchStatus();
        if (!activeJob || !activeJob.active) stopHeartbeat();
      }
      renderForms();
    }, HEARTBEAT_INTERVAL_MS);
  }

  async function startSession(form) {
    const values = formValues(form);
    const confirmation = form.querySelector('[data-deauth-authorized]');
    if (!MAC_PATTERN.test(values.ap)) {
      setStatus(form, 'Enter a valid AP BSSID.', 'error');
      return;
    }
    if (!MAC_PATTERN.test(values.target)) {
      setStatus(form, 'This device does not have a valid MAC address.', 'error');
      return;
    }
    if (!values.selectedInterface || values.selectedInterface === 'Select Interface') {
      setStatus(form, 'Choose the wireless adapter that will send the frames.', 'error');
      return;
    }
    if (confirmation && !confirmation.checked) {
      setStatus(form, 'Confirm this is an authorized isolated lab first.', 'error');
      return;
    }
    if (!confirmation && !window.confirm('Start a bounded deauth session on this authorized isolated lab network? It stops after 15 seconds or if this page loses its heartbeat.')) {
      return;
    }

    const button = form.querySelector('[data-deauth-session-button]');
    button.disabled = true;
    button.textContent = 'Starting…';
    try {
      const payload = await postForm('/deauth/start', values);
      activeJob = payload.job;
      startedHere = true;
      beginHeartbeat();
      renderForms();
    } catch (error) {
      setStatus(form, error.message || 'Unable to start bounded deauth.', 'error');
      renderForms();
    }
  }

  async function stopSession(form) {
    const button = form.querySelector('[data-deauth-session-button]');
    button.disabled = true;
    button.textContent = 'Stopping…';
    try {
      const payload = await postForm('/deauth/stop', { jobId: activeJob && activeJob.id ? activeJob.id : '' });
      activeJob = payload.job;
      startedHere = false;
      stopHeartbeat();
      window.setTimeout(async function () {
        activeJob = await fetchStatus();
        renderForms();
      }, 250);
    } catch (error) {
      setStatus(form, error.message || 'Unable to stop bounded deauth.', 'error');
      renderForms();
    }
  }

  function registerForm(form) {
    if (!form || form.dataset.boundedDeauthReady === 'true') return;
    form.dataset.boundedDeauthReady = 'true';
    forms.add(form);
    const button = form.querySelector('[data-deauth-session-button]');
    if (button) {
      button.addEventListener('click', function () {
        if (matchesJob(form, activeJob)) stopSession(form);
        else startSession(form);
      });
    }
    renderForms();
  }

  function upgradeNetworkForm(form) {
    if (!form || form.dataset.boundedDeauthReady === 'true') return;
    const toggle = form.querySelector('.wireless-deauth-toggle');
    if (!toggle) return;
    const validAp = MAC_PATTERN.test(String(form.dataset.ap || ''));
    form.dataset.target = BROADCAST_MAC;
    form.innerHTML = [
      `<button type="button" class="btn btn-outline-danger btn-sm" data-deauth-session-button ${validAp ? '' : 'disabled data-permanently-disabled="true"'}>Start AP deauth</button>`,
      `<p class="wireless-deauth-help text-muted mb-0" data-deauth-session-status>${validAp ? 'Authorized isolated lab only · bounded to 15 seconds with heartbeat stop' : 'Deauth requires a discovered AP BSSID'}</p>`
    ].join('');
    const button = form.querySelector('[data-deauth-session-button]');
    if (button && !validAp) button.dataset.permanentlyDisabled = 'true';
    registerForm(form);
  }

  async function loadInterfaces(select) {
    try {
      const response = await fetch('/adapters', { credentials: 'same-origin' });
      const payload = await response.json();
      const interfaces = Array.isArray(payload.interfaces) ? payload.interfaces : [];
      interfaces.forEach(function (item) {
        const type = String(item.interface_type || '').toLowerCase();
        if (type === 'loopback' || type === 'bluetooth') return;
        const option = document.createElement('option');
        option.value = item.name;
        option.textContent = `${item.name}${item.interface_type ? ` · ${item.interface_type}` : ''}`;
        select.appendChild(option);
      });
    } catch (error) {
      const option = document.createElement('option');
      option.value = '';
      option.textContent = 'Unable to load adapters';
      select.appendChild(option);
    }
  }

  function clientMacAddress() {
    const rows = Array.from(document.querySelectorAll('.interface-definition-list > div'));
    const macRow = rows.find(function (row) {
      const term = row.querySelector('dt');
      return term && term.textContent.trim() === 'MAC Address';
    });
    const value = macRow && macRow.querySelector('dd') ? macRow.querySelector('dd').textContent.trim() : '';
    return MAC_PATTERN.test(value) ? value.toLowerCase() : '';
  }

  function injectClientDeviceControl() {
    if (!window.location.pathname.startsWith('/clients/')) return;
    const kicker = document.querySelector('.page-kicker');
    if (kicker && kicker.textContent.trim() === 'Bluetooth Device') return;
    if (document.querySelector('[data-client-deauth-panel]')) return;
    const mac = clientMacAddress();
    if (!mac) return;
    const overview = document.querySelector('main.page-shell .theme-card.card');
    if (!overview) return;

    const panel = document.createElement('section');
    panel.className = 'theme-card card';
    panel.dataset.clientDeauthPanel = 'true';
    panel.innerHTML = `
      <div class="card-body">
        <h2 class="theme-section-title">Bounded Device Deauth</h2>
        <p class="text-muted">Target only this device (${mac}) on an authorized isolated lab. The server stops after 15 seconds, on lost browser heartbeat, on manual Stop, or on emergency stop.</p>
        <form class="theme-form" data-client-deauth-form data-target="${mac}">
          <div class="form-row">
            <div class="col">
              <label>Access point BSSID</label>
              <input class="form-control" data-deauth-ap-input placeholder="aa:bb:cc:dd:ee:ff" autocomplete="off">
            </div>
            <div class="col">
              <label>Wireless adapter</label>
              <select class="form-control" data-deauth-interface-input><option value="">Select interface</option></select>
            </div>
          </div>
          <label class="form-check deauth-lab-confirm mt-3">
            <input class="form-check-input" type="checkbox" data-deauth-authorized>
            <span class="form-check-label">I confirm this is an authorized isolated class lab.</span>
          </label>
          <div class="theme-actions">
            <button type="button" class="btn btn-outline-danger btn-sm" data-deauth-session-button>Start device deauth</button>
          </div>
          <p class="small text-muted mb-0" data-deauth-session-status>Enter the AP BSSID and choose the transmitting adapter.</p>
        </form>
      </div>`;
    overview.insertAdjacentElement('afterend', panel);
    const form = panel.querySelector('[data-client-deauth-form]');
    const select = form.querySelector('[data-deauth-interface-input]');
    loadInterfaces(select).then(function () {
      if (activeJob && activeJob.active && String(activeJob.target || '').toLowerCase() === mac) {
        form.querySelector('[data-deauth-ap-input]').value = activeJob.ap || '';
        select.value = activeJob.interface || '';
        form.querySelector('[data-deauth-authorized]').checked = true;
        startedHere = true;
        beginHeartbeat();
      }
      renderForms();
    });
    registerForm(form);
  }

  function scanForForms(root) {
    const scope = root && root.querySelectorAll ? root : document;
    if (scope.matches && scope.matches('.wireless-deauth-form')) upgradeNetworkForm(scope);
    scope.querySelectorAll('.wireless-deauth-form').forEach(upgradeNetworkForm);
  }

  document.addEventListener('change', function (event) {
    if (!event.target.matches('.wireless-deauth-toggle')) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    upgradeNetworkForm(event.target.closest('.wireless-deauth-form'));
  }, true);

  const observer = new MutationObserver(function (mutations) {
    mutations.forEach(function (mutation) {
      mutation.addedNodes.forEach(function (node) {
        if (node.nodeType === Node.ELEMENT_NODE) scanForForms(node);
      });
    });
  });

  async function initialize() {
    scanForForms(document);
    injectClientDeviceControl();
    observer.observe(document.documentElement, { childList: true, subtree: true });
    activeJob = await fetchStatus();
    injectClientDeviceControl();
    renderForms();
  }

  window.addEventListener('pagehide', function () {
    if (!startedHere || !activeJob || !activeJob.active || !csrfToken()) return;
    const body = new URLSearchParams({ jobId: activeJob.id || '', csrf_token: csrfToken() });
    const blob = new Blob([body.toString()], { type: 'application/x-www-form-urlencoded;charset=UTF-8' });
    navigator.sendBeacon('/deauth/stop', blob);
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize);
  else initialize();
}());
