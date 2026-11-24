'use strict';
const menu = document.getElementById('menu');
const sidebar = document.getElementById('sidebar');
menu.addEventListener('click', () => {
  const open = sidebar.classList.toggle('open');
  menu.setAttribute('aria-expanded', String(open));
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') {
    sidebar.classList.remove('open');
    menu.setAttribute('aria-expanded', 'false');
  }
});
const search = document.getElementById('search');
if (search) {
  const rows = [...document.querySelectorAll('#equipment-table tbody tr')];
  search.addEventListener('input', () => {
    const term = search.value.trim().toLowerCase();
    let matches = 0;
    rows.forEach(row => {
      row.hidden = !row.textContent.toLowerCase().includes(term);
      if (!row.hidden) matches++;
    });
    document.getElementById('no-match').hidden = matches !== 0;
  });
}
const equipment = document.getElementById('equipment');
if (equipment) {
  const quantity = document.getElementById('quantity');
  const stockNote = document.getElementById('stock-note');
  const updateStock = () => {
    const stock = equipment.selectedOptions[0]?.dataset.stock;
    if (stock !== undefined) {
      quantity.max = stock;
      stockNote.textContent = stock + ' units in stock. Slot availability checked on approval.';
    } else {
      quantity.removeAttribute('max');
      stockNote.textContent = 'Select equipment to see stock.';
    }
  };
  equipment.addEventListener('change', updateStock);
  updateStock();
  const start = document.getElementById('start-time');
  const end = document.getElementById('end-time');
  const checkTime = () => end.setCustomValidity(start.value && end.value && end.value <= start.value ? 'End time must be later than start time.' : '');
  start.addEventListener('input', checkTime);
  end.addEventListener('input', checkTime);
  checkTime();
}
