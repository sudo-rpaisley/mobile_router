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

  function unlockVault() {
    if (!window.crypto || !window.crypto.subtle) {
      window.alert('Credential encryption requires localhost or an HTTPS connection.');
      return false;
    }
    var password = window.prompt('Enter the credential vault master password:');
    if (!password) return false;
    vaultPassword = password;
    clearTimeout(lockTimer);
    lockTimer = setTimeout(lockVault, 5 * 60 * 1000);
    setVaultStatus(true);
    audit('vault.unlock');
    return true;
  }

  document.getElementById('vault-unlock')?.addEventListener('click', unlockVault);
  document.getElementById('vault-lock')?.addEventListener('click', lockVault);

  document.getElementById('credential-form')?.addEventListener('submit', async function (event) {
    var secretInput = document.getElementById('credential_secret');
    if (!secretInput.value) return;
    event.preventDefault();
    if (!vaultPassword && !unlockVault()) return;
    try {
      document.getElementById('secret_ciphertext').value = await encryptSecret(secretInput.value, vaultPassword);
      secretInput.value = '';
      event.target.submit();
    } catch (error) {
      window.alert('Unable to encrypt the secret: ' + error.message);
    }
  });

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
      if (!vaultPassword && !unlockVault()) return;
      try { secret.textContent = await decryptSecret(secret.dataset.ciphertext, vaultPassword); }
      catch (error) { window.alert('Unable to decrypt this secret. Check the master password.'); return; }
    }
    button.setAttribute('aria-pressed', 'true');
    button.setAttribute('aria-label', 'Hide secret');
    button.querySelector('i').className = 'fas fa-eye-slash';
    audit('credential.reveal');
  });
}());
