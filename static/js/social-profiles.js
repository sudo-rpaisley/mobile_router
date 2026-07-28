(function () {
  'use strict';
  var vaultPassword = null;
  var lockTimer = null;
  var encoder = new TextEncoder();
  var decoder = new TextDecoder();

  function bytesToBase64(bytes) {
    var binary = '';
    bytes.forEach(function (value) { binary += String.fromCharCode(value); });
    return btoa(binary);
  }

  function base64ToBytes(value) {
    var binary = atob(value);
    return Uint8Array.from(binary, function (character) { return character.charCodeAt(0); });
  }

  async function deriveKey(password, salt, usage) {
    var material = await crypto.subtle.importKey('raw', encoder.encode(password), 'PBKDF2', false, ['deriveKey']);
    return crypto.subtle.deriveKey(
      { name: 'PBKDF2', salt: salt, iterations: 310000, hash: 'SHA-256' }, material,
      { name: 'AES-GCM', length: 256 }, false, usage
    );
  }

  async function encryptSecret(secret, password) {
    var salt = crypto.getRandomValues(new Uint8Array(16));
    var iv = crypto.getRandomValues(new Uint8Array(12));
    var key = await deriveKey(password, salt, ['encrypt']);
    var encrypted = await crypto.subtle.encrypt({ name: 'AES-GCM', iv: iv }, key, encoder.encode(secret));
    return 'vault:v1:' + bytesToBase64(salt) + ':' + bytesToBase64(iv) + ':' + bytesToBase64(new Uint8Array(encrypted));
  }

  async function decryptSecret(payload, password) {
    var parts = payload.split(':');
    if (parts.length !== 5 || parts[0] !== 'vault' || parts[1] !== 'v1') throw new Error('Unsupported encrypted secret.');
    var salt = base64ToBytes(parts[2]);
    var iv = base64ToBytes(parts[3]);
    var ciphertext = base64ToBytes(parts[4]);
    var key = await deriveKey(password, salt, ['decrypt']);
    return decoder.decode(await crypto.subtle.decrypt({ name: 'AES-GCM', iv: iv }, key, ciphertext));
  }

  function setVaultStatus(unlocked) {
    var status = document.getElementById('vault-status');
    if (!status) return;
    status.textContent = unlocked ? 'Unlocked' : 'Locked';
    status.className = 'badge ' + (unlocked ? 'badge-success' : 'badge-secondary');
  }

  function audit(action) {
    var config = window.socialProfileSecurity;
    if (!config) return;
    var body = new URLSearchParams({ action: action, csrf_token: config.csrfToken });
    fetch('/social-engineering/profiles/' + encodeURIComponent(config.profileId) + '/audit', {
      method: 'POST', body: body, headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    });
  }

  function lockVault() {
    vaultPassword = null;
    clearTimeout(lockTimer);
    document.querySelectorAll('.credential-secret').forEach(function (secret) { secret.textContent = '••••••••'; });
    document.querySelectorAll('.credential-reveal').forEach(function (button) {
      button.setAttribute('aria-pressed', 'false');
      button.setAttribute('aria-label', 'Reveal secret');
      button.querySelector('i').className = 'fas fa-eye';
    });
    setVaultStatus(false);
  }

  async function unlockVault() {
    if (!window.crypto || !window.crypto.subtle) {
      window.alert('Credential encryption requires localhost or an HTTPS connection.');
      return false;
    }
    var password = window.prompt('Enter the credential vault master password:');
    if (!password) return false;
    var config = window.socialProfileSecurity || {};
    if (config.vaultVerifier) {
      try {
        var verified = await decryptSecret(config.vaultVerifier, password);
        if (verified !== 'mobile-router-vault-verifier-v1') throw new Error('Verifier mismatch');
      } catch (error) {
        window.alert('Incorrect vault master password.');
        return false;
      }
    } else {
      var confirmation = window.prompt('Confirm the new vault master password:');
      if (confirmation !== password) {
        window.alert('The vault passwords did not match.');
        return false;
      }
      try {
        var verifier = await encryptSecret('mobile-router-vault-verifier-v1', password);
        var response = await fetch('/vault-verifier', {
          method: 'POST',
          body: new URLSearchParams({ vault_verifier: verifier, csrf_token: config.csrfToken }),
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
        });
        if (!response.ok) throw new Error('Unable to save vault verifier.');
        config.vaultVerifier = verifier;
      } catch (error) {
        window.alert(error.message);
        return false;
      }
    }
    vaultPassword = password;
    clearTimeout(lockTimer);
    lockTimer = setTimeout(lockVault, 5 * 60 * 1000);
    setVaultStatus(true);
    audit('vault.unlock');
    return true;
  }

  document.getElementById('vault-unlock')?.addEventListener('click', function () { unlockVault(); });
  document.getElementById('vault-lock')?.addEventListener('click', lockVault);
  document.getElementById('vault-rotate')?.addEventListener('click', async function () {
    if (!vaultPassword && !(await unlockVault())) return;
    var oldPassword = vaultPassword;
    var newPassword = window.prompt('Enter a new vault master password (12 characters minimum):');
    if (!newPassword || newPassword.length < 12) { window.alert('Use at least 12 characters.'); return; }
    if (window.prompt('Confirm the new vault master password:') !== newPassword) { window.alert('The new passwords did not match.'); return; }
    var replacements = {};
    try {
      var encryptedSecrets = window.socialProfileSecurity.vaultCredentials || [];
      for (var index = 0; index < encryptedSecrets.length; index += 1) {
        var item = encryptedSecrets[index];
        var plaintext = await decryptSecret(item.ciphertext, oldPassword);
        replacements[item.id] = await encryptSecret(plaintext, newPassword);
      }
      var verifier = await encryptSecret('mobile-router-vault-verifier-v1', newPassword);
      var backup = { version: 1, createdAt: new Date().toISOString(), verifier: window.socialProfileSecurity.vaultVerifier,
        credentials: Object.fromEntries(encryptedSecrets.map(function (item) { return [item.id, item.ciphertext]; })) };
      var link = document.createElement('a');
      link.href = URL.createObjectURL(new Blob([JSON.stringify(backup, null, 2)], { type: 'application/json' }));
      link.download = 'mobile-router-vault-recovery-' + new Date().toISOString().slice(0, 10) + '.json';
      link.click(); URL.revokeObjectURL(link.href);
      var response = await fetch('/vault-rotate', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ csrf_token: window.socialProfileSecurity.csrfToken, vault_verifier: verifier, credentials: JSON.stringify(replacements) }) });
      if (!response.ok) throw new Error((await response.json()).message || 'Unable to rotate vault.');
      document.querySelectorAll('.credential-secret[data-credential-id]').forEach(function (item) { if (replacements[item.dataset.credentialId]) item.dataset.ciphertext = replacements[item.dataset.credentialId]; });
      window.socialProfileSecurity.vaultCredentials = encryptedSecrets.map(function (item) { return { id: item.id, ciphertext: replacements[item.id] }; });
      window.socialProfileSecurity.vaultVerifier = verifier; vaultPassword = newPassword;
      window.alert('Vault master password changed. An encrypted recovery backup was downloaded.');
    } catch (error) { window.alert('Vault rotation failed: ' + error.message); }
  });
  document.getElementById('vault-restore')?.addEventListener('click', function () { document.getElementById('vault-backup-file').click(); });
  document.getElementById('vault-backup-file')?.addEventListener('change', async function (event) {
    var file = event.target.files[0];
    if (!file || !window.confirm('Restore this encrypted vault backup? Current encrypted secrets will be replaced.')) return;
    try {
      var backup = JSON.parse(await file.text());
      if (backup.version !== 1 || !backup.verifier || !backup.credentials) throw new Error('Unsupported backup file.');
      var response = await fetch('/vault-rotate', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ csrf_token: window.socialProfileSecurity.csrfToken, vault_verifier: backup.verifier, credentials: JSON.stringify(backup.credentials) }) });
      if (!response.ok) throw new Error((await response.json()).message || 'Unable to restore backup.');
      window.alert('Encrypted vault backup restored. Reloading now.'); window.location.reload();
    } catch (error) { window.alert('Vault restore failed: ' + error.message); }
  });
  document.querySelectorAll('[data-add-device-password]').forEach(function (button) {
    button.addEventListener('click', function () {
      document.getElementById('credential_kind').value = 'device';
      document.getElementById('credential_device').value = button.dataset.addDevicePassword;
      document.getElementById('credential_label').value = button.dataset.deviceName + ' password';
      window.jQuery('#add-credential-modal').modal('show');
    });
  });

  document.querySelectorAll('[data-edit-device]').forEach(function (button) {
    button.addEventListener('click', function () {
      var device = JSON.parse(button.dataset.editDevice);
      var form = document.getElementById('edit-device-form');
      form.action = '/social-engineering/profiles/' + encodeURIComponent(window.socialProfileSecurity.profileId) + '/devices/' + encodeURIComponent(device.id) + '/update';
      document.getElementById('edit_device_name').value = device.name || '';
      document.getElementById('edit_device_type').value = device.device_type || 'other';
      document.getElementById('edit_device_inventory').value = device.mac || '';
      document.getElementById('edit_device_mac').value = device.mac || '';
      document.getElementById('edit_device_manufacturer').value = device.manufacturer || '';
      document.getElementById('edit_device_model').value = device.model || '';
      document.getElementById('edit_device_os').value = device.operating_system || '';
      document.getElementById('edit_device_hostname').value = device.hostname || '';
      document.getElementById('edit_device_status').value = device.status || 'active';
      document.getElementById('edit_device_notes').value = device.notes || '';
      window.jQuery('#edit-device-modal').modal('show');
    });
  });

  document.querySelectorAll('[data-edit-credential]').forEach(function (button) {
    button.addEventListener('click', function () {
      var credential = JSON.parse(button.dataset.editCredential);
      var form = document.getElementById('credential-edit-form');
      form.action = '/social-engineering/profiles/' + encodeURIComponent(window.socialProfileSecurity.profileId) + '/credentials/' + encodeURIComponent(credential.id) + '/update';
      document.getElementById('edit_credential_kind').value = credential.credential_kind || 'unassigned';
      document.getElementById('edit_credential_label').value = credential.label || '';
      document.getElementById('edit_credential_purpose').value = credential.purpose || '';
      document.getElementById('edit_credential_url').value = credential.website_url || '';
      document.getElementById('edit_credential_device').value = credential.device_id || '';
      document.getElementById('edit_credential_username').value = credential.username || '';
      document.getElementById('edit_credential_notes').value = credential.notes || '';
      document.getElementById('edit_credential_secret').value = '';
      document.getElementById('edit_secret_ciphertext').value = '';
      window.jQuery('#edit-credential-modal').modal('show');
    });
  });

  async function encryptCredentialForm(event, secretInputId, ciphertextInputId) {
    var secretInput = document.getElementById(secretInputId);
    if (!secretInput.value) return;
    event.preventDefault();
    if (!vaultPassword && !(await unlockVault())) return;
    try {
      document.getElementById(ciphertextInputId).value = await encryptSecret(secretInput.value, vaultPassword);
      secretInput.value = '';
      event.target.submit();
    } catch (error) {
      window.alert('Unable to encrypt the secret: ' + error.message);
    }
  }
  document.getElementById('credential-form')?.addEventListener('submit', function (event) { encryptCredentialForm(event, 'credential_secret', 'secret_ciphertext'); });
  document.getElementById('credential-edit-form')?.addEventListener('submit', function (event) { encryptCredentialForm(event, 'edit_credential_secret', 'edit_secret_ciphertext'); });

  document.addEventListener('click', async function (event) {
    var button = event.target.closest('.credential-reveal');
    if (!button) return;
    var secret = button.parentElement.querySelector('.credential-secret');
    if (button.getAttribute('aria-pressed') === 'true') {
      secret.textContent = '••••••••';
      button.setAttribute('aria-pressed', 'false');
      button.querySelector('i').className = 'fas fa-eye';
      return;
    }
    if (secret.dataset.legacySecret) {
      secret.textContent = secret.dataset.legacySecret;
    } else {
      if (!vaultPassword && !(await unlockVault())) return;
      try { secret.textContent = await decryptSecret(secret.dataset.ciphertext, vaultPassword); }
      catch (error) { window.alert('Unable to decrypt this secret. Check the master password.'); return; }
    }
    button.setAttribute('aria-pressed', 'true');
    button.setAttribute('aria-label', 'Hide secret');
    button.querySelector('i').className = 'fas fa-eye-slash';
    audit('credential.reveal');
    window.setTimeout(function () {
      secret.textContent = '••••••••';
      button.setAttribute('aria-pressed', 'false');
      button.setAttribute('aria-label', 'Reveal secret');
      button.querySelector('i').className = 'fas fa-eye';
    }, 20000);
  });
  document.addEventListener('visibilitychange', function () { if (document.hidden) lockVault(); });
}());
