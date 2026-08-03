(function () {
  'use strict';

  const root = document.querySelector('[data-device-workspace]');
  if (!root) return;

  const host = String(root.getAttribute('data-host') || '');
  const storageKey = `mobile-router:device-workspace:${host || window.location.pathname}`;
  const tabs = Array.from(root.querySelectorAll('[data-device-workspace-tab]'));
  const panels = Array.from(root.querySelectorAll('[data-device-workspace-panel]'));
  const select = root.querySelector('[data-device-workspace-select]');
  const dirtyForms = new Set();
  let activeName = 'overview';

  function panelFor(name) {
    return panels.find(function (panel) {
      return panel.getAttribute('data-device-workspace-panel') === name;
    }) || null;
  }

  function tabFor(name) {
    return tabs.find(function (tab) {
      return tab.getAttribute('data-device-workspace-tab') === name;
    }) || null;
  }

  function storedWorkspace() {
    try {
      return String(window.localStorage.getItem(storageKey) || '');
    } catch (error) {
      return '';
    }
  }

  function rememberWorkspace(name) {
    try {
      window.localStorage.setItem(storageKey, name);
    } catch (error) {
      // Navigation remains usable when browser storage is unavailable.
    }
  }

  function formSnapshot(form) {
    const entries = [];
    new FormData(form).forEach(function (value, key) {
      if (value instanceof File) {
        entries.push([key, value.name, value.size]);
      } else {
        entries.push([key, String(value)]);
      }
    });
    return JSON.stringify(entries);
  }

  function formPanel(form) {
    return form.closest('[data-device-workspace-panel]');
  }

  function updatePanelDirtyState(panel) {
    if (!panel) return;
    const name = panel.getAttribute('data-device-workspace-panel');
    const tab = tabFor(name);
    const hasDirty = Array.from(dirtyForms).some(function (form) {
      return formPanel(form) === panel;
    });
    panel.classList.toggle('has-unsaved-changes', hasDirty);
    if (tab) {
      tab.classList.toggle('is-dirty', hasDirty);
      tab.setAttribute('aria-label', `${tab.textContent.trim()}${hasDirty ? ', unsaved changes' : ''}`);
    }
  }

  function markFormState(form) {
    if (!form || form.hasAttribute('data-workspace-no-dirty')) return;
    if (!form.dataset.workspaceInitialState) {
      form.dataset.workspaceInitialState = formSnapshot(form);
    }
    const dirty = formSnapshot(form) !== form.dataset.workspaceInitialState;
    form.classList.toggle('is-dirty', dirty);
    const status = form.querySelector('[data-workspace-form-status]');
    if (status) status.textContent = dirty ? 'Unsaved changes' : 'Saved';
    if (dirty) dirtyForms.add(form);
    else dirtyForms.delete(form);
    updatePanelDirtyState(formPanel(form));
  }

  function registerForms(container) {
    const forms = Array.from(container.querySelectorAll('form[data-workspace-form]'));
    forms.forEach(function (form) {
      form.dataset.workspaceInitialState = formSnapshot(form);
      markFormState(form);
    });
  }

  async function loadPanel(panel) {
    if (!panel || panel.dataset.workspaceLoaded === 'true') return true;
    const url = panel.getAttribute('data-workspace-url');
    if (!url) {
      panel.dataset.workspaceLoaded = 'true';
      registerForms(panel);
      return true;
    }
    if (panel.dataset.workspaceLoading === 'true') return false;

    panel.dataset.workspaceLoading = 'true';
    panel.innerHTML = '<div class="device-workspace-loading"><div class="spinner-border text-primary" role="status" aria-hidden="true"></div><p>Loading workspace…</p></div>';
    try {
      const response = await fetch(url, {
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });
      if (!response.ok) throw new Error(`Workspace request failed (${response.status})`);
      panel.innerHTML = await response.text();
      panel.dataset.workspaceLoaded = 'true';
      registerForms(panel);
      document.dispatchEvent(new CustomEvent('device-workspace:loaded', {
        detail: { panel: panel },
      }));
      return true;
    } catch (error) {
      panel.innerHTML = `
        <div class="alert alert-danger" role="alert">
          <strong>Unable to load this workspace.</strong>
          <p class="mb-2">${String(error.message || error)}</p>
          <button type="button" class="btn btn-sm btn-outline-danger" data-workspace-retry>Retry</button>
        </div>`;
      panel.querySelector('[data-workspace-retry]').addEventListener('click', function () {
        panel.dataset.workspaceLoading = 'false';
        loadPanel(panel);
      });
      return false;
    } finally {
      panel.dataset.workspaceLoading = 'false';
    }
  }

  function canLeaveActive() {
    const activePanel = panelFor(activeName);
    if (!activePanel || !activePanel.classList.contains('has-unsaved-changes')) return true;
    return window.confirm('This workspace contains unsaved changes. Leave it without saving?');
  }

  async function activate(name, options) {
    const settings = Object.assign({ focus: false, updateHash: true, force: false }, options || {});
    const panel = panelFor(name);
    const tab = tabFor(name);
    if (!panel || !tab) return;
    if (!settings.force && name !== activeName && !canLeaveActive()) {
      if (select) select.value = activeName;
      return;
    }

    await loadPanel(panel);
    panels.forEach(function (candidate) {
      const active = candidate === panel;
      candidate.hidden = !active;
      candidate.classList.toggle('active', active);
    });
    tabs.forEach(function (candidate) {
      const active = candidate === tab;
      candidate.classList.toggle('active', active);
      candidate.setAttribute('aria-selected', active ? 'true' : 'false');
      candidate.setAttribute('tabindex', active ? '0' : '-1');
    });

    activeName = name;
    if (select) select.value = name;
    rememberWorkspace(name);
    if (settings.updateHash) window.history.replaceState(null, '', `#workspace-${name}`);
    if (settings.focus) panel.focus({ preventScroll: true });
    tab.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
  }

  tabs.forEach(function (tab) {
    tab.setAttribute('tabindex', tab.classList.contains('active') ? '0' : '-1');
    tab.addEventListener('click', function () {
      activate(tab.getAttribute('data-device-workspace-tab'), { focus: true });
    });
  });

  const tablist = root.querySelector('.device-workspace-tablist');
  if (tablist) {
    tablist.addEventListener('keydown', function (event) {
      const index = tabs.indexOf(tabFor(activeName));
      let nextIndex = null;
      if (event.key === 'ArrowRight' || event.key === 'ArrowDown') nextIndex = (index + 1) % tabs.length;
      else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') nextIndex = (index - 1 + tabs.length) % tabs.length;
      else if (event.key === 'Home') nextIndex = 0;
      else if (event.key === 'End') nextIndex = tabs.length - 1;
      if (nextIndex === null) return;
      event.preventDefault();
      const name = tabs[nextIndex].getAttribute('data-device-workspace-tab');
      activate(name).then(function () { tabs[nextIndex].focus(); });
    });
  }

  if (select) {
    select.addEventListener('change', function () {
      activate(select.value, { focus: true });
    });
  }

  root.addEventListener('click', function (event) {
    const trigger = event.target.closest('[data-workspace-open]');
    if (!trigger) return;
    event.preventDefault();
    activate(trigger.getAttribute('data-workspace-open'), { focus: true });
  });

  root.addEventListener('input', function (event) {
    const form = event.target.closest('form[data-workspace-form]');
    if (form) markFormState(form);
  });
  root.addEventListener('change', function (event) {
    const form = event.target.closest('form[data-workspace-form]');
    if (form) markFormState(form);
  });

  document.addEventListener('device-workspace:form-saved', function (event) {
    const form = event.detail && event.detail.form;
    if (!form) return;
    form.dataset.workspaceInitialState = formSnapshot(form);
    markFormState(form);
  });

  window.addEventListener('beforeunload', function (event) {
    if (!dirtyForms.size) return;
    event.preventDefault();
    event.returnValue = '';
  });

  window.addEventListener('hashchange', function () {
    const match = window.location.hash.match(/^#workspace-(overview|identity|network|services|security|history)$/);
    if (match) activate(match[1], { updateHash: false, force: true });
  });

  registerForms(root);
  const hashMatch = window.location.hash.match(/^#workspace-(overview|identity|network|services|security|history)$/);
  const initial = hashMatch ? hashMatch[1] : (storedWorkspace() || 'overview');
  activate(panelFor(initial) ? initial : 'overview', { updateHash: false, force: true });
}());
