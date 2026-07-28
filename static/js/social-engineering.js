(function () {
  'use strict';
  function addRow(type) {
    var list = document.querySelector('[data-repeat-list="' + type + '"]');
    var row = list.querySelector('.social-repeat-row').cloneNode(true);
    row.querySelectorAll('input').forEach(function (input) { input.value = ''; });
    row.querySelectorAll('textarea').forEach(function (textarea) { textarea.value = ''; });
    row.querySelectorAll('select').forEach(function (select) { select.selectedIndex = 0; });
    list.appendChild(row);
  }
  document.addEventListener('click', function (event) {
    if (event.target.closest('[data-add-email]')) addRow('emails');
    if (event.target.closest('[data-add-social]')) addRow('social');
    var remove = event.target.closest('[data-remove-row]');
    if (remove) {
      var row = remove.closest('.social-repeat-row');
      var list = row.parentElement;
      if (list.querySelectorAll('.social-repeat-row').length > 1) row.remove();
      else row.querySelectorAll('input').forEach(function (input) { input.value = ''; });
    }
  });
  document.addEventListener('change', function (event) {
    if (!event.target.matches('.recovery-ref-picker')) return;
    var hidden = event.target.parentElement.nextElementSibling;
    hidden.value = Array.from(event.target.selectedOptions).map(function (option) { return option.value; }).join(',');
  });
}());
