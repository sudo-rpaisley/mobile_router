let layoutId = null;
let layoutName = '';
// Map controllerId -> array of engine objects
let engines = {};
let controllers = [];
let scrambleInterval = null;
let speedLockIntervals = {};

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) {
    alert(message);
    return;
  }
  const toast = document.createElement('div');
  toast.className = 'toast ' + type;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.add('hide');
    toast.addEventListener('transitionend', () => toast.remove());
  }, 3000);
}

function postJSON(url, data) {
  return fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
}

function applyTheme(theme) {
  document.body.classList.toggle('dark', theme === 'dark');
  const toggle = document.getElementById('theme-toggle');
  if (toggle) toggle.checked = theme === 'dark';
}

function toggleTheme() {
  const newTheme = document.body.classList.contains('dark') ? 'light' : 'dark';
  localStorage.setItem('theme', newTheme);
  applyTheme(newTheme);
}

document.addEventListener('DOMContentLoaded', () => {
  applyTheme(localStorage.getItem('theme') || 'light');
});

function saveIP(id) {
  const ip = document.getElementById('ip-' + id).value;
  return postJSON('/set-ip', { id, ip });
}


function saveControllerName(id) {
  const name = document.getElementById('controller-name-' + id).value;
  return postJSON('/set-controller-name', { id, name });
}

function toggleEditController(id) {
  const nameInput = document.getElementById('controller-name-' + id);
  const nameSpan = document.getElementById('controller-display-' + id);
  const ipInput = document.getElementById('ip-' + id);
  const ipSpan = document.getElementById('ip-display-' + id);
  const btn = document.getElementById('edit-controller-' + id);
  const delBtn = document.getElementById('delete-controller-' + id);
  if (!nameInput.dataset.editing) {
    nameInput.dataset.editing = 'true';
    ipInput.dataset.editing = 'true';
    nameInput.style.display = 'inline-block';
    nameSpan.style.display = 'none';
    ipInput.removeAttribute('readonly');
    ipInput.classList.add('editing');
    ipInput.style.display = 'inline-block';
    if (ipSpan) ipSpan.style.display = 'none';
    btn.classList.add('save');
    btn.textContent = '🖫';
    btn.title = 'Save Controller';
    if (delBtn) delBtn.style.display = 'inline-block';
    nameInput.focus();
  } else {
    const newName = nameInput.value.trim();
    const newIp = ipInput.value.trim();
    nameSpan.textContent = newName || 'Controller';
    if (ipSpan) ipSpan.textContent = newIp;
    nameInput.removeAttribute('data-editing');
    ipInput.removeAttribute('data-editing');
    nameInput.style.display = 'none';
    nameSpan.style.display = 'inline-block';
    ipInput.setAttribute('readonly', true);
    ipInput.classList.remove('editing');
    ipInput.style.display = 'none';
    if (ipSpan) ipSpan.style.display = 'inline-block';
    btn.classList.remove('save');
    btn.textContent = '🖉';
    btn.title = 'Edit Controller';
    if (delBtn) delBtn.style.display = 'none';
    Promise.all([saveControllerName(id), saveIP(id)])
      .then(() => showToast('Controller Saved', 'success'));
  }
}

function saveLayoutName() {
  const name = document.getElementById('layout-name-input').value.trim();
  postJSON('/set-layout-name', { name }).then(() => {
    layoutName = name;
    showToast('Layout Saved', 'success');
  });
}

function toggleEditLayoutName() {
  const input = document.getElementById('layout-name-input');
  const span = document.getElementById('layout-name-display');
  const btn = document.getElementById('edit-layout-name');
  if (!input.dataset.editing) {
    input.dataset.editing = 'true';
    input.style.display = 'inline-block';
    span.style.display = 'none';
    btn.classList.add('save');
    btn.textContent = '🖫';
    btn.title = 'Save Name';
    input.focus();
  } else {
    span.textContent = input.value.trim();
    input.removeAttribute('data-editing');
    input.style.display = 'none';
    span.style.display = 'inline-block';
    btn.classList.remove('save');
    btn.textContent = '🖉';
    btn.title = 'Edit Layout Name';
    saveLayoutName();
  }
}

function addController() {
  const ip = document.getElementById('ip').value.trim();
  const name = document.getElementById('name').value.trim();
  postJSON('/add-controller', { ip, name }).then(res => {
    if (!res.ok) {
      return res.text().then(t => showToast(t, 'error'));
    }
    location.reload();
  });
}

function performDeleteController(id) {
  hideConfirm();
  postJSON('/delete-controller', { id }).then(() => location.reload());
}

function confirmDeleteController(id) {
  const overlay = document.getElementById('confirm-overlay');
  const btn = document.getElementById('confirm-delete-btn');
  btn.onclick = () => performDeleteController(id);
  overlay.classList.add('show');
}

function hideConfirm() {
  document.getElementById('confirm-overlay').classList.remove('show');
}

function initController(ip) {
  const setupCommands = ['<1>', '<1 MAIN>', '<1 PROG>', '<1 JOIN>'];
  setupCommands.forEach(cmd => sendCmd(ip, cmd));
}

function scanEngines(ip, id) {
  const scanBtn = document.querySelector(`#controller-${id} button[data-action=scan]`);
  const oldText = scanBtn.textContent;
  const oldClass = scanBtn.className;

  scanBtn.disabled = true;
  scanBtn.textContent = 'Scanning...';

  fetch('/scan-engines?ip=' + encodeURIComponent(ip))
    .then(res => {
      if (!res.ok) throw new Error('Scan failed');
      return res.json();
    })
    .then(data => {
      const list = data.engines.map(eId => ({ id: eId.toString() }));
      engines[id] = list;
      renderEngines(id, ip);
    })
    .catch(() => {
      scanBtn.classList.add('red');
      scanBtn.textContent = 'Scan Failed';
    })
    .finally(() => {
      setTimeout(() => {
        scanBtn.disabled = false;
        scanBtn.textContent = oldText;
        scanBtn.className = oldClass;
      }, 1500);
    });
}

function sendCmd(ip, cmd) {
  postJSON('/send', { cmd, ip });
}

function sendThrottle(ip, id, rawSpeed) {
  const speed = Math.abs(parseInt(rawSpeed, 10));
  const dir = rawSpeed >= 0 ? 1 : 0;
  sendCmd(ip, `<t ${id} ${speed} ${dir}>`);
}

function updateThrottle(slider, ip, id) {
  const value = parseInt(slider.value, 10);
  const out = slider.nextElementSibling;
  if (out) out.textContent = value;
  sendThrottle(ip, id, value);
}

function renderEngines(id, ip) {
  const container = document.getElementById('controls-' + id);
  container.innerHTML = '';
  const list = engines[id] || [];
  list.forEach(e => {
    const div = document.createElement('div');
    div.className = 'engine';
    if (e.editing) div.classList.add('editing');

    const editBtn = document.createElement('button');
    editBtn.className = 'edit-engine-btn' + (e.editing ? ' save' : '');
    editBtn.textContent = e.editing ? '🖫' : '🖉';
    editBtn.title = e.editing ? 'Save Engine' : 'Edit Engine';
    editBtn.onclick = () => toggleEditEngine(e.id, id, ip);
    div.appendChild(editBtn);

    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'delete-engine-btn';
    deleteBtn.textContent = 'Delete';
    deleteBtn.title = 'Delete Engine';
    deleteBtn.onclick = () => deleteEngine(e.id, id, ip);
    div.appendChild(deleteBtn);

    const title = document.createElement('h3');
    title.className = 'engine-title';
    const nameSpan = document.createElement('span');
    nameSpan.id = `engine-display-${id}-${e.id}`;
    nameSpan.textContent = e.name || 'Engine';
    const nameInput = document.createElement('input');
    nameInput.type = 'text';
    nameInput.placeholder = 'Name (optional)';
    nameInput.value = e.name || '';
    nameInput.id = `engine-name-${id}-${e.id}`;
    nameInput.className = 'engine-name-input';

    const addr = document.createElement('p');
    addr.className = 'engine-address';
    addr.id = `engine-id-display-${id}-${e.id}`;
    addr.textContent = 'Address: ' + e.id;
    const addrInput = document.createElement('input');
    addrInput.type = 'text';
    addrInput.value = e.id;
    addrInput.placeholder = 'Address';
    addrInput.id = `engine-id-${id}-${e.id}`;
    addrInput.className = 'engine-id-input';

    if (e.editing) {
      nameSpan.style.display = 'none';
      addr.style.display = 'none';
    } else {
      nameInput.style.display = 'none';
      addrInput.style.display = 'none';
    }

    title.appendChild(nameSpan);
    title.appendChild(nameInput);
    div.appendChild(title);
    div.appendChild(addr);
    div.appendChild(addrInput);

    const speedGroup = document.createElement('div');
    speedGroup.className = 'speed-group';

    const labelWrap = document.createElement('div');
    labelWrap.className = 'slider-labels';
    labelWrap.innerHTML = '<span>-127</span><span>0</span><span>127</span>';
    speedGroup.appendChild(labelWrap);

    const row = document.createElement('div');
    row.className = 'slider-row';

    const slider = document.createElement('input');
    slider.type = 'range';
    slider.min = '-127';
    slider.max = '127';
    slider.value = '0';
    slider.className = 'slider';
    slider.setAttribute('list', 'speedmarks');
    slider.addEventListener('input', () => updateThrottle(slider, ip, e.id));
    row.appendChild(slider);

    const speedSpan = document.createElement('span');
    speedSpan.className = 'speed-value';
    speedSpan.textContent = '0';
    row.appendChild(speedSpan);

    speedGroup.appendChild(row);
    div.appendChild(speedGroup);

    const lightsBtn = document.createElement('button');
    lightsBtn.className = 'btn';
    lightsBtn.textContent = 'Lights';
    lightsBtn.onclick = () => sendCmd(ip, `<f ${e.id} 0 1>`);
    div.appendChild(lightsBtn);

    const hornBtn = document.createElement('button');
    hornBtn.className = 'btn';
    hornBtn.textContent = 'Horn';
    hornBtn.onclick = () => sendCmd(ip, `<f ${e.id} 1 1>`);
    div.appendChild(hornBtn);

    const stopBtn = document.createElement('button');
    stopBtn.className = 'btn red';
    stopBtn.textContent = 'Stop';
    stopBtn.onclick = () => {
      slider.value = '0';
      updateThrottle(slider, ip, e.id);
    };
    div.appendChild(stopBtn);


    const redTeamDetails = document.createElement('details');
    redTeamDetails.className = 'red-team';
    const summary = document.createElement('summary');
    summary.textContent = 'Red Team';
    redTeamDetails.appendChild(summary);
    const redTeamDiv = document.createElement('div');
    redTeamDiv.className = 'red-team-buttons';

    const attacks = [
      { label: 'Scramble Attack', func: 'attackScrambleToggle(this)' },
      { label: 'Turbo Blast', func: 'attackTurboBlast()' },
      { label: 'Slow Creep', func: 'attackSlowCreep()' },
      { label: 'Ghost Drift', func: 'attackGhostDrift()' },
      { label: 'Rollercoaster', func: 'attackRollercoaster()' },
      { label: 'Jitter Bug', func: 'attackJitterBug()' },
      { label: 'Reverse Slam', func: 'attackReverseSlam()' },
      { label: 'Ping-Pong Attack', func: 'attackPingPong()' },
      { label: 'Emergency Flood', func: 'attackEmergencyFlood()' }
    ];

    attacks.forEach(a => {
      const btn = document.createElement('button');
      btn.textContent = a.label;
      btn.className = 'btn';
      btn.setAttribute('onclick', a.func);
      redTeamDiv.appendChild(btn);
    });

    redTeamDetails.appendChild(redTeamDiv);
    div.appendChild(redTeamDetails);
    container.appendChild(div);
  });
}


function toggleEditEngine(id, controllerId, ip) {
  const list = engines[controllerId] || [];
  const engine = list.find(e => e.id.toString() === id.toString());
  if (!engine) return;
  if (!engine.editing) {
    engine.editing = true;
  } else {
    const nameInput = document.getElementById(`engine-name-${controllerId}-${id}`);
    const idInput = document.getElementById(`engine-id-${controllerId}-${id}`);
    const newName = nameInput ? nameInput.value.trim() : engine.name;
    const newId = idInput ? idInput.value.trim() : engine.id;
    engine.name = newName;
    engine.id = newId;
    delete engine.editing;
    postJSON('/update-engine', {
      controllerId,
      engineId: id,
      name: newName,
      newId
    })
      .then(res => {
        if (!res.ok) return res.text().then(t => Promise.reject(t));
      })
      .then(() => showToast('Engine Saved', 'success'))
      .catch(err => showToast(err, 'error'));
  }
  renderEngines(controllerId, ip);
}

function deleteEngine(id, controllerId, ip) {
  postJSON('/delete-engine', { controllerId, engineId: id }).then(() => {
    engines[controllerId] = (engines[controllerId] || []).filter(
      e => e.id.toString() !== id.toString()
    );
    renderEngines(controllerId, ip);
  });
}

function toggleAddEngine(controllerId) {
  const form = document.getElementById('manual-add-form-' + controllerId);
  form.style.display = form.style.display === 'flex' ? 'none' : 'flex';
}

function toggleController(controllerId) {
  const btn = document.getElementById('collapse-' + controllerId);
  const controls = document.getElementById('controls-' + controllerId);
  const form = document.getElementById('manual-add-form-' + controllerId);
  const collapsed = btn.dataset.collapsed === 'true';
  if (collapsed) {
    btn.dataset.collapsed = 'false';
    btn.textContent = '▼';
    if (controls) controls.style.display = '';
  } else {
    btn.dataset.collapsed = 'true';
    btn.textContent = '►';
    if (controls) controls.style.display = 'none';
    if (form) form.style.display = 'none';
  }
  localStorage.setItem(
    'collapsed-' + layoutId + '-' + controllerId,
    btn.dataset.collapsed
  );
}

function applyCollapsedState(controllerId) {
  const collapsed =
    localStorage.getItem('collapsed-' + layoutId + '-' + controllerId) === 'true';
  const btn = document.getElementById('collapse-' + controllerId);
  const controls = document.getElementById('controls-' + controllerId);
  const form = document.getElementById('manual-add-form-' + controllerId);
  if (btn) {
    btn.dataset.collapsed = collapsed ? 'true' : 'false';
    btn.textContent = collapsed ? '►' : '▼';
  }
  if (controls) controls.style.display = collapsed ? 'none' : '';
  if (form && collapsed) form.style.display = 'none';
}

function confirmAddEngine(controllerId) {
  const id = document.getElementById('manual-id-' + controllerId).value.trim();
  const name = document.getElementById('manual-name-' + controllerId).value.trim();
  if (!id) return showToast('Engine address is required', 'error');
  const list = engines[controllerId] || [];
  if (list.some(e => e.id.toString() === id.toString())) {
    return showToast('Engine with this ID already exists', 'error');
  }
  const engine = { id, name };
  postJSON('/add-engine', { controllerId, engineId: id, name })
    .then(res => {
      if (!res.ok) return res.text().then(t => Promise.reject(t));
    })
    .then(() => {
      engines[controllerId] = [...list, engine];
      const ip = controllers.find(c => c.id === controllerId).ip;
      renderEngines(controllerId, ip);
      const form = document.getElementById('manual-add-form-' + controllerId);
      form.style.display = 'none';
      document.getElementById('manual-id-' + controllerId).value = '';
      document.getElementById('manual-name-' + controllerId).value = '';
    })
    .catch(err => showToast(err, 'error'));
}

fetch('/get-config')
  .then(res => res.json())
  .then(data => {
    controllers = data.controllers || [];
    layoutId = data.layoutId;
    layoutName = data.layoutName || '';
    const span = document.getElementById('layout-name-display');
    const input = document.getElementById('layout-name-input');
    if (span) span.textContent = layoutName;
    if (input) input.value = layoutName;
    controllers.forEach(c => {
      engines[c.id] = c.engines || [];
      renderEngines(c.id, c.ip);
      applyCollapsedState(c.id);
    });
  });
