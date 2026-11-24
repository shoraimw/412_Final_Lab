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
  const form = document.getElementById('reservation-form');
  const quantity = document.getElementById('quantity');
  const note = document.getElementById('stock-note');
  const start = document.getElementById('start-time');
  const end = document.getElementById('end-time');
  const day = form.elements.reservation_date;
  const student = form.elements.student_id;
  let sequence = 0;
  async function refresh() {
    const version = ++sequence;
    const stock = equipment.selectedOptions[0]?.dataset.stock;
    quantity.setCustomValidity('');
    student.setCustomValidity('');
    end.setCustomValidity(start.value && end.value && end.value <= start.value ? 'End time must be later than start time.' : '');
    if (stock === undefined) quantity.removeAttribute('max');
    else quantity.max = stock;
    note.textContent = stock === undefined ? 'Select equipment to see stock.' : stock + ' total units. Select a valid date and time to check availability.';
    if (!equipment.value || !day.value || !day.validity.valid || !start.value || !end.value || end.value <= start.value) return;
    const params = new URLSearchParams({equipment_id: equipment.value, reservation_date: day.value, start_time: start.value, end_time: end.value, student_id: form.dataset.guest === 'true' ? '' : student.value});
    try {
      const response = await fetch('/api/availability?' + params, {cache: 'no-store'});
      if (!response.ok) throw new Error('Availability unavailable');
      const result = await response.json();
      if (version !== sequence) return;
      quantity.max = result.available;
      note.textContent = result.available + ' of ' + result.stock + ' units available for this slot.';
      if (Number(quantity.value) > result.available) quantity.setCustomValidity('Requested quantity exceeds available equipment.');
      if (result.overlap) student.setCustomValidity('An overlapping reservation already exists.');
    } catch (error) {
      if (version === sequence) note.textContent = 'Live availability unavailable. The server will validate your request.';
    }
  }
  for (const field of [equipment, day, start, end, student, quantity]) field.addEventListener('input', refresh);
  refresh();
}
