document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('setup-wizard-form');
  if (!form) {
    return;
  }

  const csrfToken = form.dataset.csrfToken || '';
  const submitButton = document.getElementById('install-selected-components');
  const finishAnywayButton = document.getElementById('finish-setup-anyway');
  const progressPanel = document.getElementById('setup-install-progress');
  const progressFill = document.getElementById('setup-progress-fill');
  const progressLabel = document.getElementById('setup-progress-label');
  const warning = document.getElementById('setup-install-warning');

  function setBusy(isBusy) {
    submitButton.disabled = isBusy;
    form.querySelectorAll('input[name="components"]').forEach(function (input) {
      if (!input.closest('.is-installed')) {
        input.disabled = isBusy || input.dataset.permanentlyDisabled === 'true';
      }
    });
  }

  function updateCard(componentId, success, message) {
    const card = form.querySelector(`[data-setup-component="${CSS.escape(componentId)}"]`);
    if (!card) {
      return;
    }
    const result = card.querySelector('[data-component-result]');
    const status = card.querySelector('[data-component-status]');
    result.textContent = message;
    result.classList.toggle('is-success', success);
    result.classList.toggle('is-error', !success);
    status.textContent = success ? 'Installed' : 'Install failed';
    status.classList.toggle('is-success', success);
    status.classList.toggle('is-error', !success);
    if (success) {
      card.classList.add('is-installed');
      const checkbox = card.querySelector('input[name="components"]');
      if (checkbox) {
        checkbox.checked = false;
        checkbox.disabled = true;
        checkbox.dataset.permanentlyDisabled = 'true';
      }
    }
  }

  async function postForm(url, fields) {
    const body = new URLSearchParams({csrf_token: csrfToken, ...fields});
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: body.toString()
    });
    let payload = {};
    try {
      payload = await response.json();
    } catch (error) {
      payload = {error: 'The server returned an unreadable response.'};
    }
    if (!response.ok) {
      throw new Error(payload.error || payload.message || 'Installation failed.');
    }
    return payload;
  }

  async function finishSetup() {
    progressLabel.textContent = 'Saving setup choices…';
    const response = await postForm('/setup-wizard/complete', {mode: 'completed'});
    window.location.assign(response.redirect || '/');
  }

  form.addEventListener('submit', async function (event) {
    event.preventDefault();
    const selected = Array.from(
      form.querySelectorAll('input[name="components"]:checked:not(:disabled)')
    ).map(function (input) { return input.value; });

    progressPanel.hidden = false;
    warning.hidden = true;
    finishAnywayButton.hidden = true;
    setBusy(true);

    if (!selected.length) {
      try {
        await finishSetup();
      } catch (error) {
        progressLabel.textContent = error.message;
        warning.hidden = false;
        setBusy(false);
      }
      return;
    }

    let failures = 0;
    for (let index = 0; index < selected.length; index += 1) {
      const componentId = selected[index];
      const card = form.querySelector(`[data-setup-component="${CSS.escape(componentId)}"]`);
      const componentName = card && card.querySelector('h2')
        ? card.querySelector('h2').textContent.trim()
        : componentId;
      progressLabel.textContent = `Installing ${componentName} (${index + 1} of ${selected.length})…`;
      progressFill.style.width = `${Math.round((index / selected.length) * 100)}%`;

      try {
        const response = await postForm('/setup-wizard/install', {component: componentId});
        const result = response.result || {};
        updateCard(componentId, true, result.message || `${componentName} installed.`);
      } catch (error) {
        failures += 1;
        updateCard(componentId, false, error.message);
      }
    }

    progressFill.style.width = '100%';
    if (failures) {
      progressLabel.textContent = `${selected.length - failures} installed, ${failures} failed.`;
      warning.hidden = false;
      finishAnywayButton.hidden = false;
      setBusy(false);
      return;
    }

    try {
      await finishSetup();
    } catch (error) {
      progressLabel.textContent = error.message;
      warning.hidden = false;
      finishAnywayButton.hidden = false;
      setBusy(false);
    }
  });

  finishAnywayButton.addEventListener('click', async function () {
    finishAnywayButton.disabled = true;
    try {
      await finishSetup();
    } catch (error) {
      progressLabel.textContent = error.message;
      finishAnywayButton.disabled = false;
    }
  });

  form.querySelectorAll('input[name="components"]:disabled').forEach(function (input) {
    input.dataset.permanentlyDisabled = 'true';
  });
});
