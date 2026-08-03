(function () {
  'use strict';

  const output = document.querySelector('[data-vlan-output]');

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function show(kind, message, detail) {
    if (!output) return;
    output.innerHTML = `<div class="alert alert-${kind}" role="status"><strong>${escapeHtml(message)}</strong>${detail ? `<p class="mb-0 mt-1">${escapeHtml(detail)}</p>` : ''}</div>`;
    output.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function responseMessage(payload, form) {
    if (payload.message) return payload.message;
    if (payload.vlan) return `${payload.vlan.label} saved.`;
    if (payload.investigation) {
      const summary = payload.investigation.summary || {};
      return `Investigation complete: ${summary.reachable_hosts || 0} of ${summary.total_hosts || 0} hosts reachable.`;
    }
    if (payload.rule) return 'Segmentation expectation saved.';
    if (payload.result) return payload.result.mismatch ? 'Segmentation result does not match the saved expectation.' : 'Segmentation result matches the saved expectation.';
    if (payload.integration) return 'Infrastructure integration saved.';
    if (payload.probe) return 'Remote probe configuration saved.';
    if (payload.vlans) return `Imported ${payload.vlans.length} VLAN definition(s) and ${(payload.devices || []).length} device record(s).`;
    return `${form.dataset.actionLabel || 'Operation'} completed.`;
  }

  async function submitForm(form) {
    const confirmText = form.getAttribute('data-confirm');
    if (confirmText && !window.confirm(confirmText)) return;
    const button = form.querySelector('button[type="submit"]');
    const original = button ? button.textContent : '';
    if (button) {
      button.disabled = true;
      button.textContent = form.action.includes('/investigate') ? 'Investigating…' : 'Working…';
    }
    show('info', form.action.includes('/investigate') ? 'Running bounded VLAN investigation…' : 'Saving VLAN records…', 'Long routed investigations may take several minutes. Do not close the page.');

    try {
      const response = await fetch(form.action, {
        method: (form.method || 'POST').toUpperCase(),
        body: new FormData(form),
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });
      const payload = await response.json().catch(function () { return {}; });
      if (!response.ok) throw new Error(payload.message || `Request failed (${response.status})`);
      const kind = payload.result && payload.result.mismatch ? 'warning' : 'success';
      show(kind, responseMessage(payload, form));
      const destination = form.getAttribute('data-vlan-redirect');
      if (destination) {
        window.location.assign(destination);
      } else if (form.hasAttribute('data-vlan-refresh')) {
        window.setTimeout(function () { window.location.reload(); }, 650);
      }
    } catch (error) {
      show('danger', 'VLAN operation failed', error.message || String(error));
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = original;
      }
    }
  }

  document.addEventListener('submit', function (event) {
    const form = event.target.closest('form[data-vlan-ajax]');
    if (!form) return;
    event.preventDefault();
    submitForm(form);
  });
}());
