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

  document.addEventListener('DOMContentLoaded', function () {
    enhanceTables();
    addKeyboardSearch();
    markExternalLinks();
  });
}());
