(function () {
  'use strict';

  function enhanceTables() {
    document.querySelectorAll('#result_list tbody tr').forEach(function (row) {
      row.addEventListener('mouseenter', function () { row.dataset.bsHover = 'true'; });
      row.addEventListener('mouseleave', function () { delete row.dataset.bsHover; });
    });
  }

  function addKeyboardSearch() {
    var search = document.querySelector('#searchbar');
    if (!search) return;
    document.addEventListener('keydown', function (event) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        search.focus();
        search.select();
      }
    });
  }

  function markExternalLinks() {
    document.querySelectorAll('a[target="_blank"]').forEach(function (link) {
      link.setAttribute('rel', 'noopener noreferrer');
    });
  }

  function addPasswordToggle() {
    var toggle = document.querySelector('[data-password-toggle]');
    var password = document.querySelector('#id_password');
    if (!toggle || !password) return;
    toggle.addEventListener('click', function () {
      var isVisible = password.type === 'text';
      password.type = isVisible ? 'password' : 'text';
      toggle.setAttribute('aria-pressed', String(!isVisible));
      toggle.textContent = isVisible ? toggle.dataset.showLabel : toggle.dataset.hideLabel;
      password.focus();
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    enhanceTables();
    addKeyboardSearch();
    markExternalLinks();
    addPasswordToggle();
  });
}());
