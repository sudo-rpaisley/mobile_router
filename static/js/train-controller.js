(function () {
  const state = window.trainControllerState;
  const status = document.getElementById('train-status');
  const scanOutput = document.getElementById('train-scan-job');
  const stepOrder = ['add_controller', 'setup', 'add_engine', 'lights', 'throttle'];

  function message(text, kind) {
    status.textContent = text;
    status.className = `alert alert-${kind || 'info'}`;
  }

  async function api(url, method, body) {
    message('Working…', 'info');
    const response = await fetch(url, {
      method,
      headers: {'Content-Type': 'application/json'},
      body: body ? JSON.stringify(body) : undefined
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.message || 'Request failed');
    message('Completed successfully.', 'success');
    return result;
  }

  async function refresh(task) {
    try {
      await task();
      window.location.reload();
    } catch (error) {
      message(error.message, 'danger');
    }
  }

  function authorized() {
    return window.confirm('Confirm that you are authorized to control this model railway hardware.');
  }

  function formBody(form) {
    return Object.fromEntries(new FormData(form));
  }

  document.querySelectorAll('.mode-button').forEach(button => button.addEventListener('click', () =>
    refresh(() => api('/api/train-controller/mode', 'POST', {mode: button.dataset.mode}))
  ));
  document.getElementById('layout-name-form').addEventListener('submit', event => {
    event.preventDefault();
    refresh(() => api('/api/train-controller/layout', 'PUT', formBody(event.target)));
  });
  document.getElementById('add-controller-form').addEventListener('submit', event => {
    event.preventDefault();
    refresh(() => api('/api/train-controller/controllers', 'POST', formBody(event.target)));
  });
  document.querySelectorAll('.edit-controller-form').forEach(form => form.addEventListener('submit', event => {
    event.preventDefault();
    refresh(() => api(`/api/train-controller/controllers/${form.dataset.controller}`, 'PUT', formBody(form)));
  }));
  document.querySelectorAll('.add-engine-form').forEach(form => form.addEventListener('submit', event => {
    event.preventDefault();
    refresh(() => api(`/api/train-controller/controllers/${form.dataset.controller}/engines`, 'POST', formBody(form)));
  }));
  document.querySelectorAll('.edit-engine-form').forEach(form => form.addEventListener('submit', event => {
    event.preventDefault();
    refresh(() => api(`/api/train-controller/controllers/${form.dataset.controller}/engines/${form.dataset.engine}`, 'PUT', formBody(form)));
  }));
  document.querySelectorAll('.delete-controller').forEach(button => button.addEventListener('click', () => {
    if (window.confirm('Delete this controller and its engine roster?')) {
      refresh(() => api(`/api/train-controller/controllers/${button.dataset.controller}`, 'DELETE'));
    }
  }));
  document.querySelectorAll('.delete-engine').forEach(button => button.addEventListener('click', () =>
    refresh(() => api(`/api/train-controller/controllers/${button.dataset.controller}/engines/${button.dataset.engine}`, 'DELETE'))
  ));
  document.querySelectorAll('.train-action').forEach(button => button.addEventListener('click', () => {
    if (!authorized()) return;
    refresh(() => api(`/api/train-controller/controllers/${button.dataset.controller}/actions`, 'POST', {
      action: button.dataset.action, engine_id: button.dataset.engine, authorized: true
    }));
  }));
  document.querySelectorAll('.train-speed').forEach(slider => {
    slider.addEventListener('input', () => {
      document.getElementById(`speed-output-${slider.dataset.engine}`).value = slider.value;
    });
    slider.addEventListener('change', () => {
      if (!authorized()) { slider.value = 0; return; }
      refresh(() => api(`/api/train-controller/controllers/${slider.dataset.controller}/actions`, 'POST', {
        action: 'throttle', engine_id: slider.dataset.engine, speed: slider.value, authorized: true
      }));
    });
  });

  document.querySelectorAll('.train-controller-panel').forEach(panel => {
    const key = `train-controller-collapsed-${panel.dataset.controller}`;
    panel.open = window.localStorage.getItem(key) !== 'true';
    panel.addEventListener('toggle', () => window.localStorage.setItem(key, String(!panel.open)));
  });

  async function pollScan(jobId, controllerId) {
    const result = await api(`/api/train-controller/scan-jobs/${jobId}`, 'GET');
    const job = result.job;
    scanOutput.innerHTML = `<div class="progress"><div class="progress-bar" style="width:${job.progress}%">${job.progress}%</div></div><p>Checked ${job.current} of ${job.maximum}; found ${job.engines.length}.</p>`;
    if (['queued', 'running'].includes(job.status)) {
      const cancel = document.createElement('button');
      cancel.className = 'btn btn-sm btn-outline-danger';
      cancel.textContent = 'Cancel scan';
      cancel.addEventListener('click', () => api(`/api/train-controller/scan-jobs/${jobId}/cancel`, 'POST'));
      scanOutput.appendChild(cancel);
      window.setTimeout(() => pollScan(jobId, controllerId), 500);
    } else if (job.status === 'completed') {
      if (!job.engines.length) {
        scanOutput.insertAdjacentHTML('beforeend', '<div class="alert alert-info">No active engines were found.</div>');
        return;
      }
      const importButton = document.createElement('button');
      importButton.className = 'btn btn-success';
      importButton.textContent = 'Import selected engines';
      const choices = document.createElement('div');
      choices.className = 'train-engine-choices';
      job.engines.forEach(address => {
        const label = document.createElement('label');
        label.innerHTML = `<input type="checkbox" value="${address}" checked> Address ${address}`;
        choices.appendChild(label);
      });
      scanOutput.appendChild(choices);
      importButton.addEventListener('click', () => {
        const addresses = Array.from(choices.querySelectorAll('input:checked')).map(input => Number(input.value));
        if (!addresses.length) { message('Select at least one discovered engine.', 'warning'); return; }
        refresh(() => api(`/api/train-controller/controllers/${controllerId}/engines/import`, 'POST', {addresses}));
      });
      scanOutput.appendChild(importButton);
    } else {
      message(job.error || `Scan ${job.status}.`, job.status === 'cancelled' ? 'warning' : 'danger');
    }
  }

  document.querySelectorAll('.train-scan').forEach(button => button.addEventListener('click', async () => {
    if (!authorized()) return;
    try {
      const maximum = document.getElementById(`scan-max-${button.dataset.controller}`).value;
      const result = await api(`/api/train-controller/controllers/${button.dataset.controller}/scan-jobs`, 'POST', {maximum, authorized: true});
      pollScan(result.job.id, button.dataset.controller);
    } catch (error) {
      message(error.message, 'danger');
    }
  }));

  document.getElementById('save-train-evidence').addEventListener('click', () =>
    refresh(() => api('/api/train-controller/evidence', 'POST', {}))
  );

  if (state.mode === 'training') {
    const current = stepOrder.find(step => !state.training.completed.includes(step));
    document.body.classList.add('train-training-mode');
    document.querySelectorAll('.train-action,.train-speed,.train-scan').forEach(control => {
      if (!['emergency_stop', 'stop'].includes(control.dataset.action)) control.disabled = true;
    });
    document.querySelectorAll('[data-training-step]').forEach(control => {
      if (control.dataset.trainingStep !== current) {
        control.classList.add('training-locked');
        control.querySelectorAll('button,input').forEach(item => { item.disabled = true; });
        if (control.matches('button,input')) control.disabled = true;
      } else {
        control.classList.add('training-spotlight');
        if (window.trainControllerCapability.available || ['add_controller', 'add_engine'].includes(current)) {
          control.querySelectorAll('button,input').forEach(item => { item.disabled = false; });
          if (control.matches('button,input')) control.disabled = false;
        }
      }
    });
  }
}());
