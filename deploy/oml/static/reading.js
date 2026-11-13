/* Projector-friendly font size applies to every page and survives navigation. */
(() => {
  'use strict';
  const sizes = [18, 20, 22, 24, 26, 28, 30];
  const key = 'oml-font-size';
  let size = 22;
  try {
    const saved = Number(localStorage.getItem(key));
    if (sizes.includes(saved)) size = saved;
  } catch (_) { /* Reading remains available when browser storage is disabled. */ }
  const apply = () => {
    document.documentElement.dataset.fontSize = String(size);
    const label = document.getElementById('font-size-value');
    if (label) label.textContent = size + 'px';
    const minus = document.getElementById('font-smaller');
    const plus = document.getElementById('font-larger');
    if (minus) minus.disabled = size === sizes[0];
    if (plus) plus.disabled = size === sizes[sizes.length - 1];
  };
  apply();
  document.addEventListener('DOMContentLoaded', () => {
    apply();
    for (const [id, step] of [['font-smaller', -2], ['font-larger', 2], ['font-reset', 0]]) {
      document.getElementById(id)?.addEventListener('click', () => {
        size = step === 0 ? 22 : Math.max(18, Math.min(30, size + step));
        apply();
        try { localStorage.setItem(key, String(size)); } catch (_) { /* Optional storage. */ }
      });
    }
  });
})();
