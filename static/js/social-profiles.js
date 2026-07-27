document.addEventListener('click', function (event) {
  var button = event.target.closest('.credential-reveal');
  if (!button) return;
  var secret = button.parentElement.querySelector('.credential-secret');
  var revealing = button.getAttribute('aria-pressed') !== 'true';
  secret.textContent = revealing ? secret.dataset.secret : '••••••••';
  button.setAttribute('aria-pressed', revealing ? 'true' : 'false');
  button.setAttribute('aria-label', revealing ? 'Hide secret' : 'Reveal secret');
  button.querySelector('i').className = revealing ? 'fas fa-eye-slash' : 'fas fa-eye';
});
